"""Duel-first policy for Mech Royale practice: fight the squad one hunter at a time.

The map, routing, zone, loot and aiming helpers come from example_bot.py (the survive-first
policy, kept as the free-for-all mode). This file decides when and how to fight.
"""
import math
import random
import time

import mechfight as mf
import example_bot as eb
from example_bot import (Bot, Contact, Zone, ZERO, obj, seq, number, vec, limit, angle, bearing, distance)

SHELTER_SLICE_S = 0.006     # time caps are safety nets only: node and count limits should bind
STEER_SLICE_S = 0.004
SEED_SALT = 0               # set by royale.SEED; changes every random choice, same policy
PLAY_MODE = "practice"  # "practice" = duel-first (this file); "free-for-all" = survive-first example_bot.Bot

DUEL_UPGRADES = {   # offensive first, as the 5.48 leader picks
    "lightning_range": 110, "gun_damage": 100, "lightning_efficiency": 100, "gun_rate": 95, "armor": 90,
    "gun_mag": 90, "laser_damage": 90, "plating": 85, "gun_velocity": 85, "laser_charge": 85, "nanites": 80,
    "servos": 80, "jets": 80, "reactor": 80, "lightning_chain": 80, "gyros": 60, "mortar_reload": 60,
    "mortar_splash": 60, "mortar_velocity": 50, "capacitor": 50, "sensors": 40, "laser_pierce": 40,
}
KNOWN_WEAPONS = ("gun", "mortar", "laser", "lightning")
SECOND_RANK = {"lightning": 3, "laser": 2}   # lightning first (gun kept); never pick up a mortar


class _Ranks(dict):
    """Weapon ranks for the shared loot code: .get() hides the mortar so it is never taken."""
    def get(self, key, default=None):
        return None if key == "mortar" else super().get(key, default)


DUEL_WEAPON_RANK = _Ranks({"gun": 0, "mortar": -1, "lightning": 3, "laser": 2})
FIRST_WEAPON_DETOUR_M = 135.0   # walk this far for a first lightning or laser
LIGHTNING_SWAP_M = 70.0         # and this far to trade a laser for lightning
HEAL_BELOW, HEAL_UNTIL = 0.43, 0.83
CROWD_RANGE_M = 90.0
LASER_RANGE_M = 130.0
REPAIR_TO = 0.85                # heal to this share before hunting the next one
VEL_SMOOTH = 0.35          # weight of the newest velocity sample in the per-target average
RETREAT_FRACTION = 0.30    # break contact below this health share when the duel is going badly
NPC_FARM_M = 170.0          # walk to drones this far for their 2 cubes
FARM_HP = 0.50              # farm drones and crates above this health share
FIGHT_CUBE_M = 40.0
GUN_RANGE_M = 90.0          # preferred gun-only duel range (simulator: dodging needs flight time)
STRAFE_MIN_S = 0.3
STRAFE_MAX_S = 0.7
CRATE_FARM_M = 70.0


