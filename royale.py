"""Entry point: detect at run time whether this match is the practice squad or a free-for-all.

Practice: 15 house bots on one squad never fight each other, so before the late zone the
only mechs that die are the ones we kill. Free-for-all: other mechs die without us, and we
see beams from one mech ending on another. Until the evidence arrives we play the practice
policy; once it does we switch for the rest of the match.
"""
import mechfight as mf
import example_bot as eb
import duel_bot
import math
import time

# Deterministic play: wide time caps so per-call work limits decide, not the wall clock.
eb.PLAN_BUDGET_S = 0.010
eb.ROUTE_SLICE_S = 0.004
from example_bot import obj, seq, number, vec, distance, bearing, angle, limit, raised

SEED = 1                    # the only source of randomness; a different value is a different draw
FORCE_MODE = None           # None = detect; "practice" or "free-for-all" pins the policy
GUARDED_OPENER = True       # squad play fights only mechs that attack or close on us


class Detector:
    """Strict free-for-all detector: it must stay quiet in the squad game.

    House bots never fight each other, so before the zone turns deadly a mech we did not kill
    almost never dies, and no laser beam goes from one mech into another. Only those two
    signals count here (HP loss can come from drones we cannot see; lightning arcs pick
    drones and crates too). Free-for-all once:
      - 2 deaths we did not cause while zone dps <= 35 (the first two phases), or
      - 3 such deaths while zone dps <= 100, or
      - laser beams from one mech ending on another, away from us and from drones and
        crates, seen at 2 different times.
    """

    def __init__(self, hello):
        self.slot = number(hello.get("slot"), -1)
        self.start_alive = None
        self.kills = 0
        self.beam_times = []
        self.ffa = False
        self.reason = ""
        self.score = 0.0

    def update(self, obs, now):
        if self.ffa:
            return True
        for event in seq(obs.get("events"))[:200]:
            if obj(event).get("type") == "kill":
                self.kills += 1
        alive = number(obs.get("alive"), None)
        dps = number(obj(obs.get("zone")).get("dps"), 0)
        if alive is not None:
            if self.start_alive is None:
                self.start_alive = max(alive, 1)
            others = (self.start_alive - alive) - self.kills
            self.score = others
            if (others >= 2 and dps <= 35) or (others >= 3 and dps <= 100):
                self.ffa, self.reason = True, f"{others} deaths not ours at {now:.1f}s (dps {dps:.0f})"
                return True
        me = vec(obj(obs.get("self")).get("pos"), 3)
        if me is None:
            return False
        mechs, others_near = [], []
        for entry in seq(obs.get("mechs"))[:48]:
            entry = obj(entry)
            p = vec(entry.get("pos"), 3)
            ident = number(entry.get("id"), None)
            if p is None or ident is None or ident == self.slot:
                continue
            (mechs if entry.get("kind") == "mech" else others_near).append((ident, p))
        others_near += [(None, p) for item in seq(obs.get("crates"))[:40] if (p := vec(obj(item).get("pos"), 3)) is not None]
        for beam in seq(obs.get("beams"))[:32]:
            beam = obj(beam)
            if beam.get("kind") != "laser":
                continue
            path = seq(beam.get("path"))
            end = vec(path[1], 3) if len(path) >= 2 else None
            by = number(beam.get("by"), None)
            if end is None or by is None or by == self.slot or distance(end, me) < 20:
                continue
            if any(distance(end, p) < 12 for _, p in others_near):
                continue
            if any(ident != by and distance(end, p) < 4.5 for ident, p in mechs):
                if not self.beam_times or now - self.beam_times[-1] > 1.0:
                    self.beam_times.append(now)
        if len(self.beam_times) >= 2:
            self.ffa, self.reason = True, f"laser beams mech-to-mech at {self.beam_times[:2]}"
        return self.ffa


