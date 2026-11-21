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

PLAY_MODE = "practice"  # "practice" = duel-first (this file); "free-for-all" = survive-first example_bot.Bot

DUEL_UPGRADES = {
    "plating": 100, "armor": 96, "gun_damage": 92, "gun_rate": 90, "lightning_efficiency": 89,
    "laser_damage": 88, "nanites": 84, "laser_charge": 82, "gun_mag": 80, "reactor": 72,
    "capacitor": 70, "gyros": 66, "gun_velocity": 64, "lightning_range": 62, "servos": 60,
    "lightning_chain": 50, "jets": 48, "sensors": 46, "mortar_reload": 30, "mortar_velocity": 28,
    "mortar_splash": 26, "laser_pierce": 20,
}
KNOWN_WEAPONS = ("gun", "mortar", "laser", "lightning")
SECOND_RANK = {"lightning": 3, "laser": 2, "mortar": 1}
VEL_SMOOTH = 0.35          # weight of the newest velocity sample in the per-target average
RETREAT_FRACTION = 0.30    # break contact below this health share when the duel is going badly
NPC_FARM_M = 120.0
GUN_RANGE_M = 90.0          # preferred gun-only duel range (simulator: dodging needs flight time)
STRAFE_MIN_S = 0.3
STRAFE_MAX_S = 0.7
CRATE_FARM_M = 70.0


class DuelBot(Bot):
    def __init__(self, hello):
        super().__init__(hello)
        self.rng = random.Random(number(hello.get("seed"), 0))
        self.strafe_sign = 1 if self.rng.random() < 0.5 else -1
        self.strafe_until = 0.0
        self.vel_avg = {}
        self.seen_hp = {}
        self.retreat_until = -math.inf
        self.mode = "start"

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
        mechs = [c for c in contacts if c.kind == "mech"]
        for c in contacts:
            if c.kind == "mech":
                share = c.hp / c.max_hp if math.isfinite(c.hp) else 1.0
                rear = c.face_error > math.pi / 2
                merit = 120 + 60 * (1 - share) + 25 * c.attacker + 20 * rear - c.dist * 0.35
                merit += 12 * (c.id == self.last_fire_target) + (30 if c.clear else -40)
            else:
                if mechs and any(m.clear and m.dist < 150 for m in mechs):
                    continue
                if c.dist > NPC_FARM_M or terminal_burn:
                    continue
                merit = 40 + (350 - min(350, c.hp)) * 0.1 - c.dist * 0.3 + 30 * c.attacker
            targets.append((merit, self.lead_contact(c)))
        if not any(m.clear and m.dist < 150 for m in mechs) and not must_move and not terminal_burn:
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

    # ----------------------------------------------------------------- movement
    def desired_range(self, kinds, foe):
        theirs = {k for k in foe.armed if k in KNOWN_WEAPONS}
        if "lightning" in kinds:
            r = 26.0
        elif "laser" in kinds:
            r = 75.0
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
        boost = energy > 45 and (d > want + 25 or (foe.clear and foe.dist < 90 and "lightning" not in kinds))
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
        items = seq(me.get("weapons"))
        weapons = [obj(items[i]) if i < len(items) else {} for i in range(2)]
        kinds = {w.get("kind") for w in weapons if w.get("kind") in KNOWN_WEAPONS}
        mechs = [c for c in contacts if c.kind == "mech"]
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
                                           min(until, begin + 0.0029), False)
            if cover is not None:
                goal = cover
            else:
                away = bearing(foe.pos, pos)
                goal = (pos[0] + 25 * math.cos(away), pos[1] + 25 * math.sin(away))
                if zone.gap(goal, 4) < 2:
                    goal = zone.next_center
            boost = energy > 20
        elif not urgent and not terminal_burn:
            pickup = self.loot_goal(obs, pos, zone, contacts, weapons, fraction, cubes, True, urgent, action)
            if pickup is not None:
                goal = pickup
                self.mode = "loot"
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
                               min(until, time.perf_counter() + 0.0020), in_zone, terminal_burn, None)
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
                                   min(until, time.perf_counter() + 0.0020), in_zone, False, None)
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
