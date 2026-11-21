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
# Arm early (practice only, switched on by royale.PRACTICE_ARM through DuelBot.arm): while we hold
# only the gun, walk to a laser (else lightning) pickup seen this match when it is quiet.
ARM_DETOUR_M = 150.0        # straight-line reach to a remembered or visible pickup
ARM_CLEAR_M = 90.0          # no mech (seen or tracked) this close, else fight as before
ARM_QUIET_S = 4.0           # and nothing has damaged us for this long
ARM_BOOST_ENERGY = 35.0     # boost toward it above this energy (keeps a jet / dodge reserve)
ARM_STALL_S = 6.0           # no 2 m of progress for this long while detouring: give that pickup up
ARM_FORGET_M = 35.0         # in plain sight this close and not listed: someone took it
ARM_CUBE_FIRST_M = 20.0     # a cube this close is collected on the way
ARM_LASER_EDGE_M = 60.0     # a laser wins unless a lightning is this much closer
# Practice fight discipline (P2). Each switch acts only on the practice instance (DuelBot.squad).
PR_RETREAT2 = True          # retreat when two or three hunters are on us, or the damage race is lost
PR_KEEP_LASER_RANGE = True  # holding a laser: keep laser range against laser hunters (no 30 m rush)
PR_LL_RANGE = True          # laser + lightning: close to arc range only when healthy and the foe is weaker
PR_DUCK = True              # gun reloading and nothing else ready: step behind cover within 18 m
PR_LASER_LOS = True         # start a laser charge only on a mech in sight; never dump a charge into a wall
PR_BOOST_STRAFE = False     # boost through fights with 70/30 energy hysteresis, charging or not
PR_UPGRADES = True          # laser_charge / laser_damage near the top of the upgrade order
PR_NEAR_M = 160.0           # hunters in sight this close count as "on us"
PR_TWO_HP = 0.55            # two on us and below this share: retreat
PR_THREE_HP = 0.80          # three on us and below this share: retreat
PR_LOW_HP = 0.35            # below this share against a foe at least 0.10 healthier: retreat
PR_RACE_DPS = 60.0          # damage race: taking more than this per second (4 s window) ...
PR_RACE_RATIO = 0.8         # ... and our time to die under 0.8 x their time to die ...
PR_RACE_HP = 0.75           # ... while below this share
PR_LL_HP = 0.60             # laser + lightning: arc range only above this share
PR_DUCK_M = 18.0            # cover must be this close to duck
PR_DUCK_READY_S = 0.3       # another weapon this close to ready: keep fighting instead of ducking
PR_BOOST_ON, PR_BOOST_OFF = 70.0, 30.0
PR_UPGRADE_RANK = dict(DUEL_UPGRADES, laser_charge=99, laser_damage=95)


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
        self.arm = False           # arm-early detour (practice only; set by royale.PRACTICE_ARM)
        self.arm_seen = {}         # pickup id -> (kind, pos) for lasers and lightning seen this match
        self.arm_banned = set()    # pickups given up on
        self.arm_progress = None   # (id, best distance, time of last progress, last arm tick)
        self.squad = False         # P2 practice discipline (set by royale for the practice policy only)
        self.dmg_in, self.dmg_out = [], []   # (time, amount) over the last 4 s
        self.boost_latch = False
        self.laser_plan = False
        self.my_hp = 1400.0

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
        farming_ok = self.hp_share >= 0.85
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
    def desired_range(self, kinds, foe):
        theirs = {k for k in foe.armed if k in KNOWN_WEAPONS}
        weaker = math.isfinite(foe.hp) and foe.hp < self.my_hp
        if "lightning" in kinds and not (self.squad and PR_LL_RANGE and "laser" in kinds
                                         and not (self.hp_share > PR_LL_HP and weaker)):
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
        if "laser" in theirs and "lightning" not in kinds and not (self.squad and PR_KEEP_LASER_RANGE and "laser" in kinds):
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
        if self.squad and PR_BOOST_STRAFE:
            if energy > PR_BOOST_ON:
                self.boost_latch = True
            elif energy < PR_BOOST_OFF:
                self.boost_latch = False
            boost = self.boost_latch
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
                table = PR_UPGRADE_RANK if self.squad and PR_UPGRADES else DUEL_UPGRADES
                return table.get(ident, 0) if isinstance(ident, str) else 0
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
        self.my_hp = hp
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
            if self.squad and PR_RETREAT2:
                amount = limit(number(event.get("amount")), 0, 5000)
                if event.get("type") == "damaged" and event.get("weapon") != "zone" and len(self.dmg_in) < 200:
                    self.dmg_in.append((now, amount))
                elif event.get("type") == "hit" and 0 <= number(event.get("target"), -1) < 100 and len(self.dmg_out) < 200:
                    self.dmg_out.append((now, amount))
        self.dmg_in = [e for e in self.dmg_in if now - e[0] <= 4.0]
        self.dmg_out = [e for e in self.dmg_out if now - e[0] <= 4.0]
        self.update_hunt_point(obs, pos, now)
        items = seq(me.get("weapons"))
        weapons = [obj(items[i]) if i < len(items) else {} for i in range(2)]
        kinds = {w.get("kind") for w in weapons if w.get("kind") in KNOWN_WEAPONS}
        if self.arm:
            self.arm_remember(obs, pos, eye)
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
        foe_share = (foe.hp / foe.max_hp) if foe is not None and math.isfinite(foe.hp) else 1.0

        # Retreat to repair when losing badly and the foe is not nearly dead.
        if foe is not None and fraction < RETREAT_FRACTION and foe_share > fraction + 0.15 and len(visible) >= 1:
            self.retreat_until = now + 4.0
        near = [c for c in visible if c.dist < PR_NEAR_M]
        if self.squad and PR_RETREAT2 and foe is not None:
            losing = ((len(near) >= 2 and fraction < PR_TWO_HP) or (len(near) >= 3 and fraction < PR_THREE_HP)
                      or (fraction < PR_LOW_HP and foe_share > fraction + 0.10 and visible))
            taken = sum(a for _, a in self.dmg_in) / 4.0
            dealt = sum(a for _, a in self.dmg_out) / 4.0
            if (taken > PR_RACE_DPS and fraction < PR_RACE_HP and math.isfinite(foe.hp)
                    and hp / taken < PR_RACE_RATIO * foe.hp / max(1.0, dealt)):
                losing = True
            if losing:
                self.retreat_until = max(self.retreat_until, now + 4.0)
        if foe is not None and foe_share < 0.25 and fraction > 0.12 and not (self.squad and PR_RETREAT2 and len(near) >= 3):
            self.retreat_until = -math.inf   # finish it
        retreating = now < self.retreat_until or (len(visible) >= 3 and fraction < 0.6)
        arm_goal = None
        if self.arm and not (kinds - {"gun"}) and not urgent and not retreating and not terminal_burn:
            arm_goal = self.arm_goal(pos, zone, contacts, walk, now)

        move = None
        boost = False
        self.mode = "roam"
        if self.arena is not None:
            goal = self.arena.inset(goal, radius + 0.4)
        if arm_goal is not None:
            # Arm early: take a laser or lightning before the next hunter arrives.
            self.mode = "arm"
            cube = self.cube_goal(obs, pos, zone, ARM_CUBE_FIRST_M)
            goal = cube if cube is not None else arm_goal
            boost = energy > ARM_BOOST_ENERGY and distance(pos, goal) > 12
        elif not urgent and foe is not None and not retreating and not terminal_burn:
            self.mode = "duel"
            move, boost = self.engage_move(pos, foe, kinds, zone, now, radius, height, energy, fraction, hunters)
            cube = self.cube_goal(obs, pos, zone, FIGHT_CUBE_M) if fraction > RETREAT_FRACTION else None
            if cube is not None:
                # Kill cubes heal and add damage: walk onto them mid-fight, still aiming at the foe.
                self.mode = "duel-cube"
                c = bearing(pos, cube)
                move = [math.cos(c), math.sin(c)]
                boost = energy > 30
            if self.squad and PR_DUCK and cube is None and self.should_duck(weapons, foe, energy):
                cover = None
                if time.perf_counter() < until:
                    cover = self.shelter_point(pos, zone, contacts, bearing(pos, foe.pos), radius, height, now,
                                               min(until, begin + SHELTER_SLICE_S), False)
                if cover is not None and distance(pos, cover) < PR_DUCK_M:
                    # Gun reloading and nothing else ready: out of sight until it is back.
                    self.mode = "duck"
                    goal, move, boost = cover, None, energy > 25
            if self.mode != "duck" and not foe.clear and foe.dist > 30:
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
            action["boost"] = bool(boosting) and (not charging or (self.squad and PR_BOOST_STRAFE and self.mode == "duel"))
        return action

    def aim_for(self, weapon, target, base, muzzle, pitch_bounds):
        # With arm-early on, the laser is kept for mechs: the gun (or the arc) takes drones and crates.
        if self.arm and target.kind != "mech" and weapon.get("kind") == "laser":
            return None
        if (self.squad and PR_LASER_LOS and weapon.get("kind") == "laser" and number(weapon.get("charge")) <= 0
                and not (target.kind == "mech" and target.clear)):
            return None    # a new charge only on a mech we can see
        plan = super().aim_for(weapon, target, base, muzzle, pitch_bounds)
        if plan is not None and weapon.get("kind") == "laser":
            self.laser_plan = True
        return plan

    def combat(self, obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy, fraction, zone,
               action, until, terminal_burn, repairing, incoming):
        self.laser_plan = False
        super().combat(obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy, fraction, zone,
                       action, until, terminal_burn, repairing, incoming)
        if self.squad and PR_LASER_LOS and not self.laser_plan and not must_move:
            # Sight lost mid-charge: keep holding (it fires by itself after hold_s) rather than
            # letting go into a wall; the target often steps back out.
            firing = action.get("fire")
            for i, weapon in enumerate(weapons):
                if weapon.get("kind") == "laser" and number(weapon.get("charge")) > 0 and isinstance(firing, list):
                    firing[i] = True

    def should_duck(self, weapons, foe, energy):
        """Gun reloading, nothing else ready, foe not on top of us."""
        if foe.dist <= 30:
            return False
        gun = next((w for w in weapons if w.get("kind") == "gun"), None)
        if gun is None:
            return False
        if not (number(gun.get("reload")) > 0.6 or number(gun.get("ammo"), 1) <= 0):
            return False
        for w in weapons:
            kind = w.get("kind")
            if kind == "laser" and number(w.get("cooldown")) < PR_DUCK_READY_S:
                return False
            if kind == "lightning" and number(w.get("cooldown")) < PR_DUCK_READY_S and energy > eb.BOOST_RESERVE:
                return False
        return True

    def arm_remember(self, obs, pos, eye):
        listed = set()
        for item in seq(obs.get("pickups"))[:40]:
            item = obj(item)
            p, ident, kind = vec(item.get("pos"), 3), number(item.get("id"), None), item.get("kind")
            if p is None or ident is None or ident < 0:
                continue
            listed.add(ident)
            if kind in SECOND_RANK and ident not in self.arm_banned and (ident in self.arm_seen or len(self.arm_seen) < 64):
                self.arm_seen[ident] = (kind, p)
        for ident, (kind, p) in list(self.arm_seen.items()):
            if ident in listed or distance(pos, p) > ARM_FORGET_M:
                continue
            if self.arena is None or self.arena.clear_ray(eb.raised(pos, eye), eb.raised(p, 0.6)):
                del self.arm_seen[ident]     # in plain sight and gone: someone took it
        for event in seq(obs.get("events"))[:40]:
            event = obj(event)
            if event.get("type") in ("took", "take_failed"):
                ident = number(event.get("id"), None)
                self.arm_seen.pop(ident, None)
                if event.get("type") == "take_failed":
                    self.arm_banned.add(ident)

    def arm_goal(self, pos, zone, contacts, walk, now):
        """Where to walk for a first laser (else lightning), or None when it is not quiet."""
        if now - self.last_damage < ARM_QUIET_S:
            return None
        rivals = [c.pos for c in contacts if c.kind == "mech"]
        if any(distance(pos, r) < ARM_CLEAR_M for r in rivals):
            return None
        best = None
        for ident, (kind, p) in self.arm_seen.items():
            if ident in self.arm_banned or abs(p[2] - pos[2]) > 4:
                continue
            d = distance(pos, p)
            if d > ARM_DETOUR_M or zone.gap(p, d / max(1.0, walk) + eb.LOOT_SAFE_S) < 4:
                continue
            if any(distance(r, p) < eb.LOOT_CONTEST_M for r in rivals):
                continue
            choice = (-d + (ARM_LASER_EDGE_M if kind == "laser" else 0.0), ident, d)
            if best is None or choice > best[0]:
                best = (choice, p)
        if best is None:
            self.arm_progress = None
            return None
        ident, d = best[0][1], best[0][2]
        prog = self.arm_progress
        if prog is None or prog[0] != ident or now - prog[3] > 1.0:
            prog = (ident, d, now, now)          # new target, or resumed after an interruption
        elif d < prog[1] - 2.0:
            prog = (ident, d, now, now)
        else:
            prog = (ident, prog[1], prog[2], now)
        if now - prog[2] > ARM_STALL_S:
            self.arm_banned.add(ident)           # no way there (roof, wall maze): stop trying
            self.arm_progress = None
            return None
        self.arm_progress = prog
        return best[1][:2]

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