class Selective(eb.Bot):
    SEPARATION = 145.0
    UPGRADES = (
        ("servos", "nanites", "plating", "armor", "laser_damage", "gyros"),
        ("plating", "laser_charge", "gun_rate", "armor", "nanites", "gun_mag", "capacitor"),
        ("plating", "nanites", "armor", "laser_charge", "reactor"),
        ("laser_damage", "laser_charge", "gun_mag"),
        ("laser_damage", "plating", "armor", "nanites", "servos", "gun_rate", "laser_charge"),
        ("laser_charge", "laser_damage", "plating", "armor"),
        ("laser_damage", "plating", "armor"),
        ("armor", "plating", "laser_damage"),
    )
    SECONDARIES = ("laser", "lightning")

    def __init__(self, hello):
        super().__init__(hello)
        self.duel = duel_bot.DuelBot(hello)
        self.pickups = {}
        self.visible_pickups = {}
        self.last_seen = {}
        self.rivals = []
        self.goal = None
        self.goal_until = -math.inf
        self.last_mech_damage = -math.inf
        vision = obj(obj(hello.get("config")).get("vision"))
        self.vision = limit(number(vision.get("range"), 200), 45, 350)
        self.near_vision = limit(number(vision.get("near_range"), 45), 5, 100)
        self.half_fov = math.radians(limit(number(vision.get("fov_deg"), 120), 10, 360) / 2)
        self.mode = "survive"

    def observe(self, obs, me, pos, actual, now):
        previous = self.last_seen
        self.last_seen = {i: (t, p) for i, (t, p) in previous.items() if 0 <= now - t < 3}
        self.enemy_cubes = {}
        for raw in seq(obs.get("mechs"))[:48]:
            enemy = obj(raw)
            ident, point = number(enemy.get("id"), None), vec(enemy.get("pos"), 3)
            if enemy.get("kind") == "mech" and ident is not None and ident != self.slot and point is not None:
                self.last_seen[ident] = now, point
                self.enemy_cubes[ident] = limit(number(enemy.get("cubes"), 0), 0, 100)
        if self.alive == 2 and self.enemy_cubes:
            self.last_seen = {i: self.last_seen[i] for i in self.enemy_cubes}
        self.rivals = sorted((distance(pos, p), p) for _, p in self.last_seen.values())[:16]
        self.heard_rival = None
        for raw in seq(obs.get("sounds"))[:40]:
            sound = obj(raw)
            reach = {"near": 42, "mid": 100}.get(sound.get("dist")) if isinstance(sound.get("dist"), str) else None
            yaw = number(sound.get("bearing"), None)
            if (reach and yaw is not None and number(sound.get("age"), 0) < 0.45
                    and sound.get("kind") in ("gun", "laser", "laser_charge", "lightning", "mortar", "boost", "step")):
                self.heard_rival = pos[0] + reach * math.cos(yaw), pos[1] + reach * math.sin(yaw), pos[2]
                break

        if "laser" in self.kinds:
            self.pickups.clear()
            return
        visible = {}
        for raw in seq(obs.get("pickups"))[:64]:
            item = obj(raw)
            ident, point = number(item.get("id"), None), vec(item.get("pos"), 3)
            if ident is not None and ident >= 0 and point is not None and item.get("kind") in self.SECONDARIES:
                visible[ident] = (now, item["kind"], point)
        for raw in seq(obs.get("events"))[:40]:
            event = obj(raw)
            if event.get("type") == "take_failed" and event.get("reason") == "gone":
                self.pickups.pop(number(event.get("id"), None), None)
        eye = raised(pos, self.phys("eye_height", 8, obj(me.get("stats"))))
        remembered = {}
        for ident, record in self.pickups.items():
            t, _, point = record
            if ident in visible or not 0 <= now - t <= 22:
                continue
            d = distance(pos, point)
            expected = d <= self.near_vision - 3 or (
                d <= self.vision - 10 and abs(angle(bearing(pos, point) - actual[0])) < self.half_fov - 0.10
            )
            if not expected or (self.arena is not None and not self.arena.clear_ray(eye, raised(point, 0.5))):
                remembered[ident] = record
        remembered.update(visible)
        self.pickups = dict(list(remembered.items())[-64:])
        self.visible_pickups = visible

    def clear_approach(self, pos, goal, clearance):
        dx, dy = goal[0] - pos[0], goal[1] - pos[1]
        span = max(0.01, dx * dx + dy * dy)
        rivals = self.rivals
        if not rivals and self.heard_rival is not None:
            rivals = [(distance(pos, self.heard_rival), self.heard_rival)]
        for here, enemy in rivals:
            along = limit(((enemy[0] - pos[0]) * dx + (enemy[1] - pos[1]) * dy) / span, 0, 1)
            nearest = pos[0] + along * dx, pos[1] + along * dy
            if (distance(nearest, enemy) < min(clearance, here - 1)
                    or distance(goal, enemy) < min(clearance, here + 10)):
                return False
        return True

    def weapon_goal(self, pos, zone, weapons, urgent, action):
        if "laser" in self.kinds:
            return None
        spare = next((i for i, w in enumerate(weapons) if not w.get("kind")), None)
        swap = next((i for i, w in enumerate(weapons) if w.get("kind") in ("lightning", "mortar")), None)
        if spare is None and swap is None:
            return None
        options = []
        reach = limit(number(self.loot.get("pickup_radius"), 4), 0.5, 15)
        for ident, (_, kind, point) in self.pickups.items():
            if kind in self.kinds:
                continue
            d, climb = distance(pos, point), point[2] - pos[2]
            if d <= reach - 0.15 and abs(climb) <= 3.5 and ident in self.visible_pickups:
                options.append((kind != "laser", 0, ident, point))
            elif (not urgent and d < 8 and abs(climb) <= 3.5 and ident in self.visible_pickups
                  and (not self.rivals or self.rivals[0][0] > 65)
                  and zone.gap(point, 2) > 2):
                options.append((kind != "laser", d, ident, point))
            elif (not urgent and -65 <= climb <= 36 and (climb <= 4 or self.energy > 45)
                  and d < (70 if "lightning" in self.kinds else 240)
                  and zone.gap(point, d / 9 + 4) > min(3, zone.radius * 0.12)
                  and self.clear_approach(pos, point, 120)):
                outside = max(0, distance(point, zone.next_center) - zone.next_radius + 10)
                options.append((kind != "laser", d + max(0, climb - 4) * 2 + outside * 0.55, ident, point))
        if not options:
            return None
        _, cost, ident, point = min(options)
        if cost == 0:
            action["take"] = ident
            if spare is None:
                action["drop"] = swap
            return None
        self.weapon_point = point
        self.mode = "arm"
        return point[:2]

    def loot_goal(self, obs, pos, zone, contacts, weapons, hp_fraction, cubes, safe, urgent, action):
        goal = self.weapon_goal(pos, zone, weapons, urgent, action)
        if goal is not None:
            return goal
        nearest = self.rivals[0][0] if self.rivals else math.inf
        quiet = nearest >= self.SEPARATION and self.heard_rival is None and zone.now - self.last_mech_damage > 3
        if urgent or not quiet:
            return None
        options = []
        for raw in seq(obs.get("cubes"))[:64]:
            point = vec(obj(raw).get("pos"), 3)
            if point is not None and abs(point[2] - pos[2]) < 4:
                d = distance(pos, point)
                if d < 135 and zone.gap(point, d / 9 + 3) > 2 and self.clear_approach(pos, point, self.SEPARATION):
                    options.append((d, point[:2]))
        for raw in seq(obs.get("drops"))[:8]:
            item = obj(raw)
            point = vec(item.get("pos"), 3)
            if point is None or item.get("holder") not in (None, self.slot):
                continue
            d = distance(pos, point)
            if (d < 110 and number(item.get("lands_in"), 0) < d / 10 + 1
                    and zone.gap(point, d / 9 + 10) > 4 and self.clear_approach(pos, point, 165)):
                options.append((d * 0.60 - 14 - 24 * (1 - hp_fraction), point[:2]))
        if options:
            self.mode = "loot"
            return min(options)[1]
        if (self.alive <= 3 or zone.next_radius < 40 or hp_fraction < 0.8 or nearest < 175
                or (cubes >= 21 and not self.kinds.isdisjoint(self.SECONDARIES))):
            return None
        farms = [c for c in contacts if c.kind == "npc" and c.clear and c.dist < 78]
        for raw in seq(obs.get("crates"))[:36]:
            item = obj(raw)
            point, ident = vec(item.get("pos"), 3), number(item.get("id"), None)
            if point is None or ident is None or abs(point[2] - pos[2]) > 12:
                continue
            d = distance(pos, point)
            if d < 95 and (self.arena is None or self.arena.clear_ray(raised(pos, 7), raised(point, 1.2))):
                farms.append(eb.Contact(ident, "crate", point, eb.ZERO, None, number(item.get("hp"), 300),
                                        300, 1, d, 0, True, False, False, ()))
        if farms and distance(pos, zone.next_center) < zone.next_radius - 6:
            self.farm = min(farms, key=lambda c: c.dist + 14 * (c.kind == "npc"))
        return None

    def shelter_point(self, pos, zone, contacts, direction, radius, height, now, until, terminal_burn):
        if terminal_burn:
            return super().shelter_point(pos, zone, contacts, direction, radius, height, now, until, True)
        if self.farm is not None:
            return pos[:2]
        if self.goal is not None and now < self.goal_until and distance(pos, self.goal) > 3:
            if all(distance(self.goal, p) >= min(120, d - 4) for d, p in self.rivals):
                return self.goal

        arena = self.arena
        goal_radius = max(0, zone.next_radius - min(16, zone.next_radius * 0.22))
        next_gap = goal_radius - distance(pos, zone.next_center)
        roam = ((self.alive > 3 and self.kinds.isdisjoint(self.SECONDARIES) and self.hp_share > 0.65)
                or (self.alive == 2 and not self.rivals and self.hp_share > 0.86))
        scout = self.scout_yaw + math.floor(now / 10) * 1.91
        sx, sy = math.cos(scout), math.sin(scout)
        enemies = self.rivals
        if not enemies and self.heard_rival is not None:
            enemies = [(distance(pos, self.heard_rival), self.heard_rival)]
        options = []
        for run in (0, 26, 58):
            for dx, dy in eb.COVER_ANGLES if run else ((0, 0),):
                point = pos[0] + dx * run, pos[1] + dy * run
                if zone.gap(point, 7) < min(5, zone.radius * 0.18):
                    continue
                cell = arena.cell(*point) if arena is not None else None
                if run and arena is not None and not arena.ground_ok(cell, radius):
                    continue
                base = arena.floor[cell] if run and cell is not None else pos[2]
                gap = goal_radius - distance(point, zone.next_center)
                score = min(0, gap) * 1.5 + min(18, max(0, gap)) * 0.15 - run * 0.16
                if roam and next_gap > -28:
                    score += run * (0.22 + (dx * sx + dy * sy) * 0.15)
                if cell is not None:
                    near = arena.clearance[cell] * eb.GRID_M
                    score += max(0, 20 - abs(near - radius - 5)) * 0.65
                for d, enemy in enemies:
                    separation = distance(point, enemy)
                    score -= max(0, self.SEPARATION - separation) * (1.5 if d < 125 else 0.85)
                    score -= max(0, 64 - separation) * 1.8
                    if self.alive == 2 and self.fight is not None:
                        preferred = 152 if "laser" in self.kinds else 125
                        score -= abs(separation - preferred) * 1.2
                options.append((score, run, point, base))
        best, top_score = pos[:2], -math.inf
        standing = [option for option in options if option[1] == 0]
        for score, run, point, base in sorted(options, reverse=True)[:5] + standing:
            if arena is not None and time.perf_counter() < until:
                for _, enemy in enemies[:2]:
                    if not arena.clear_ray(raised(enemy, 8), (point[0], point[1], base + height * 0.65)):
                        score += 28
                if run and not arena.corridor(pos, point, radius, height):
                    score -= 9
            if score > top_score:
                best, top_score = point, score
        self.goal, self.goal_until = best, now + 0.65
        return best

    def route(self, pos, goal, zone, radius, height, stuck, until):
        arena, pickup = self.arena, self.weapon_point
        if (arena is not None and pickup is not None and pickup[:2] == goal
                and 3.5 < pickup[2] - pos[2] and distance(pos, pickup) < 30
                and not arena.solid(raised(pos, height + 1.5))):
            self.climb = True
            return goal
        waypoint = super().route(pos, goal, zone, radius, height, stuck, until)
        if (waypoint != goal and self.rivals and not self.clear_approach(pos, waypoint, 105)
                and zone.gap(pos, 3) > 8):
            return self.shelter_point(pos, zone, (), None, radius, height, zone.now, until, False)
        return waypoint

    def movement(self, pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction, stats,
                 grounded, energy, now, until, in_zone, terminal_burn, drop_hint):
        nearest = self.rivals[0][0] if self.rivals else math.inf
        running = (nearest < 118 and self.fight is None and self.weapon_point is None
                   and (distance(pos, waypoint) > eb.HOLD_M or any(c.clear for c in threats)))
        move = super().movement(pos, vel, waypoint, zone, urgent, evade or running, threats, hazards, direction,
                                stats, grounded, energy, now, until, in_zone, terminal_burn, drop_hint)
        if self.climb:
            course = bearing(pos, waypoint)
            speed = 0.33 if self.weapon_point[2] - pos[2] > 7 else 0.75
            return {"move": [speed * math.cos(course), speed * math.sin(course)],
                    "jump": grounded, "boost": not grounded}
        if (running or (self.weapon_point is not None and nearest > 135)) and grounded and energy > 35:
            if distance(pos, waypoint) > 12 and not move.get("jump"):
                move["boost"] = True
        self.cornered = (nearest < 34 and self.weapon_point is None and (
            zone.radius < 48 or (now < self.stuck_until and not move.get("boost"))
            or distance(pos, waypoint) < 4
        ))
        return move

    def target(self, obs, pos, contacts, fraction, zone, must_move, safe, terminal_burn, repairing, incoming):
        if self.cornered or terminal_burn:
            nearby = [c for c in contacts if c.kind == "mech" and c.clear and c.dist < (195 if terminal_burn else 48)]
            if nearby:
                return [(100, min(nearby, key=lambda c: c.dist))]
        if self.fight is not None:
            return [(100, self.fight)]
        return [(50, self.farm)] if self.farm is not None else []

    def contacts(self, obs, pos, eye):
        contacts = super().contacts(obs, pos, eye)
        self.exposed = any(c.kind == "mech" and c.clear and c.dist < 100 for c in contacts)
        if self.alive == 3 or (self.alive > 3 and self.kinds.isdisjoint(self.SECONDARIES)):
            return contacts
        for enemy in sorted(contacts, key=lambda c: c.hp):
            if (enemy.kind != "mech" or not enemy.clear or not enemy.armed
                    or not math.isfinite(enemy.hp) or self.hp_share < 0.47):
                continue
            laser = "laser" in self.kinds
            their_laser = "laser" in enemy.armed
            if their_laser and not laser:
                continue
            long_range = 108 <= enemy.dist <= (200 if laser else 158)
            advantage = self.hp / max(1, enemy.hp)
            cube_edge = min(self.cube_count, 21) - min(self.enemy_cubes.get(enemy.id, 0), 21)
            advantage *= 1 + 0.022 * cube_edge
            if laser and not their_laser:
                advantage *= 1.45
            if "lightning" in enemy.armed and "lightning" not in self.kinds and enemy.dist < 55:
                advantage *= 0.65
            alone = all(distance(enemy.pos, p) < 1 or d >= 175 for d, p in self.rivals)
            if self.alive == 2:
                allowed = ((long_range and advantage >= 0.93)
                           or (enemy.dist >= 60 and advantage > 1.65)
                           or (enemy.dist < 40 and "lightning" in self.kinds and advantage > 1.3))
            else:
                allowed = long_range and alone and advantage >= 1.9
            if allowed:
                self.fight = enemy
                break
        return contacts

    def act(self, obs):
        errors = (ArithmeticError, LookupError, TypeError, ValueError, AttributeError)
        self.mode = "survive"
        self.weapon_point = self.fight = self.farm = None
        self.climb = self.cornered = False
        me = obj(obs.get("self"))
        now, pos = number(obs.get("t"), 0), vec(me.get("pos"), 3)
        actual = vec(me.get("aim"), 2) or (0, 0)
        offer = seq(obj(obs.get("offer")).get("choices"))[:3]
        try:
            self.kinds = {obj(w).get("kind") for w in seq(me.get("weapons"))[:2]
                          if obj(w).get("kind") in duel_bot.KNOWN_WEAPONS}
            self.alive = number(obs.get("alive"), 16)
            self.hp = max(0, number(me.get("hp"), 0))
            self.hp_share = self.hp / max(1, number(me.get("max_hp"), 1400))
            self.cube_count = limit(number(me.get("cubes")), 0, 100)
            self.energy = limit(number(me.get("energy")), 0, 1000)
            for raw in seq(obs.get("events"))[:40]:
                event = obj(raw)
                if (event.get("type") == "damaged" and event.get("weapon") not in ("zone", "npc")
                        and number(event.get("by"), 0) < 100):
                    self.last_mech_damage = now
            if pos is not None:
                self.observe(obs, me, pos, actual, now)
            self.last_fire_target = None
            action = super().act(obs)
            if self.last_fire_target is None and pos is not None:
                if self.weapon_point is not None and not self.exposed:
                    action["aim"] = [bearing(pos, self.weapon_point), 0.0]
                elif not self.rivals and now - self.last_damage >= eb.HIT_MEMORY_S:
                    action["aim"] = [angle(self.scout_yaw + now * 1.9), 0.0]
        except errors:
            try:
                self.duel.arena = self.arena
                action = self.duel.act(obs) or {}
                for key in ("fire", "take", "drop"):
                    action.pop(key, None)
            except errors:
                action = {}
        if offer:
            index = min(len(seq(me.get("upgrades"))), len(self.UPGRADES) - 1)
            rank = self.UPGRADES[index]
            def priority(i):
                upgrade = obj(offer[i]).get("id")
                if not isinstance(upgrade, str):
                    return 0
                if upgrade in rank:
                    return 200 - rank.index(upgrade)
                return eb.UPGRADE_RANK.get(upgrade, 0)
            action["pick"] = max(range(len(offer)), key=priority)
        return action