class DuelBot(Bot):
    def __init__(self, hello):
        super().__init__(hello)
        self.rng = random.Random(int(SEED_SALT) * 1000003 + int(number(hello.get("seed"), 0)))
        self.strafe_sign = 1 if self.rng.random() < 0.5 else -1
        self.strafe_until = 0.0
        self.vel_avg = {}
        self.seen_hp = {}
        self.retreat_until = -math.inf
        self.mode = "start"
        self.hp_share = 1.0
        self.healing = False
        self.light_range = 45.0
        self.dodging = False
        self.guarded = False   # opener: fight only mechs that attack or close on us
        self.last_seen = {}        # mech id -> (time, pos)
        self.kill_spot = None      # (time, pos) where a victim died
        self.hunt_point = None     # (time, pos) best guess of where a hunter is

    # ------------------------------------------------------------------ targets
    def track(self, contacts):
        for c in contacts:
            old = self.vel_avg.get(c.id)
            v = c.vel
            if old is not None:
                v = tuple(o + (n - o) * VEL_SMOOTH for o, n in zip(old, c.vel))
            self.vel_avg[c.id] = v

    def lead_contact(self, c):
        """Aim between the current velocity and the recent mean: a jinking target averages out."""
        avg = self.vel_avg.get(c.id, c.vel)
        vel = tuple(0.5 * a + 0.5 * b for a, b in zip(avg, c.vel))
        return Contact(c.id, c.kind, c.pos, vel, c.aim, c.hp, c.max_hp, c.scale, c.dist, c.face_error,
                       c.clear, c.attacker, c.charging, c.armed)

    def target(self, obs, pos, contacts, fraction, zone, must_move, safe, terminal_burn, repairing, incoming):
        targets = []
        farming_ok = self.hp_share >= FARM_HP
        mechs = [c for c in contacts if c.kind == "mech"]
        for c in contacts:
            if c.kind == "mech" and self.guarded and not self.engaging_us(c, pos):
                continue
            if c.kind == "mech":
                share = c.hp / c.max_hp if math.isfinite(c.hp) else 1.0
                rear = c.face_error > math.pi / 2
                merit = 120 + 60 * (1 - share) + 25 * c.attacker + 20 * rear - c.dist * 0.35
                merit += 12 * (c.id == self.last_fire_target) + (30 if c.clear else -40)
            else:
                if mechs and any(m.clear and m.dist < 150 for m in mechs):
                    continue
                if c.dist > NPC_FARM_M or terminal_burn or not (farming_ok or c.attacker):
                    continue
                merit = 40 + (350 - min(350, c.hp)) * 0.1 - c.dist * 0.3 + 30 * c.attacker
            targets.append((merit, self.lead_contact(c)))
        if farming_ok and not any(m.clear and m.dist < 150 for m in mechs) and not must_move and not terminal_burn:
            for item in seq(obs.get("crates"))[:36]:
                item = obj(item)
                p, ident = vec(item.get("pos"), 3), number(item.get("id"), None)
                if p is None or ident is None or abs(p[2] - pos[2]) > 12:
                    continue
                d = distance(pos, p)
                if d > CRATE_FARM_M:
                    continue
                hp = number(item.get("hp"), 300)
                targets.append((20 + (300 - hp) * 0.06 - d * 0.27 + 8 * (ident == self.last_fire_target),
                                Contact(ident, "crate", p, ZERO, None, hp, 300, 1, d, 0, True, False, False, ())))
        return sorted(targets, key=lambda choice: choice[0], reverse=True)[:4]

    def engaging_us(self, c, pos):
        """A mech that has hit us, is close, or is closing on us while facing us."""
        if c.attacker or c.dist < 60:
            return True
        dx, dy = pos[0] - c.pos[0], pos[1] - c.pos[1]
        d = math.hypot(dx, dy) or 1.0
        closing = (c.vel[0] * dx + c.vel[1] * dy) / d
        facing = c.aim is not None and abs(angle(c.aim[0] - bearing(c.pos, pos))) < 0.5
        return c.dist < 140 and closing > 3.0 and facing

    # ----------------------------------------------------------------- movement
    def desired_range(self, kinds, foe, energy=100.0, crowd=1, light_range=45.0):
        """Orbit ranges as the leader plays them: 34 m with lightning (energy for arcs),
        76 m with the gun, 105 m with a laser; widen to 90 m when 3+ are near; close to 42 m
        on a foe under 260 HP when 2 or fewer are near."""
        if "lightning" in kinds and energy >= 9:
            r = min(34.0, light_range * 0.8)
        elif "mortar" in kinds:
            r = 58.0
        elif "laser" in kinds:
            r = 105.0
        else:
            r = 76.0
        if crowd >= 3:
            r = max(r, CROWD_RANGE_M)
        if math.isfinite(foe.hp) and foe.hp < 260 and crowd <= 2:
            r = min(r, 42.0)
        return r

    def free_dir(self, pos, course, radius, height, reach=5.0):
        arena = self.arena
        if arena is None:
            return course
        for delta in (0.0, 0.4, -0.4, 0.8, -0.8, 1.3, -1.3, 1.9, -1.9, 2.6, -2.6, math.pi):
            c = course + delta
            goal = (pos[0] + reach * math.cos(c), pos[1] + reach * math.sin(c))
            if arena.corridor(pos, goal, radius, height):
                return c
        return course

    def engage_move(self, pos, foe, kinds, zone, now, radius, height, energy, hp_fraction, hunters):
        d = distance(pos, foe.pos)
        want = self.desired_range(kinds, foe, energy, sum(1 for c in hunters if c.dist < 145), self.light_range)
        if now >= self.strafe_until:
            self.strafe_sign = -self.strafe_sign if self.rng.random() < 0.8 else self.strafe_sign
            self.strafe_until = now + self.rng.uniform(STRAFE_MIN_S, STRAFE_MAX_S)
        to_me = bearing(foe.pos, pos)
        radial = limit((d - want) / 12.0, -1.0, 1.0)           # >0: too far, close in
        if foe.charging and foe.aim is not None and d > 25 and abs(angle(foe.aim[0] - bearing(foe.pos, pos))) < 0.2:
            # A laser is charging on us: step sideways at full speed, no radial drift.
            if not self.dodging:
                self.dodging = True
                self.strafe_until = now + self.rng.uniform(0.5, 0.9)
            radial = 0.0
        else:
            self.dodging = False
        # Move tangentially around the foe, plus a radial correction toward the wanted range.
        tangent = to_me + self.strafe_sign * math.pi / 2
        mx = math.cos(tangent) * (1 - abs(radial) * 0.6) - math.cos(to_me) * radial
        my = math.sin(tangent) * (1 - abs(radial) * 0.6) - math.sin(to_me) * radial
        course = math.atan2(my, mx)
        # Do not strafe out of the zone.
        ahead = (pos[0] + 12 * math.cos(course), pos[1] + 12 * math.sin(course))
        if zone.gap(ahead, 3) < 2:
            self.strafe_sign = -self.strafe_sign
            course = bearing(pos, zone.next_center)
        free = self.free_dir(pos, course, radius, height)
        if abs(angle(free - course)) > 1.2 and now >= self.strafe_until - 0.25:
            self.strafe_sign = -self.strafe_sign
            self.strafe_until = now + self.rng.uniform(0.35, 0.9)
        if "lightning" in kinds:
            boost = energy > 65 and d > want + 25          # energy is for arcs
        else:
            boost = energy > 35 and d < 100
        boost = boost or (self.dodging and energy > 15)
        return [math.cos(free), math.sin(free)], boost

    # ---------------------------------------------------------------------- act
    def act(self, obs):
        if PLAY_MODE != "practice":
            return super().act(obs)
        try:
            return self.duel_act(obs)
        except (ArithmeticError, LookupError, TypeError, ValueError, AttributeError) as error:
            mf.log(f"duel policy error, using the survive-first policy this tick: {error!r}")
            return super().act(obs)

    def duel_act(self, obs):
        begin = time.perf_counter()
        until = begin + eb.PLAN_BUDGET_S
        obs = obj(obs)
        me = obj(obs.get("self"))
        zone_obs = obj(obs.get("zone"))
        action = {}
        pos = vec(me.get("pos"), 3)
        offer = seq(obj(obs.get("offer")).get("choices"))[:3]
        if offer:
            def rank(i):
                ident = obj(offer[i]).get("id")
                return DUEL_UPGRADES.get(ident, 0) if isinstance(ident, str) else 0
            action["pick"] = max(range(len(offer)), key=rank)
        if pos is None:
            return action
        now = number(obs.get("t"), number(obs.get("tick")) * self.physics_dt)
        velocity = vec(me.get("vel"), 3) or ZERO
        actual = vec(me.get("aim"), 2) or (0.0, 0.0)
        stats = obj(me.get("stats"))
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        height = limit(self.phys("height", 9, stats), 1, 80)
        eye = limit(self.phys("eye_height", 8, stats), 1, 80)
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        hp = max(0, number(me.get("hp"), 1400))
        fraction = limit(hp / max(1, number(me.get("max_hp"), 1400)), 0, 1)
        self.hp_share = fraction
        energy = limit(number(me.get("energy"), 0), 0, 1000)
        grounded = me.get("grounded") is not False
        cubes = limit(number(me.get("cubes")), 0, 100)
        center = vec(zone_obs.get("center"), 2) or pos[:2]
        size = limit(number(zone_obs.get("radius"), 560), 0, 2000)
        zone = Zone(center, size, vec(zone_obs.get("next_center"), 2) or center,
                    limit(number(zone_obs.get("next_radius"), size), 0, size),
                    number(zone_obs.get("shrink_start"), now), number(zone_obs.get("shrink_end"), now + 99), now,
                    max(0, number(zone_obs.get("dps"))))
        goal, urgent = zone.anchor(pos, walk)
        gap = zone.gap(pos)
        in_zone = me.get("in_zone")
        if not isinstance(in_zone, bool):
            in_zone = gap >= 0
        terminal_burn = False
        if not in_zone:
            if zone.next_radius == 0 and zone.dps > 0:
                pace = limit(self.phys("boost_speed", 19.5, stats), walk, 90)
                survival = min(hp / zone.dps, max(0, self.match_end - now))
                terminal_burn = (-gap > pace * survival or (zone.radius == 0 and distance(pos, center) < 1e-6))
            if terminal_burn:
                goal, urgent = pos[:2], False
            elif not urgent:
                goal, urgent = center, True
        self.remember(obs, now)
        contacts = self.contacts(obs, pos, eye)
        self.track(contacts)
        for c in contacts:
            if c.kind == "mech":
                self.last_seen[c.id] = (now, c.pos)
        for event in seq(obs.get("events"))[:40]:
            event = obj(event)
            if event.get("type") == "kill":
                victim = number(event.get("target"), None)
                seen = self.last_seen.get(victim)
                if seen is not None:
                    self.kill_spot = (now, seen[1])
        self.update_hunt_point(obs, pos, now)
        items = seq(me.get("weapons"))
        weapons = [obj(items[i]) if i < len(items) else {} for i in range(2)]
        kinds = {w.get("kind") for w in weapons if w.get("kind") in KNOWN_WEAPONS}
        mechs = [c for c in contacts if c.kind == "mech"]
        if self.guarded:
            mechs = [c for c in mechs if self.engaging_us(c, pos)]
        hunters = [c for c in mechs if c.dist < 170]
        visible = [c for c in hunters if c.clear]
        hazards = self.nearby_shells(obs, pos, velocity, height)
        just_hit = now - self.last_damage < eb.HIT_MEMORY_S

        foe = None
        if hunters:
            def foe_key(c):
                # The leader's choice: near, low health, few cubes; stay on the current target;
                # with lightning, prefer laser carriers (lightning shorts their charge).
                hp = c.hp if math.isfinite(c.hp) else 1400.0
                score = c.dist + hp * 0.10 + 200 * (c.scale - 1)   # cubes x 10 (scale = 1 + 0.05 x cubes)
                if c.id == self.last_fire_target:
                    score -= 45
                if "lightning" in kinds and "laser" in c.armed:
                    score -= 30
                return score
            foe = min(hunters, key=foe_key)
        foe_share = (foe.hp / foe.max_hp) if foe is not None and math.isfinite(foe.hp) else 1.0

        # Healing is an explicit break from combat (the leader's rule): below 43%, not hurt for
        # 1 s, and no foe within 125 m; it ends above 83% or when anyone comes within 65 m.
        if self.healing and (fraction > HEAL_UNTIL or any(c.dist < 65 for c in mechs)):
            self.healing = False
        if fraction < HEAL_BELOW and now - self.last_damage > 1 and (foe is None or foe.dist > 125):
            self.healing = True
        retreating = False
        crowd = sum(1 for c in hunters if c.dist < 145)
        lw = next((w for w in weapons if w.get("kind") == "lightning"), None)
        self.light_range = number(obj(lw.get("stats")).get("range"), 45) if lw else 45.0

        move = None
        boost = False
        self.mode = "roam"
        if self.arena is not None:
            goal = self.arena.inset(goal, radius + 0.4)
        if not urgent and self.healing and not terminal_burn:
            self.mode = "heal"
            near = min(mechs, key=lambda c: c.dist) if mechs else None
            goal = zone.next_center
            if near is not None and time.perf_counter() < until:
                cover = self.shelter_point(pos, zone, contacts, bearing(pos, near.pos), radius, height, now,
                                           min(until, begin + SHELTER_SLICE_S), False)
                if cover is not None:
                    goal = cover
            drop = self.drop_goal(obs, pos, zone, walk)
            if drop is not None:
                goal = drop
        elif not urgent and foe is not None and not retreating and not terminal_burn:
            self.mode = "duel"
            move, boost = self.engage_move(pos, foe, kinds, zone, now, radius, height, energy, fraction, hunters)
            res = self.resource_goal(obs, pos, zone, hunters, kinds, weapons) if crowd < 3 else None
            if res is not None:
                # Commit to cubes and a better weapon mid-fight, still aiming at the foe.
                self.mode = "duel-cube"
                c = bearing(pos, res)
                move = [math.cos(c), math.sin(c)]
                boost = energy > 30
            if not foe.clear and foe.dist > 30:
                # Close in along a route rather than strafing into a wall.
                waypoint = self.route(pos, foe.pos[:2], zone, radius, height, now < self.stuck_until,
                                      min(until, time.perf_counter() + eb.ROUTE_SLICE_S))
                c = bearing(pos, waypoint)
                move = [math.cos(c), math.sin(c)]
        elif not urgent and retreating and foe is not None and not terminal_burn:
            self.mode = "retreat"
            direction = bearing(pos, foe.pos)
            cover = None
            if time.perf_counter() < until:
                cover = self.shelter_point(pos, zone, contacts, direction, radius, height, now,
                                           min(until, begin + SHELTER_SLICE_S), False)
            if cover is not None:
                goal = cover
            else:
                away = bearing(foe.pos, pos)
                goal = (pos[0] + 25 * math.cos(away), pos[1] + 25 * math.sin(away))
                if zone.gap(goal, 4) < 2:
                    goal = zone.next_center
            boost = energy > 20
        elif not urgent and not terminal_burn:
            saved = eb.WEAPON_RANK, eb.WEAPON_DETOUR_M
            eb.WEAPON_RANK = DUEL_WEAPON_RANK   # one ranking for walking to loot and swapping at our feet
            if not ({"laser", "lightning"} & kinds):
                eb.WEAPON_DETOUR_M = FIRST_WEAPON_DETOUR_M
            elif "lightning" not in kinds:
                eb.WEAPON_DETOUR_M = 0.0  # trading up to lightning is handled by resource_goal
            try:
                pickup = self.loot_goal(obs, pos, zone, contacts, weapons, fraction, cubes, True, urgent, action)
            finally:
                eb.WEAPON_RANK, eb.WEAPON_DETOUR_M = saved
            self.keep_lightning(obs, weapons, action)
            cube = self.cube_goal(obs, pos, zone)
            if self.kill_spot is not None and (now - self.kill_spot[0] > 30 or distance(pos, self.kill_spot[1]) < 5):
                self.kill_spot = None
            drop = self.drop_goal(obs, pos, zone, walk)
            res = self.resource_goal(obs, pos, zone, hunters, kinds, weapons)
            if cube is not None:
                goal = cube
                self.mode = "cube"
            elif res is not None:
                goal = res
                self.mode = "resource"
            elif drop is not None:
                goal = drop
                self.mode = "drop"
            elif pickup is not None:
                goal = pickup
                self.mode = "loot"
            elif self.kill_spot is not None and zone.gap(self.kill_spot[1], 5) > 3:
                goal = self.kill_spot[1][:2]
                self.mode = "spoils"
            elif self.hunt_point is not None and not self.guarded and fraction > REPAIR_TO and zone.gap(self.hunt_point[1], 5) > 3:
                goal = self.hunt_point[1][:2]
                self.mode = "hunt"
            else:
                farm = self.farm_goal(obs, pos, contacts, zone) if fraction >= FARM_HP else None
                if farm is not None:
                    goal = farm
                    self.mode = "farm"
                elif distance(pos, zone.next_center) > zone.next_radius * 0.5:
                    goal = zone.next_center
        self.better_weapon(obs, pos, weapons, action)

        if move is None:
            waypoint = self.route(pos, goal, zone, radius, height, now < self.stuck_until,
                                  min(until, time.perf_counter() + eb.ROUTE_SLICE_S))
            evade = bool(hazards) or just_hit or bool(visible)
            mv = self.movement(pos, velocity, waypoint, zone, urgent, evade, hunters, hazards,
                               self.damage_bearing if just_hit else None, stats, grounded, energy, now,
                               min(until, time.perf_counter() + STEER_SLICE_S), in_zone, terminal_burn, None)
            action.update(mv)
            if boost and energy > 20:
                action["boost"] = True
            if (urgent or terminal_burn) and visible and not hazards and zone.radius > eb.DEATH_CIRCLE_M:
                # Moving to the zone under fire: weave a little so the lead misses.
                m = action.get("move") or [0.0, 0.0]
                if math.hypot(*m) > 0.5:
                    if now >= self.strafe_until:
                        self.strafe_sign = -self.strafe_sign
                        self.strafe_until = now + self.rng.uniform(0.4, 1.0)
                    c = math.atan2(m[1], m[0]) + 0.45 * self.strafe_sign
                    action["move"] = [math.cos(c), math.sin(c)]
        else:
            if hazards:
                mv = self.movement(pos, velocity, (pos[0] + move[0] * 10, pos[1] + move[1] * 10), zone, False, True,
                                   hunters, hazards, None, stats, grounded, energy, now,
                                   min(until, time.perf_counter() + STEER_SLICE_S), in_zone, False, None)
                action.update(mv)
            else:
                action["move"] = move
                action["boost"] = bool(boost)

        # Aim: at the foe, else the last damage, else where we go.
        if foe is not None:
            direction = bearing(pos, foe.pos)
        elif just_hit and self.damage_bearing is not None:
            direction = self.damage_bearing
        elif now - self.last_sound < eb.SOUND_MEMORY_S and self.sound_bearing is not None:
            direction = self.sound_bearing
        else:
            m = action.get("move") or [0.0, 0.0]
            direction = math.atan2(m[1], m[0]) if math.hypot(*m) > 0.2 else angle(self.scout_yaw + now * eb.SCAN_RATE)
            # Sweep a little either side of the walking line so hunters behind are seen sooner.
            direction = angle(direction + 0.9 * math.sin(now * 1.3))
        action["aim"] = [direction, 0.0]
        if self.mode == "heal" and (foe is None or foe.dist > 85):
            action["fire"] = [False, False]   # dealing damage restarts the repair delay
            return action
        if time.perf_counter() < until + 0.002:
            boosting = action.pop("boost", False)
            self.combat(obs, pos, weapons, actual, stats, contacts, True, urgent, False, energy, 1.0, zone,
                        action, until + 0.002, terminal_burn, False, bool(hazards))
            charging = any(f and w.get("kind") == "laser" for f, w in zip(action.get("fire", ()), weapons))
            action["boost"] = bool(boosting) and not charging
        return action

    def cube_goal(self, obs, pos, zone, reach=140.0):
        best, goal = math.inf, None
        for item in seq(obs.get("cubes"))[:40]:
            p = vec(obj(item).get("pos"), 3)
            if p is None or abs(p[2] - pos[2]) > 10 or zone.gap(p, 6) < 3:
                continue
            d = distance(pos, p)
            if d < reach and d < best:
                best, goal = d, p[:2]
        return goal

    def update_hunt_point(self, obs, pos, now):
        if self.hunt_point is not None and (now - self.hunt_point[0] > 12 or distance(pos, self.hunt_point[1]) < 8):
            self.hunt_point = None
        recent = [v for v in self.last_seen.values() if now - v[0] < 15]
        if recent:
            t, p = max(recent, key=lambda v: v[0])
            if now - t > 0.5:
                self.hunt_point = (t, p)
                return
        if now - self.last_damage < 2 and self.damage_bearing is not None:
            b = self.damage_bearing
            self.hunt_point = (now, (pos[0] + 60 * math.cos(b), pos[1] + 60 * math.sin(b), pos[2]))
            return
        for sound in seq(obs.get("sounds"))[:40]:
            sound = obj(sound)
            if sound.get("kind") not in ("gun", "lightning", "laser", "mortar", "step", "boost"):
                continue
            b = number(sound.get("bearing"), None)
            if b is None:
                continue
            reach = {"near": 40, "mid": 100}.get(sound.get("dist"), 180)
            self.hunt_point = (now, (pos[0] + reach * math.cos(b), pos[1] + reach * math.sin(b), pos[2]))
            return

    def resource_goal(self, obs, pos, zone, hunters, kinds, weapons):
        """Cubes within 90 m and wanted weapons, priced by distance plus danger from mechs near
        them (the leader's costs); taken when the cost is under 45."""
        near = [c for c in hunters if c.dist < 145]
        best, goal = 45.0, None
        for item in seq(obs.get("cubes"))[:40]:
            p = vec(obj(item).get("pos"), 3)
            if p is None or abs(p[2] - pos[2]) > 5 or zone.gap(p, 6) < 3:
                continue
            d = distance(pos, p)
            if d > 90:
                continue
            danger = sum(max(0.0, 60 - distance(c.pos, p)) for c in near)
            cost = d * 0.35 + danger * 0.8
            if cost < best:
                best, goal = cost, p[:2]
        empty = any(not w.get("kind") for w in weapons)
        if empty or "lightning" not in kinds:
            weights = {"lightning": 0.45, "laser": 0.85}
            for item in seq(obs.get("pickups"))[:40]:
                item = obj(item)
                p, kind = vec(item.get("pos"), 3), item.get("kind")
                if p is None or kind not in weights or kind in kinds or abs(p[2] - pos[2]) > 5:
                    continue
                if not empty and kind != "lightning":
                    continue
                d = distance(pos, p)
                if d > (135 if empty else 70) or zone.gap(p, 6) < 3:
                    continue
                danger = sum(max(0.0, 55 - distance(c.pos, p)) for c in near)
                cost = d * weights[kind] + danger
                if cost < best:
                    best, goal = cost, p[:2]
        return goal

    def drop_goal(self, obs, pos, zone, walk):
        """A supply drop nobody else is capturing, reachable about when it lands: 3 cubes,
        full health and energy for standing in its ring alone."""
        me = number(obj(obs.get("self")).get("id"), self.slot)
        best, goal = math.inf, None
        for item in seq(obs.get("drops"))[:8]:
            item = obj(item)
            p = vec(item.get("pos"), 3)
            if p is None:
                continue
            holder = item.get("holder")
            if holder is not None and number(holder, -1) != me:
                continue
            d = distance(pos, p)
            if d > 220 or number(item.get("lands_in"), 0) > d / max(walk, 1) + 3:
                continue
            if zone.gap(p, 15) < 4:
                continue
            ring = number(item.get("radius"), 8)
            if d < best:
                best, goal = d, (pos[:2] if d < ring - 3 else p[:2])
        return goal

    def farm_goal(self, obs, pos, contacts, zone):
        best, goal = math.inf, None
        for c in contacts:
            if c.kind == "npc" and c.dist < NPC_FARM_M and zone.gap(c.pos, 6) > 5:
                score = c.dist * 0.8
                if score < best:
                    best, goal = score, c.pos[:2]
        for item in seq(obs.get("crates"))[:36]:
            item = obj(item)
            p = vec(item.get("pos"), 3)
            if p is None or abs(p[2] - pos[2]) > 12 or zone.gap(p, 6) < 5:
                continue
            d = distance(pos, p)
            if d < 150 and d < best:
                best, goal = d, p[:2]
        if goal is not None and distance(pos, goal) < 25:
            return None  # close enough to shoot it from here
        return goal

    def keep_lightning(self, obs, weapons, action):
        """Taking a laser while holding gun + lightning: drop the gun, keep the arc."""
        take = action.get("take")
        if take is None or "drop" not in action:
            return
        kinds = [w.get("kind") for w in weapons]
        kind = None
        for item in seq(obs.get("pickups"))[:40]:
            item = obj(item)
            if number(item.get("id"), None) == take:
                kind = item.get("kind")
        if "drop" in action and kinds[action["drop"]] == "gun":
            del action["take"], action["drop"]   # the gun is kept

    def better_weapon(self, obs, pos, weapons, action):
        """Swap the gun or a weak second weapon for a better one lying within reach."""
        if "take" in action:
            return
        held = [w.get("kind") for w in weapons]
        reach = limit(number(self.loot.get("pickup_radius"), 4), 1, 10)
        for item in seq(obs.get("pickups"))[:40]:
            item = obj(item)
            p, ident, kind = vec(item.get("pos"), 3), number(item.get("id"), None), item.get("kind")
            if p is None or ident is None or not isinstance(kind, str) or kind in held or kind not in SECOND_RANK:
                continue
            if distance(pos, p) > reach - 0.3 or abs(p[2] - pos[2]) > 3.8:
                continue
            for slot, w in enumerate(weapons):
                k = w.get("kind")
                if not k:
                    action["take"] = ident
                    return
            for slot, w in enumerate(weapons):
                k = w.get("kind")
                if isinstance(k, str) and k in SECOND_RANK and SECOND_RANK[kind] > SECOND_RANK[k] and number(w.get("charge")) <= 0:
                    action["take"], action["drop"] = ident, slot
                    return


def make_bot(hello):
    return DuelBot(hello) if PLAY_MODE == "practice" else Bot(hello)


if __name__ == "__main__":
    mf.run(make_bot)
