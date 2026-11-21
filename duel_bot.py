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

DUEL_UPGRADES = {
    "plating": 100, "gun_mag": 97, "armor": 96, "gun_damage": 92, "lightning_efficiency": 89,
    "laser_damage": 88, "gun_rate": 86, "nanites": 84, "laser_charge": 82, "reactor": 72,
    "capacitor": 70, "gyros": 66, "gun_velocity": 64, "lightning_range": 62, "servos": 60,
    "lightning_chain": 50, "jets": 48, "sensors": 46, "mortar_reload": 30, "mortar_velocity": 28,
    "mortar_splash": 26, "laser_pierce": 20,
}
KNOWN_WEAPONS = ("gun", "mortar", "laser", "lightning")
SECOND_RANK = {"laser": 3, "lightning": 2}   # laser first; never pick up a mortar (laser cook-off)


class _Ranks(dict):
    """Weapon ranks for the shared loot code: .get() hides the mortar so it is never taken."""
    def get(self, key, default=None):
        return None if key == "mortar" else super().get(key, default)


DUEL_WEAPON_RANK = _Ranks({"gun": 0, "mortar": -1, "lightning": 2, "laser": 3})
FIRST_WEAPON_DETOUR_M = 160.0   # walk this far for a first laser or lightning
LASER_DETOUR_M = 90.0           # and this far to add a laser
# These three switches affect only the guarded practice instance in royale.py.
# The unguarded DuelBot used by Selective's error fallback retains its old policy.
PRACTICE_FOCUS_COMMIT = False
PRACTICE_RANGE_DISCIPLINE = False
PRACTICE_FIRE_CYCLE = False
PRACTICE_PLAN_S = 0.008
FOCUS_SWITCH_MARGIN = 32.0
FOCUS_BLOCKED_S = 0.6
FINISH_HP_SHARE = 0.30
FINISH_OWN_SHARE = 0.55
FINISH_MAX_CROWD = 2
LETHAL_DAMAGE_FACTOR = 0.70  # conservative estimate; no rear/cook-off/cube bonus
LASER_RANGE_M = 110.0
REPAIR_TO = 0.85                # heal to this share before hunting the next one
VEL_SMOOTH = 0.35          # weight of the newest velocity sample in the per-target average
RETREAT_FRACTION = 0.30    # break contact below this health share when the duel is going badly
NPC_FARM_M = 120.0
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
        self.dodging = False
        self.guarded = False   # opener: fight only mechs that attack or close on us
        self.last_seen = {}        # mech id -> (time, pos)
        self.kill_spot = None      # (time, pos) where a victim died
        self.hunt_point = None     # (time, pos) best guess of where a hunter is
        self.focus_id = None
        self.focus_blocked_at = None
        self.practice_foe = None
        self.practice_crowd = 0
        self.practice_weapons = ()
        self.practice_energy = 0.0
        self.practice_finish = False

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
        if self.guarded and PRACTICE_FOCUS_COMMIT and self.practice_foe is not None:
            return [(200.0, self.lead_contact(self.practice_foe))]
        targets = []
        farming_ok = self.hp_share >= 0.85
        mechs = [c for c in contacts if c.kind == "mech"]
        for c in contacts:
            if c.kind == "mech" and self.guarded and PRACTICE_FOCUS_COMMIT:
                continue  # No selected movement focus: do not open a different duel.
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
    def desired_range(self, kinds, foe):
        if self.guarded and PRACTICE_RANGE_DISCIPLINE:
            return self.practice_range(kinds, foe)
        theirs = {k for k in foe.armed if k in KNOWN_WEAPONS}
        if "lightning" in kinds:
            r = 26.0
        elif "laser" in kinds:
            r = LASER_RANGE_M
        elif "mortar" in kinds:
            r = 60.0
        else:
            r = GUN_RANGE_M
        if "lightning" in theirs and "lightning" not in kinds:
            r = max(r, 55.0)          # stay out of their arc
        if "mortar" in theirs and "lightning" in kinds:
            r = min(r, 22.0)          # inside the shell's useful range
        if "laser" in theirs and "lightning" not in kinds:
            r = min(r, 30.0)
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
        want = self.desired_range(kinds, foe)
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
        boost = (energy > 45 and (d > want + 25 or (foe.clear and foe.dist < 90 and "lightning" not in kinds))
                 or self.dodging and energy > 15)
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
        active = self.guarded and (PRACTICE_FOCUS_COMMIT or PRACTICE_RANGE_DISCIPLINE or PRACTICE_FIRE_CYCLE)
        until = begin + (min(eb.PLAN_BUDGET_S, PRACTICE_PLAN_S) if active else eb.PLAN_BUDGET_S)
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
                share = c.hp / c.max_hp if math.isfinite(c.hp) else 1.0
                return share * 120 + c.dist * 0.5 - (40 if c.clear else 0) - (25 if c.attacker else 0)
            foe = min(hunters, key=foe_key)
        if active:
            if PRACTICE_FOCUS_COMMIT:
                foe = self.choose_focus(mechs, now)
            self.practice_foe = foe
            if PRACTICE_RANGE_DISCIPLINE:
                self.practice_weapons, self.practice_energy = weapons, energy
                # Count all reported living mechs, not only the eight contact candidates.
                nearby = {number(obj(e).get("id"), -1) for e in seq(obs.get("mechs"))[:48]
                          if obj(e).get("kind") == "mech" and number(obj(e).get("hp"), 1) > 0
                          and (p := vec(obj(e).get("pos"), 3)) is not None and distance(pos, p) < 180}
                nearby.update(i for i in self.hits if 0 <= i < 16 and i != self.slot)
                nearby.discard(self.slot)
                self.practice_crowd = len(nearby)
                self.practice_finish = bool(foe and foe.clear and math.isfinite(foe.hp)
                    and foe.hp <= foe.max_hp * FINISH_HP_SHARE and fraction >= FINISH_OWN_SHARE
                    and self.practice_crowd <= FINISH_MAX_CROWD and foe.dist <= 130
                    and self.ready_delay(foe) <= 0.3)
        foe_share = (foe.hp / foe.max_hp) if foe is not None and math.isfinite(foe.hp) else 1.0

        # Retreat to repair when losing badly and the foe is not nearly dead.
        if foe is not None and fraction < RETREAT_FRACTION and foe_share > fraction + 0.15 and len(visible) >= 1:
            self.retreat_until = now + 4.0
        if foe is not None and foe_share < 0.25 and fraction > 0.12:
            self.retreat_until = -math.inf   # finish it
        retreating = now < self.retreat_until or (len(visible) >= 3 and fraction < 0.6)

        move = None
        boost = False
        self.mode = "roam"
        if self.arena is not None:
            goal = self.arena.inset(goal, radius + 0.4)
        if not urgent and foe is not None and not retreating and not terminal_burn:
            self.mode = "duel"
            move, boost = self.engage_move(pos, foe, kinds, zone, now, radius, height, energy, fraction, hunters)
            cube = self.cube_goal(obs, pos, zone, FIGHT_CUBE_M) if fraction > RETREAT_FRACTION else None
            if cube is not None and not (self.guarded and PRACTICE_RANGE_DISCIPLINE and self.practice_finish):
                # Kill cubes heal and add damage: walk onto them mid-fight, still aiming at the foe.
                self.mode = "duel-cube"
                c = bearing(pos, cube)
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
            elif "laser" not in kinds:
                eb.WEAPON_DETOUR_M = LASER_DETOUR_M
            try:
                pickup = self.loot_goal(obs, pos, zone, contacts, weapons, fraction, cubes, True, urgent, action)
            finally:
                eb.WEAPON_RANK, eb.WEAPON_DETOUR_M = saved
            self.keep_lightning(obs, weapons, action)
            cube = self.cube_goal(obs, pos, zone)
            if self.kill_spot is not None and (now - self.kill_spot[0] > 30 or distance(pos, self.kill_spot[1]) < 5):
                self.kill_spot = None
            if cube is not None:
                goal = cube
                self.mode = "cube"
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
                farm = self.farm_goal(obs, pos, contacts, zone)
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
        if time.perf_counter() < until + 0.002:
            boosting = action.pop("boost", False)
            self.combat(obs, pos, weapons, actual, stats, contacts, True, urgent, False, energy, 1.0, zone,
                        action, until + 0.002, terminal_burn, False, bool(hazards))
            charging = any(f and w.get("kind") == "laser" for f, w in zip(action.get("fire", ()), weapons))
            action["boost"] = bool(boosting) and not charging
        return action

    def setting(self, weapon, key, default):
        return number(obj(weapon.get("stats")).get(key),
                      number(obj(self.weapon_config.get(weapon.get("kind"))).get(key), default))

    def ready_delay(self, foe):
        waits = []
        for w in self.practice_weapons:
            kind = w.get("kind")
            wait = max(0, number(w.get("cooldown")))
            if kind == "gun":
                reload = number(w.get("reload"))
                if number(w.get("ammo"), 0) <= 0 and reload <= 0:
                    reload = self.setting(w, "reload", 2.4)
                wait = max(wait, reload)
            elif kind == "laser":
                wait += max(0, self.setting(w, "charge", 0.75) - number(w.get("charge")))
            elif kind == "lightning":
                if foe.dist > self.setting(w, "range", 45) * 0.9 or self.practice_energy < 18:
                    continue
            else:
                continue
            waits.append(wait)
        return min(waits, default=math.inf)

    def choose_focus(self, mechs, now):
        candidates = [c for c in mechs if c.hp > 0 and c.dist <= (210 if c.id == self.focus_id or c.attacker else 170)]
        current = next((c for c in candidates if c.id == self.focus_id), None)
        if current is None or current.clear:
            self.focus_blocked_at = None
        elif self.focus_blocked_at is None:
            self.focus_blocked_at = now
        expired = self.focus_blocked_at is not None and now - self.focus_blocked_at >= FOCUS_BLOCKED_S
        if not candidates:
            self.focus_id = None
            return None
        def cost(c):
            health = c.hp if math.isfinite(c.hp) else c.max_hp
            return 0.09 * health + 0.45 * c.dist + (0 if c.clear else 55) - 18 * c.attacker
        best = min(candidates, key=lambda c: (cost(c), c.id))
        if current is not None and not expired:
            if cost(current) <= cost(best) + FOCUS_SWITCH_MARGIN:
                best = current
        if expired:
            clear = [c for c in candidates if c.clear]
            if clear:
                best = min(clear, key=lambda c: (cost(c), c.id))
        if best.id != self.focus_id:
            self.focus_blocked_at = None if best.clear else now
        self.focus_id = best.id
        return best

    def practice_range(self, kinds, foe):
        arc = next((w for w in self.practice_weapons if w.get("kind") == "lightning"), None)
        usable_arc = arc is not None and self.practice_energy >= max(18, 3 * self.setting(arc, "energy", 3))
        want = 26.0 if usable_arc else LASER_RANGE_M if "laser" in kinds else GUN_RANGE_M
        floor = 0.0
        if "lightning" in foe.armed and not usable_arc:
            floor = number(obj(self.weapon_config.get("lightning")).get("range"), 45) * 1.4
        if "mortar" in foe.armed and usable_arc:
            want = 22.0
        if self.practice_finish:
            # Close modestly only while healthy, ready, and not surrounded.
            want = min(want, max(45.0, foe.dist - 12.0))
        return max(floor, want)

    def charge_damage(self, weapon):
        full = max(0.05, self.setting(weapon, "charge", 0.75))
        part = limit(self.setting(weapon, "min_frac", 0.35), 0, 1)
        return self.setting(weapon, "damage", 315) * (part + (1 - part) *
            limit(number(weapon.get("charge")) / full, 0, 1)) * LETHAL_DAMAGE_FACTOR

    def combat(self, obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy, fraction, zone,
               action, until, terminal_burn, repairing, incoming):
        if not (self.guarded and PRACTICE_FIRE_CYCLE):
            return super().combat(obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy,
                                  fraction, zone, action, until, terminal_burn, repairing, incoming)
        fire = action["fire"] = [False, False]
        targets = self.target(obs, pos, contacts, fraction, zone, must_move, safe, terminal_burn, repairing, incoming)
        escaping = must_move or incoming or self.mode == "retreat"
        muzzle = self.phys("muzzle_height", 7, stats)
        bounds = self.phys("min_pitch", -0.7, stats), self.phys("max_pitch", 1.3, stats)
        velocity = vec(obj(obs.get("self")).get("vel"), 3) or ZERO
        base = tuple(p + v * self.physics_dt for p, v in zip(pos, velocity))
        selected = None
        for _, target in targets[:4]:
            plans = []
            for i, w in enumerate(weapons[:2]):
                if time.perf_counter() >= until:
                    break
                kind = w.get("kind")
                if kind not in KNOWN_WEAPONS:
                    continue
                charge = number(w.get("charge"))
                if kind == "gun" and (number(w.get("reload")) > 0 or number(w.get("ammo"), 0) <= 0):
                    continue
                if kind == "lightning" and energy < max(18, self.setting(w, "energy", 3)):
                    continue
                if kind == "laser" and escaping and charge <= 0:
                    continue
                plan = self.aim_for(w, target, base, muzzle, bounds)
                if plan is None:
                    continue
                cooldown = max(0, number(w.get("cooldown")))
                rank = {"gun": 12, "laser": 26, "lightning": 28, "mortar": 20}[kind] - 60 * cooldown
                if charge > 0:
                    full = max(0.05, self.setting(w, "charge", 0.75))
                    turn = abs(angle(plan[0] - actual[0])) / max(0.1, self.phys("turn_rate", 4, stats))
                    turn = max(turn, abs(plan[1] - actual[1]) / max(0.1, self.phys("pitch_rate", 3, stats)))
                    lethal = math.isfinite(target.hp) and target.hp <= self.charge_damage(w)
                    # Use gun lead early in a charge; reserve time to aim the release.
                    release_due = lethal or full - charge <= turn + 2 * self.dt
                    rank += 100 if release_due else -30
                elif kind == "gun" and math.isfinite(target.hp) and target.hp <= self.setting(w, "damage", 45) * LETHAL_DAMAGE_FACTOR:
                    rank += 40
                plans.append((rank, i, plan))
            if plans:
                selected = target, plans
                break
        self.last_fire_target = None
        if selected is not None:
            target, plans = selected
            _, chosen, main = max(plans, key=lambda item: (item[0], -item[1]))
            action["aim"] = list(main[:2])
            self.last_fire_target = target.id
            for _, i, plan in plans:
                w, kind = weapons[i], weapons[i]["kind"]
                yaw, pitch, width, vertical = plan
                # Both the current and commanded torso angles must support this shot.
                aligned = (abs(angle(yaw - actual[0])) <= width
                    and abs(angle(yaw - main[0])) <= width
                    and (kind == "lightning" or (abs(pitch - actual[1]) <= vertical
                         and abs(pitch - main[1]) <= vertical)))
                ready = number(w.get("cooldown")) <= self.dt + 1e-9
                if kind == "laser":
                    charge = number(w.get("charge"))
                    full = max(0.05, self.setting(w, "charge", 0.75))
                    minimum = max(0, self.setting(w, "min_charge", 0.15))
                    lethal = math.isfinite(target.hp) and target.hp <= self.charge_damage(w)
                    if charge > 0:
                        fire[i] = not (escaping or (aligned and charge >= minimum
                            and (charge >= full or lethal)))
                    elif chosen == i and ready and not escaping:
                        turn_window = min(0.8, max(0, self.phys("turn_rate", 4, stats)) * full * 0.5)
                        pitch_window = min(0.6, max(0, self.phys("pitch_rate", 3, stats)) * full * 0.5)
                        fire[i] = (abs(angle(yaw - actual[0])) <= turn_window
                                   and abs(pitch - actual[1]) <= pitch_window)
                elif ready and aligned:
                    fire[i] = True
        # Releasing an unusable charge restores speed; it may expend a beam into cover.
        for i, w in enumerate(weapons[:2]):
            if w.get("kind") == "gun" and not fire[i] and number(w.get("reload")) <= 0:
                ammo = number(w.get("ammo"), 0)
                if ammo <= 0 or (selected is None and not self.practice_foe
                                and ammo <= self.setting(w, "mag", 12) * eb.RELOAD_FRACTION):
                    action["reload"] = True

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
        if kind == "laser" and "lightning" in kinds and "gun" in kinds:
            action["drop"] = kinds.index("gun")

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
            if kind == "laser" and "lightning" in held and "gun" in held:
                action["take"], action["drop"] = ident, held.index("gun")
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