class Royale:
    def __init__(self, hello):
        duel_bot.SEED_SALT = SEED
        self.practice = duel_bot.DuelBot(hello)
        self.practice.guarded = GUARDED_OPENER
        self.ffa = Selective(hello)
        self.detector = Detector(hello)
        self.mode = FORCE_MODE or "practice"
        self.first_ffa = None

    def __getattr__(self, name):
        # Tools and tests that inspect the policy see the active one.
        if name in ("practice", "ffa", "detector", "mode", "first_ffa"):
            raise AttributeError(name)
        return getattr(self.ffa if self.mode == "free-for-all" else self.practice, name)

    def load_map(self):
        self.practice.load_map()
        self.ffa.arena = self.practice.arena
        return True

    def act(self, obs):
        obs = obj(obs)
        now = number(obs.get("t"), 0)
        if FORCE_MODE is None:
            try:
                want = "free-for-all" if self.detector.update(obs, now) else "practice"
            except (ArithmeticError, LookupError, TypeError, ValueError, AttributeError):
                want = self.mode
            if want != self.mode:
                self.mode = want
                if want == "free-for-all" and self.first_ffa is None:
                    self.first_ffa = round(now, 1)
                mf.log(f"mode {want}: {self.detector.reason}")
        if self.mode == "free-for-all":
            return self.ffa.act(obs)
        return self.practice.act(obs)


if __name__ == "__main__":
    mf.run(Royale)
