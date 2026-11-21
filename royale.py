






import mechfight as mf
import example_bot as eb
import duel_bot
import json
import math
import os
import select
import subprocess
import threading
import time
from collections import deque
from typing import NamedTuple

eb.PLAN_BUDGET_S = 0.010
eb.ROUTE_SLICE_S = 0.004
from example_bot import obj, seq, number, vec, distance, bearing, angle, limit, raised

SEED = 6                    
P_DRIVER = 4
P4_SALT = 0
P4_DEADLINE_MS = 30
FORCE_MODE = None           
GUARDED_OPENER = True       
PAUSE_MED_MS = 8.0
PAUSE_MIN_MS = 4.0
PAUSE_SHOW = False
USE_PAUSE = False
USE_E = True
E_WINDOW_S = 30.0
USE_R = False
USE_H2 = True
FFA_WEDGE = True
FFA_NOT_NEAREST = True
FFA_UNSEEN_OPEN = True
FFA_QUIET_WALK = True
FFA_PICKUP_TAPER = True
FFA_LASER_COVER = False
FFA_ARM_FAST = True
FFA_SIZE_UNCAP = True
FFA_DUEL_OPEN = True
FFA_NO_MORTAR = False
FFA_PLATING_FIRST = False
FFA_ESCAPE_LATCH = False

FFA_ARM_S = 30.0
FFA_ARM_HP = 1000
FFA_ESCAPE_HIT_S = 6.0
FFA_ESCAPE_HP = 1000
FFA_ESCAPE_LASER_M = 100.0
FFA_ESCAPE_LIGHTNING_M = 70.0
FFA_ESCAPE_QUIET_S = 5.0
FFA_ESCAPE_CLEAR_M = 120.0
FFA_SIGHT_MEMORY_S = 3.0
FFA_WEDGE_MARGIN = math.radians(10)
FFA_WEDGE_COST = 40.0
FFA_LASER_MULT = 1.5
FFA_HIDDEN_REWARD = 12.0
FFA_NEAREST_COST = 25.0
FFA_NEAREST_RATIO = 0.9
FFA_POSITION_RAYS = 24
FFA_STEERING_RAYS = 12
FFA_PICKUP_FULL_S = 3.0
FFA_PICKUP_EXPIRY_S = 10.0
FFA_PICKUP_NEAR_M = 4.0
FFA_PICKUP_MEMORY_RAYS = 12
FFA_LASER_TRAVEL_S = 1.5
FFA_LASER_HOLD_S = 3.0
FFA_LASER_COVER_RAYS = 24


def mech_attacker(event, slot):
    source = number(event.get("by"), -1)
    if (event.get("type") == "damaged" and event.get("weapon") not in ("zone", "npc")
            and 0 <= source < 16 and source == int(source) and source != slot
            and number(event.get("amount")) > 0):
        return source


def segment_distance_sq(pos, end, point):
    dx, dy = end[0] - pos[0], end[1] - pos[1]
    px, py = point[0] - pos[0], point[1] - pos[1]
    span = dx * dx + dy * dy
    along = limit((px * dx + py * dy) / span, 0, 1) if span else 0
    return (px - along * dx) ** 2 + (py - along * dy) ** 2


def distance_sq(a, b):
    dx, dy = a[0] - b[0], a[1] - b[1]
    return dx * dx + dy * dy


class Detector:
    def __init__(self, hello):
        self.slot = number(hello.get("slot"), -1)
        self.start_alive = None
        self.kills = 0
        self.beam_times = []
        self.seen_hp = {}
        self.latest_attacker = None
        self.ffa = False
        self.score = 0.0

    def other_hp_drop(self, obs, events):
        zone = obj(obs.get("zone"))
        center, radius = vec(zone.get("center"), 2), number(zone.get("radius"), 0)
        ours = {number(event.get("target"), None) for event in events if event.get("type") == "hit"}
        previous, self.seen_hp = self.seen_hp, {}
        for raw in seq(obs.get("mechs"))[:48]:
            entry = obj(raw)
            if entry.get("kind") != "mech":
                continue
            ident = number(entry.get("id"), None)
            hp = number(entry.get("hp"), None)
            if ident is None or ident == self.slot or hp is None:
                continue
            self.seen_hp[ident] = hp
            if ident in ours or ident not in previous or number(entry.get("cubes"), None) != 0:
                continue
            if abs(previous[ident] - hp - 45.0) <= 1e-6 and center is not None:
                point = vec(entry.get("pos"), 3)
                if point is not None and distance(point, center) <= radius:
                    return True
        return False

    def two_attackers(self, events, now):
        for event in events:
            source = mech_attacker(event, self.slot)
            if source is None:
                continue
            if self.latest_attacker is not None:
                other, when = self.latest_attacker
                if source != other and 0 <= now - when <= 20 + 1e-9:
                    return True
            self.latest_attacker = source, now
        return False

    def update(self, obs, now):
        if self.ffa:
            return True
        g_med, g_min = mf.pause_ms
        if USE_PAUSE and now >= 1.2 and g_med is not None and g_med > PAUSE_MED_MS and g_min > PAUSE_MIN_MS:
            self.ffa = True
            return True
        events = [obj(event) for event in seq(obs.get("events"))[:200]]
        self.kills += sum(event.get("type") == "kill" for event in events)
        alive = number(obs.get("alive"), None)
        dps = number(obj(obs.get("zone")).get("dps"), 0)
        if alive is not None:
            if self.start_alive is None:
                self.start_alive = max(alive, 1)
            others = (self.start_alive - alive) - self.kills
            self.score = others
            if (others >= 2 and dps <= 35) or (others >= 3 and dps <= 100):
                self.ffa = True
                return True
            if USE_E and others >= 1 and now < E_WINDOW_S:
                self.ffa = True
                return True
        if USE_R and self.other_hp_drop(obs, events):
            self.ffa = True
            return True
        if USE_H2 and self.kills == 0 and self.two_attackers(events, now):
            self.ffa = True
            return True
        beams = seq(obs.get("beams"))[:32]
        if not beams:
            return False
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
        for beam in beams:
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
            self.ffa = True
        return self.ffa


class Sighting(NamedTuple):
    time: float
    pos: tuple
    weapons: tuple
    cubes: float | None
    hp: float | None
    yaw: float | None


class Observer(NamedTuple):
    pos: tuple
    eye: tuple
    facing: tuple | None
    wedge_weight: float


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
    SECONDARIES = ("laser", "lightning", "mortar")
    PLATING_FIRST = ("plating", "nanites", "armor", "laser_damage", "gyros")
    PICKUP_CLEARANCE = 100.0
    OPENING_CLEARANCE = 120.0

    def __init__(self, hello):
        super().__init__(hello)
        self.duel = duel_bot.DuelBot(hello)
        self.pickups = {}
        self.visible_pickups = {}
        self.last_seen = {}
        self.eliminated = set()
        self.attackers = {}
        if FFA_NO_MORTAR:
            self.SECONDARIES = ("laser", "lightning")
        self.escape_attacker = None
        self.escape_trigger = None
        self.escape_released = None
        self.single_escape = False
        self.last_escape_hit = -math.inf
        self.escape_hit_weapons = {}
        self.rivals = []
        self.first_ffa_time = None
        self.goal = None
        self.goal_until = -math.inf
        self.last_mech_damage = -math.inf
        self.last_near_sound = -math.inf
        self.heard_rival = None
        vision = obj(obj(hello.get("config")).get("vision"))
        self.vision = limit(number(vision.get("range"), 200), 45, 350)
        self.near_vision = limit(number(vision.get("near_range"), 45), 5, 100)
        self.half_fov = math.radians(limit(number(vision.get("fov_deg"), 120), 10, 360) / 2)
        self.fov_cos = math.cos(self.half_fov)
        self.margin_cos = math.cos(min(math.pi, self.half_fov + FFA_WEDGE_MARGIN))
        self.quiet_speed = max(0, number(obj(obj(hello.get("config")).get("sound")).get("step_speed"), 5) - 0.1)
        self.observers = {}
        self.mode = "survive"
        self.beam_origins = {}
        self.laser_shots = {}
        self.laser_shooter = None
        self.laser_cover = None
        self.laser_hold_until = self.laser_dodge_until = -math.inf
        self.laser_arrived = False
        self.pickup_retry = {}
        self.pickup_memory_cursor = 0

    def record(self, obs, pos, now):
        
        kills = set()
        for raw in seq(obs.get("events"))[:200]:
            event = obj(raw)
            kind = event.get("type")
            if kind == "kill":
                ident = number(event.get("target"), None)
                if ident is not None and 0 <= ident < 16:
                    kills.add(ident)
                    self.last_seen.pop(ident, None)
            elif kind == "took" or (kind == "take_failed" and event.get("reason") == "gone"):
                self.pickups.pop(number(event.get("id"), None), None)
            if (FFA_ESCAPE_LATCH and kind == "damaged" and event.get("weapon") != "zone"
                    and number(event.get("amount")) > 0):
                self.last_escape_hit = now
            source = mech_attacker(event, self.slot)
            if source is not None:
                if FFA_ESCAPE_LATCH:
                    self.escape_hit_weapons[source] = event.get("weapon")
                self.last_mech_damage = now
                yaw = number(event.get("bearing"), None)
                point = None if pos is None or yaw is None else (
                    pos[0] + 100 * math.cos(yaw), pos[1] + 100 * math.sin(yaw), pos[2]
                )
                self.attackers[source] = now, point
        self.eliminated.update(kills)

        for raw in seq(obs.get("mechs"))[:48]:
            enemy = obj(raw)
            ident, point = number(enemy.get("id"), None), vec(enemy.get("pos"), 3)
            if (enemy.get("kind") == "mech" and ident is not None and 0 <= ident < 16 and ident == int(ident) and ident != self.slot
                    and ident not in self.eliminated and point is not None):
                aim = seq(enemy.get("aim"))
                self.last_seen[ident] = Sighting(now, point, tuple(seq(enemy.get("weapons"))[:2]),
                                                number(enemy.get("cubes"), None), number(enemy.get("hp"), None),
                                                number(aim[0], None) if aim else None)
        visible = {}
        for raw in seq(obs.get("pickups"))[:64]:
            item = obj(raw)
            ident, point = number(item.get("id"), None), vec(item.get("pos"), 3)
            if ident is not None and ident >= 0 and point is not None and item.get("kind") in duel_bot.KNOWN_WEAPONS:
                visible[ident] = (now, item["kind"], point)
        self.visible_pickups = visible
        self.pickups.update(visible)
        if len(self.pickups) > 128:
            self.pickups = dict(sorted(self.pickups.items(), key=lambda item: item[1][0])[-128:])

        for raw in seq(obs.get("sounds"))[:40]:
            sound = obj(raw)
            band, kind = sound.get("dist"), sound.get("kind")
            if band not in ("near", "mid") or kind not in (
                    "gun", "mortar", "explosion", "laser", "laser_charge", "lightning", "jet", "boost", "step", "reload"):
                continue
            heard = now - max(0, number(sound.get("age")))
            if heard > self.last_near_sound and now - heard <= 2:
                self.last_near_sound = heard
                yaw = number(sound.get("bearing"), None)
                reach = 42 if band == "near" else 100
                self.heard_rival = None if pos is None or yaw is None else (
                    pos[0] + reach * math.cos(yaw), pos[1] + reach * math.sin(yaw), pos[2]
                )

    def observe(self, me, pos, actual, now):
        self.known_enemies = {i: entry.pos for i, entry in self.last_seen.items()}
        self.escape_attackers = {}
        for ident, (when, estimate) in self.attackers.items():
            if ident in self.eliminated or not 0 <= now - when <= 10:
                continue
            seen = self.last_seen.get(ident)
            point = seen.pos if seen and (estimate is None or seen.time >= when - 1) else estimate
            if point is not None:
                self.known_enemies[ident] = point
            self.escape_attackers[ident] = point
        self.disengage = len(self.escape_attackers) >= 2
        if FFA_ESCAPE_LATCH:
            self.update_escape_latch(me, pos, actual, now)
            self.single_escape = self.escape_attacker is not None and not self.disengage

        self.near_sound = 0 <= now - self.last_near_sound <= 2
        recent = {i for i, entry in self.last_seen.items() if 0 <= now - entry.time < FFA_SIGHT_MEMORY_S}
        self.prepare_risk(pos, recent)
        if self.alive == 2 and recent:
            most_recent = max(self.last_seen[i].time for i in recent)
            recent = {i for i in recent if self.last_seen[i].time == most_recent}
            self.known_enemies = {i: p for i, p in self.known_enemies.items() if i in recent}
        active = self.known_enemies if self.opening else {
            i: p for i, p in self.known_enemies.items() if i in recent or i in self.escape_attackers
        }
        self.rivals = sorted((distance(pos, p), p) for p in active.values())
        if not self.rivals and self.near_sound and self.heard_rival is not None:
            self.rivals = [(distance(pos, self.heard_rival), self.heard_rival)]
        self.farm_blocked = (0 <= now - self.last_mech_damage <= 3 or self.near_sound
                             or any(distance(pos, self.last_seen[i].pos) <= 110 for i in recent))

        if "laser" not in self.kinds and self.pickups:
            eye = raised(pos, self.phys("eye_height", 8, obj(me.get("stats"))))
            sensors = seq(me.get("upgrades")).count("sensors")
            items = list(self.pickups.items())
            if FFA_PICKUP_TAPER:
                start = self.pickup_memory_cursor % len(items)
                items = items[start:] + items[:start]
            rays = 0
            for index, (ident, (_, _, point)) in enumerate(items):
                if ident in self.visible_pickups:
                    continue
                d = distance(pos, point)
                expected = d <= self.near_vision + 15 * sensors - 3 or (
                    d <= self.vision + 25 * sensors - 10
                    and abs(angle(bearing(pos, point) - actual[0])) < self.half_fov - 0.10
                )
                if expected:
                    if self.arena is None or self.arena.clear_ray(eye, raised(point, 0.5)):
                        del self.pickups[ident]
                    rays += 1
                    if FFA_PICKUP_TAPER and rays == FFA_PICKUP_MEMORY_RAYS:
                        self.pickup_memory_cursor += index + 1
                        break

    def attacker_in_sight(self, me, pos, actual, seen):
        sensors = seq(me.get("upgrades")).count("sensors")
        span = distance(pos, seen.pos)
        if span > self.vision + 25 * sensors or (
                span > self.near_vision + 15 * sensors
                and abs(angle(bearing(pos, seen.pos) - actual[0])) > self.half_fov):
            return False
        if self.arena is None:
            return True
        eye = raised(pos, self.phys("eye_height", 8, self.self_stats))
        height = self.phys("height", 9) * (1 + max(0, seen.cubes or 0)
                                          * number(self.cubes.get("size_per_cube"), 0.05))
        return (self.arena.clear_ray(eye, raised(seen.pos, height * 0.5))
                or self.arena.clear_ray(eye, raised(seen.pos, height)))

    def update_escape_latch(self, me, pos, actual, now):
        ident = self.escape_attacker
        if ident is not None:
            if now - self.last_escape_hit >= FFA_ESCAPE_QUIET_S:
                seen = self.last_seen.get(ident)
                if (seen is None or seen.time != now or distance(pos, seen.pos) >= FFA_ESCAPE_CLEAR_M
                        or not self.attacker_in_sight(me, pos, actual, seen)):
                    self.escape_released = (ident, self.attackers[ident][0])
                    self.escape_attacker = self.escape_trigger = None
            return
        recent = [(ident, when) for ident, (when, _) in self.attackers.items()
                  if 0 <= now - when <= FFA_ESCAPE_HIT_S]
        if len(recent) != 1:
            return
        ident, when = recent[0]
        if ident in self.eliminated or (ident, when) == self.escape_released:
            return
        if self.hp < FFA_ESCAPE_HP:
            reason = "hp"
        else:
            seen = self.last_seen.get(ident)
            beam_at, origin = self.beam_origins.get(ident, (-math.inf, None))
            if seen is not None and 0 <= now - seen.time < FFA_SIGHT_MEMORY_S:
                span, weapons = distance(pos, seen.pos), seen.weapons
            elif origin is not None and 0 <= now - beam_at < FFA_SIGHT_MEMORY_S:
                span, weapons = distance(pos, origin), (self.escape_hit_weapons.get(ident),)
            else:
                return
            if "laser" in weapons and "laser" not in self.kinds and span > FFA_ESCAPE_LASER_M:
                reason = "laser"
            elif "lightning" in weapons and "lightning" not in self.kinds and span < FFA_ESCAPE_LIGHTNING_M:
                reason = "lightning"
            else:
                return
        self.escape_attacker, self.escape_trigger = ident, reason

    def pickup_threats(self, now):
        threats = []
        for ident in self.last_seen.keys() | self.attackers.keys() | self.beam_origins.keys():
            if ident in self.eliminated:
                continue
            sight = self.last_seen.get(ident)
            when, point = (sight.time, sight.pos) if sight else (-math.inf, None)
            hit, estimate = self.attackers.get(ident, (-math.inf, None))
            if hit > when:
                when, point = hit, estimate or point
            beam, origin = self.beam_origins.get(ident, (-math.inf, None))
            if beam >= when and origin is not None:
                when, point = beam, origin
            age = now - when
            if point is not None and 0 <= age < FFA_PICKUP_EXPIRY_S:
                taper = min(1, (FFA_PICKUP_EXPIRY_S - age) / (FFA_PICKUP_EXPIRY_S - FFA_PICKUP_FULL_S))
                threats.append((point, (self.PICKUP_CLEARANCE * taper) ** 2))
        return threats

    def prepare_risk(self, pos, recent):
        self.position_rays, self.steering_rays = FFA_POSITION_RAYS, FFA_STEERING_RAYS
        self.self_los = {}
        self.body_height = limit(self.phys("height", 9, self.self_stats), 1, 80)
        self.observers = {}
        self.nearest_thresholds = ()
        if not (FFA_WEDGE or FFA_NOT_NEAREST or FFA_UNSEEN_OPEN or FFA_QUIET_WALK):
            return
        eye = limit(self.phys("eye_height", 8), 1, 80)
        size_per_cube = number(self.cubes.get("size_per_cube"), 0.05)
        size_cap = math.inf if FFA_SIZE_UNCAP else number(self.cubes.get("stat_cap"), 10)
        for ident in sorted(recent, key=lambda i: distance_sq(pos, self.last_seen[i].pos)):
            seen = self.last_seen[ident]
            scale = 1 + size_per_cube * limit(seen.cubes or 0, 0, size_cap)
            facing = (math.cos(seen.yaw), math.sin(seen.yaw)) if seen.yaw is not None else None
            weight = FFA_WEDGE_COST * (FFA_LASER_MULT if "laser" in seen.weapons else 1)
            self.observers[ident] = Observer(seen.pos, raised(seen.pos, eye * scale), facing, weight)
        if FFA_NOT_NEAREST:
            
            points = [enemy.pos for enemy in self.observers.values()]
            self.nearest_thresholds = tuple(
                (point, min((distance_sq(point, other) for j, other in enumerate(points) if i != j),
                            default=math.inf) / FFA_NEAREST_RATIO ** 2)
                for i, point in enumerate(points)
            )

    def in_wedge(self, enemy, point, span_sq, margin=False):
        if span_sq <= self.near_vision ** 2:
            return True
        if span_sq > self.vision ** 2:
            return False
        if enemy.facing is None:
            return True
        dx, dy = point[0] - enemy.pos[0], point[1] - enemy.pos[1]
        return dx * enemy.facing[0] + dy * enemy.facing[1] >= (
            self.margin_cos if margin else self.fov_cos) * math.sqrt(span_sq)

    def nearest_cost(self, point):
        cost = 0.0
        for enemy, threshold in self.nearest_thresholds:
            span_sq = distance_sq(point, enemy)
            if span_sq <= threshold:
                cost += FFA_NEAREST_COST * 150 ** 2 / max(45 ** 2, span_sq)
        return cost

    def wedge_threats(self, point):
        for enemy in self.observers.values():
            span_sq = distance_sq(point, enemy.pos)
            if self.in_wedge(enemy, point, span_sq, margin=True):
                weight = enemy.wedge_weight * min(2, 150 / max(45, math.sqrt(span_sq)))
                yield enemy.eye, weight

    def wedge_score(self, point, threats, steering=False):
        ray_budget = self.steering_rays if steering else self.position_rays
        chest = raised(point, self.body_height * 0.65)
        cost = 0.0
        for eye, weight in threats:
            if self.arena is not None and ray_budget > 0:
                ray_budget -= 1
                if not self.arena.clear_ray(eye, chest):
                    continue
            
            cost += weight
        if steering:
            self.steering_rays = ray_budget
        else:
            self.position_rays = ray_budget
        return -cost if cost else FFA_HIDDEN_REWARD

    def position_score(self, point):
        wedge = self.wedge_score(point, self.wedge_threats(point)) if FFA_WEDGE and self.observers else 0
        return wedge - self.nearest_cost(point)

    def steer_score(self, point):
        wedge = self.wedge_score(point, self.wedge_threats(point), steering=True) if FFA_WEDGE and self.observers else 0
        return wedge - self.nearest_cost(point)

    def line_to_self(self, ident, enemy, pos):
        
        if ident not in self.self_los:
            self.self_los[ident] = (self.arena is None
                                    or self.arena.clear_ray(enemy.eye, raised(pos, self.body_height * 0.5))
                                    or self.arena.clear_ray(enemy.eye, raised(pos, self.body_height)))
        return self.self_los[ident]

    def can_open(self, ident, pos):
        if not FFA_UNSEEN_OPEN:
            return True
        target = self.observers.get(ident)
        if target is None or target.facing is None or self.in_wedge(target, pos, distance_sq(pos, target.pos)):
            return False
        return not any(
            other != ident and (span_sq := distance_sq(pos, enemy.pos)) <= 160 ** 2
            and self.in_wedge(enemy, pos, span_sq)
            for other, enemy in self.observers.items()
        )

    def walk_quietly(self, pos):
        if not FFA_QUIET_WALK:
            return False
        if any(distance_sq(pos, enemy.pos) <= 120 ** 2 for enemy in self.observers.values()):
            return False
        pickup = self.weapon_point or self.loot_point
        if pickup is not None:
            race_limit = 1.5 ** 2 * distance_sq(pos, pickup)
            if any(distance_sq(enemy.pos, pickup) < race_limit for enemy in self.observers.values()):
                return False
        return not any(self.line_to_self(ident, enemy, pos) for ident, enemy in self.observers.items())

    def clear_approach(self, pos, goal, clearance, strict=False):
        for d, enemy in self.rivals:
            minimum = clearance if strict else min(clearance, max(0, d - 1))
            if segment_distance_sq(pos, goal, enemy) <= minimum ** 2:
                return False
            if not strict and distance(goal, enemy) < min(clearance, d + 10):
                return False
        return True

    def safe_pickup_route(self, pos, goal):
        if FFA_PICKUP_TAPER:
            return all(segment_distance_sq(pos, goal, enemy) > clearance_sq
                       for enemy, clearance_sq in self.pickup_clearances)
        return all(segment_distance_sq(pos, goal, enemy) > self.PICKUP_CLEARANCE ** 2
                   for enemy in self.known_enemies.values())

    def nearby_weapon(self, pos):
        spare = next((i for i, w in enumerate(self.weapon_slots) if not w.get("kind")), None)
        swap = next((i for i, w in enumerate(self.weapon_slots) if w.get("kind") in ("mortar", "lightning")), None)
        options = []
        for ident, (_, kind, point) in self.visible_pickups.items():
            if FFA_NO_MORTAR and kind == "mortar":
                continue
            if kind in self.kinds or (spare is None and (kind != "laser" or swap is None)):
                continue
            span = distance_sq(pos, point)
            if span <= FFA_PICKUP_NEAR_M ** 2 and abs(point[2] - pos[2]) <= FFA_PICKUP_NEAR_M:
                rank = self.SECONDARIES.index(kind) if kind in self.SECONDARIES else len(self.SECONDARIES)
                options.append((rank, span, ident))
        return (min(options)[2], swap if spare is None else None) if options else (None, None)

    def weapon_goal(self, pos, zone, weapons, urgent, action):
        if "laser" in self.kinds:
            return None
        spare = next((i for i, w in enumerate(weapons) if not w.get("kind")), None)
        swap = next((i for i, w in enumerate(weapons) if w.get("kind") in self.SECONDARIES
                     or (FFA_NO_MORTAR and w.get("kind") == "mortar")), None)
        if urgent or (spare is None and swap is None):
            return None
        options = []
        reach = limit(number(self.loot.get("pickup_radius"), 4), 0.5, 15)
        if FFA_PICKUP_TAPER and not self.safe_pickup_route(pos, pos):
            return None
        for ident, (_, kind, point) in self.pickups.items():
            if FFA_PICKUP_TAPER and (ident == self.nearby_take[0] or self.pickup_retry.get(ident, -math.inf) > zone.now):
                continue
            if kind not in self.SECONDARIES or kind in self.kinds:
                continue
            priority = self.SECONDARIES.index(kind)
            if (spare is None and weapons[swap]["kind"] in self.SECONDARIES
                    and priority >= self.SECONDARIES.index(weapons[swap]["kind"])):
                continue
            d, climb = distance(pos, point), point[2] - pos[2]
            if d > 150 or not -65 <= climb <= 36 or (climb > 4 and self.energy <= 45):
                continue
            take = math.hypot(d, climb) <= reach and ident in self.visible_pickups
            outside = max(0, distance(point, zone.next_center) - zone.next_radius + 10)
            cost = 0 if take else d + max(0, climb - 4) * 2 + outside * 0.55
            option = priority, cost, ident, point, take
            
            start = point if FFA_PICKUP_TAPER and self.arena is not None else pos
            if zone.gap(point, 0 if take else d / 9 + 4) > 0 and self.safe_pickup_route(start, point):
                options.append(option)
        if not options:
            return None
        options.sort()
        best = options[0]
        if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) and not best[4]:
            best = min((option for option in options[:6] if option[0] == best[0]),
                       key=lambda option: option[1] - self.position_score(option[3]))
        _, _, ident, point, take = best
        self.mode = "arm"
        if take:
            action["take"] = ident
            if spare is None:
                action["drop"] = swap
            return pos[:2]
        self.weapon_point = point
        self.weapon_id = ident
        return point[:2]

    def loot_goal(self, obs, pos, zone, contacts, weapons, hp_fraction, cubes, safe, urgent, action):
        if FFA_LASER_COVER and self.laser_response_pending:
            return None
        if self.disengage or self.single_escape:
            self.mode = "escape"
            self.goal = self.search = self.route_goal = None
            self.path, self.path_index = (), 0
            return None
        goal = self.weapon_goal(pos, zone, weapons, urgent, action)
        if goal is not None:
            return goal
        nearest = self.rivals[0][0] if self.rivals else math.inf
        quiet = nearest >= self.SEPARATION and not self.farm_blocked
        if urgent or not quiet:
            return None
        options = []
        for raw in seq(obs.get("cubes"))[:64]:
            point = vec(obj(raw).get("pos"), 3)
            if point is not None and abs(point[2] - pos[2]) < 4:
                d = distance(pos, point)
                if (d < 135 and zone.gap(point, d / 9 + 3) > 2
                        and (not self.opening or distance(point, zone.next_center) < zone.next_radius)
                        and self.clear_approach(pos, point, self.SEPARATION, strict=self.opening)):
                    options.append((d, point))
        for raw in seq(obs.get("drops"))[:8]:
            item = obj(raw)
            point = vec(item.get("pos"), 3)
            if point is None or item.get("holder") not in (None, self.slot):
                continue
            d = distance(pos, point)
            if (d < 110 and number(item.get("lands_in"), 0) < d / 10 + 1
                    and zone.gap(point, d / 9 + 10) > 4
                    and (not self.opening or distance(point, zone.next_center) < zone.next_radius)
                    and self.clear_approach(pos, point, 165, strict=self.opening)):
                options.append((d * 0.60 - 14 - 24 * (1 - hp_fraction), point))
        if options:
            self.mode = "loot"
            options.sort()
            if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST):
                self.loot_point = min(options[:6], key=lambda option: option[0] - self.position_score(option[1]))[1]
            else:
                self.loot_point = options[0][1]
            return self.loot_point[:2]
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
        if FFA_LASER_COVER and self.laser_response_pending:
            return pos[:2]
        if self.disengage or self.single_escape:
            return pos[:2]
        if terminal_burn:
            point_score = self.position_score if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) else None
            return super().shelter_point(pos, zone, contacts, direction, radius, height, now, until, True,
                                         point_score=point_score)
        if self.farm is not None:
            return pos[:2]
        scouting = (FFA_PICKUP_TAPER and self.opening and self.kinds.isdisjoint(self.SECONDARIES)
                    and not self.farm_blocked)
        if self.goal is not None and now < self.goal_until and distance(pos, self.goal) > 3:
            safe_leg = (self.safe_pickup_route(pos, self.goal) if scouting else
                        self.clear_approach(pos, self.goal, self.OPENING_CLEARANCE, strict=self.opening))
            if (not self.opening or distance(self.goal, zone.next_center) < zone.next_radius) and (
                    safe_leg):
                return self.goal

        arena = self.arena
        goal_radius = max(0, zone.next_radius - min(16, zone.next_radius * 0.22))
        next_gap = goal_radius - distance(pos, zone.next_center)
        roam = ((self.alive > 3 and self.kinds.isdisjoint(self.SECONDARIES) and self.hp_share > 0.65)
                or (self.alive == 2 and not self.rivals and self.hp_share > 0.86))
        scout = self.scout_yaw + math.floor(now / 10) * 1.91
        sx, sy = math.cos(scout), math.sin(scout)
        enemies = (sorted((distance(pos, point), point) for point, _ in self.pickup_clearances)
                   if scouting else self.rivals)
        options = []
        future_center, future_radius = zone.circle_in(7)
        future_margin = min(5, zone.radius * 0.18)
        for run in (0, 26, 58):
            for dx, dy in eb.COVER_ANGLES if run else ((0, 0),):
                point = pos[0] + dx * run, pos[1] + dy * run
                if future_radius - distance(point, future_center) < future_margin:
                    continue
                cell = arena.cell(*point) if arena is not None else None
                if run and arena is not None and not arena.ground_ok(cell, radius):
                    continue
                base = arena.floor[cell] if run and cell is not None else pos[2]
                gap = goal_radius - distance(point, zone.next_center)
                score = min(0, gap) * 1.5 + min(18, max(0, gap)) * 0.15 - run * 0.16
                if self.opening and gap < goal_radius - zone.next_radius:
                    score -= 110
                if roam and next_gap > -28:
                    score += run * (0.22 + (dx * sx + dy * sy) * 0.15)
                if cell is not None:
                    near = arena.clearance[cell] * eb.GRID_M
                    score += max(0, 20 - abs(near - radius - 5)) * 0.65
                for d, enemy in enemies:
                    separation = distance(point, enemy)
                    score -= max(0, self.SEPARATION - separation) * (1.5 if d < 125 else 0.85)
                    score -= max(0, 64 - separation) * 1.8
                    if self.opening and run and segment_distance_sq(pos, point, enemy) <= min(d - 0.1, self.OPENING_CLEARANCE) ** 2:
                        score -= 45
                    if self.alive == 2 and self.fight is not None:
                        preferred = 152 if "laser" in self.kinds else 125
                        score -= abs(separation - preferred) * 1.2
                score -= self.nearest_cost(point)
                options.append((score, run, point, base))
        best, top_score = pos[:2], -math.inf
        wedge = FFA_WEDGE and self.observers
        if wedge:
            candidates = []
            for score, run, point, base in options:
                threats = tuple(self.wedge_threats(point))
                exposed_score = score - sum(weight for _, weight in threats) if threats else score + FFA_HIDDEN_REWARD
                candidates.append((exposed_score, score, run, point, base, threats))
            
            candidates.sort(reverse=True, key=lambda option: option[:4])
        else:
            standing = [option for option in options if option[1] == 0]
            candidates = [(score, score, run, point, base, ()) for score, run, point, base
                          in sorted(options, reverse=True)[:5] + standing]
        for _, score, run, point, base, threats in candidates:
            if wedge:
                if score + FFA_HIDDEN_REWARD <= top_score:
                    continue
                score += self.wedge_score((*point, base), threats)
            if arena is not None and time.perf_counter() < until:
                if not wedge:
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
        if FFA_LASER_COVER and self.laser_response_pending:
            return goal
        if self.disengage or self.single_escape:
            return goal
        arena, pickup = self.arena, self.weapon_point
        if (arena is not None and pickup is not None and pickup[:2] == goal
                and 3.5 < pickup[2] - pos[2] and distance(pos, pickup) < 30
                and not arena.solid(raised(pos, height + 1.5))
                and (not FFA_PICKUP_TAPER or self.safe_pickup_route(pos, goal))):
            self.climb = True
            return goal
        waypoint_score = self.position_score if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) else None
        waypoint = super().route(pos, goal, zone, radius, height, stuck, until, waypoint_score=waypoint_score)
        if pickup is not None:
            follows_path = (self.path and (self.route_goal == goal or
                            (FFA_PICKUP_TAPER and waypoint == self.path[self.path_index])))
            points = self.path[self.path_index:] if follows_path else ()
            unsafe = not self.safe_pickup_route(pos, waypoint) or any(
                not self.safe_pickup_route(start, end) for start, end in zip(points, points[1:]))
            if FFA_PICKUP_TAPER and points:
                unsafe |= not self.safe_pickup_route(points[-1], goal)
            if unsafe:
                self.weapon_point = None
                self.mode = "survive"
                if not FFA_PICKUP_TAPER or self.search is None:
                    if FFA_PICKUP_TAPER:
                        self.pickup_retry[self.weapon_id] = zone.now + 0.5
                    self.search = self.route_goal = None
                    self.path, self.path_index = (), 0
                return self.shelter_point(pos, zone, (), None, radius, height, zone.now, until, False)
        elif waypoint != goal and not (
                self.safe_pickup_route(pos, waypoint) if FFA_PICKUP_TAPER and self.opening
                and self.kinds.isdisjoint(self.SECONDARIES) and not self.farm_blocked
                else self.clear_approach(pos, waypoint, self.OPENING_CLEARANCE if self.opening else 105)):
            if zone.gap(pos, 3) <= 8:
                return waypoint
            self.loot_point = None
            return self.shelter_point(pos, zone, (), None, radius, height, zone.now, until, False)
        return waypoint

    def escape_move(self, pos, vel, goal, zone, hazards, stats, grounded, energy, urgent, quiet):
        arena = self.arena
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        height = limit(self.phys("height", 9, stats), 1, 80)
        boost = not quiet and grounded and energy > eb.BOOST_RESERVE
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 90)
        pace = limit(self.phys("boost_speed", 19.5, stats), 2, 90) if boost else walk
        scale = min(1, self.quiet_speed / walk) if quiet else 1
        pace *= scale
        attackers = [(distance(pos, point), point) for point in self.escape_attackers.values() if point is not None]
        origin = None
        if self.single_escape:
            ident = self.escape_attacker
            seen = self.last_seen.get(ident)
            beam_at, beam = self.beam_origins.get(ident, (-math.inf, None))
            hit_at, estimate = self.attackers[ident]
            if seen is not None and seen.time >= max(beam_at, hit_at - 1):
                point = seen.pos
                origin = self.shooter_origin(ident)
            elif beam is not None and beam_at >= hit_at - 1:
                point = origin = beam
            else:
                point = estimate if estimate is not None else seen.pos if seen is not None else None
            attackers = [(distance(pos, point), point)] if point is not None else []
        self.escape_bearings = [(span, bearing(pos, point)) for span, point in attackers]
        cover_threats = sorted(attackers)[:2] if FFA_WEDGE else attackers
        best, move = None, (0.0, 0.0)
        center, size = zone.circle_in(1.5)
        gap = size - distance(pos, center)
        next_gap = zone.next_radius - distance(pos, zone.next_center)
        candidates = []
        angles = eb.COVER_ANGLES
        if self.single_escape and attackers:
            away = bearing(attackers[0][1], pos)
            angles = ((math.cos(away), math.sin(away)), *angles)
        for dx, dy in angles:
            min_gap = gap + 0.1 if urgent and gap < 0 else min(-0.2, gap - 0.2)
            for horizon in ((0.58, 0.25) if self.single_escape else (0.58,)):
                end = (pos[0] + dx * pace * horizon + vel[0] * 0.12,
                       pos[1] + dy * pace * horizon + vel[1] * 0.12)
                if arena is not None and not arena.corridor(pos, end, radius, height):
                    continue
                end_gap = size - distance(end, center)
                if end_gap >= min_gap:
                    break
            else:
                continue
            gains = [distance(end, point) - span for span, point in attackers]
            worst = min(gains, default=0.0)
            score = sum(gains) + 2 * worst
            if urgent:
                score += 4 * (distance(pos, goal) - distance(end, goal))
            if self.opening and next_gap < 20:
                score += min(0, zone.next_radius - distance(end, zone.next_center)) - min(0, next_gap)
            for impact, seconds, reach in hazards:
                future = pos[0] + dx * pace * seconds, pos[1] + dy * pace * seconds
                score -= 2.1 * max(0, reach - distance(future, impact))
            if FFA_WEDGE or FFA_NOT_NEAREST:
                score += 0.16 * self.steer_score((*end, pos[2]))
            if arena is not None and not (FFA_WEDGE and self.observers):
                body = end[0], end[1], pos[2] + height * 0.65
                score += 28 * sum(not arena.clear_ray(raised(point, 8), body) for _, point in cover_threats)
            if self.single_escape:
                score += 0.6 * min(12, end_gap)
                candidates.append(((end_gap >= 0, worst > 0, score), end, (dx, dy)))
                continue
            option = (worst > 0, score)
            if best is None or option > best:
                best, move = option, (dx * scale, dy * scale)
        if candidates:
            candidates.sort(reverse=True)
            best, _, move = candidates[0]
            if arena is not None and origin is not None:
                
                for (inside, away, score), end, direction in candidates[:4]:
                    if not arena.clear_ray(origin, raised(end + (pos[2],), height * 0.65)):
                        option = (inside, away, score + 15)
                        if option > best:
                            best, move = option, direction
        if best is None:
            return None
        return {"move": list(move), "boost": boost, "jump": False}

    def movement(self, pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction, stats,
                 grounded, energy, now, until, in_zone, terminal_burn, drop_hint):
        if FFA_LASER_COVER and self.laser_response_pending:
            response = self.laser_move(pos, vel, zone, stats, grounded, energy)
            if response is not None:
                self.course, self.sprinting = response["move"], response["boost"]
                return response
        fast_arm = (FFA_ARM_FAST and self.weapon_point is not None and self.kinds == {"gun"}
                    and 0 <= now - self.first_ffa_time < FFA_ARM_S and self.hp >= FFA_ARM_HP and not urgent)
        quiet = (not (fast_arm or self.single_escape) and not self.laser_response_pending
                 and self.walk_quietly(pos))
        speed_cap = self.quiet_speed if quiet else None
        steer_score = self.steer_score if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) else None
        if self.disengage or self.single_escape:
            escape = self.escape_move(pos, vel, waypoint, zone, hazards, stats, grounded, energy, urgent, quiet)
            if escape is not None:
                if FFA_PICKUP_TAPER and not self.single_escape:
                    self.sweep_cube(pos, zone, stats, escape)
                self.course = escape["move"]
                self.sprinting = escape["boost"]
                return escape
            if self.single_escape:
                
                waypoint = zone.center if distance(pos, waypoint) < eb.HOLD_M else waypoint
                evade = True
        nearest = self.rivals[0][0] if self.rivals else math.inf
        running = (nearest < 118 and self.fight is None and self.weapon_point is None
                   and (distance(pos, waypoint) > eb.HOLD_M or any(c.clear for c in threats)))
        move = super().movement(pos, vel, waypoint, zone, urgent, evade or running, threats, hazards, direction,
                                stats, grounded, energy, now, until, in_zone, terminal_burn, drop_hint,
                                steer_score=steer_score, speed_cap=speed_cap)
        if self.climb:
            course = bearing(pos, waypoint)
            speed = 0.33 if self.weapon_point[2] - pos[2] > 7 else 0.75
            if quiet:
                speed = min(speed, self.quiet_speed / limit(self.phys("walk_speed", 11.7, stats), 2, 60))
            move = {"move": [speed * math.cos(course), speed * math.sin(course)],
                    "jump": grounded, "boost": not grounded and not quiet}
        if self.weapon_point is not None:
            span = min(12, distance(pos, waypoint)) if FFA_PICKUP_TAPER else 12
            projected = pos[0] + span * move["move"][0], pos[1] + span * move["move"][1]
            if not self.safe_pickup_route(pos, projected):
                self.weapon_point = None
                self.mode = "survive"
                cover = self.shelter_point(pos, zone, (), direction, self.phys("radius", 2.5, stats),
                                           self.phys("height", 9, stats), now, until, terminal_burn)
                quiet = self.walk_quietly(pos)
                move = super().movement(pos, vel, cover, zone, urgent, evade, threats, hazards, direction,
                                        stats, grounded, energy, now, until, in_zone, terminal_burn, drop_hint,
                                        steer_score=steer_score, speed_cap=self.quiet_speed if quiet else None)
        if (not quiet and (running or self.weapon_point is not None) and grounded and energy > eb.BOOST_RESERVE
                and distance(pos, waypoint) > 7 and not move.get("jump")):
            move["boost"] = True
        if self.single_escape and grounded and energy > eb.BOOST_RESERVE and not move.get("jump"):
            move["boost"] = math.hypot(*move["move"]) > 0
        if fast_arm and self.weapon_point is not None and move.get("boost"):
            drain = self.phys("boost_drain", 17, stats) if grounded else self.phys("jet_drain", 28, stats)
            move["boost"] = energy > eb.BOOST_RESERVE + self.dt * max(0, drain)
        if FFA_PICKUP_TAPER and not self.single_escape:
            self.sweep_cube(pos, zone, stats, move)
        self.course = move["move"]
        self.sprinting = bool(move.get("boost"))
        return move

    def sweep_cube(self, pos, zone, stats, move):
        
        if self.nearby_cube is None or self.climb:
            return
        dx, dy = move["move"]
        pace = math.hypot(dx, dy)
        if pace < 0.15:
            return
        cube = self.nearby_cube
        x, y = cube[0] - pos[0], cube[1] - pos[1]
        forward = (x * dx + y * dy) / pace
        side = (y * dx - x * dy) / pace
        reach = limit(number(self.cubes.get("pickup_radius"), 3.5), 0.5, FFA_PICKUP_NEAR_M)
        if forward <= 0 or abs(side) <= reach:
            return
        
        turn = math.copysign(math.atan2(abs(side), forward) - math.asin(min(1, (reach - 0.1) / math.hypot(x, y))), side)
        if abs(turn) > 0.35:
            return
        dx, dy = dx * math.cos(turn) - dy * math.sin(turn), dx * math.sin(turn) + dy * math.cos(turn)
        end = (pos[0] + 5 * dx / pace, pos[1] + 5 * dy / pace)
        if zone.gap(end, 0.5) < min(0, zone.gap(pos)):
            return
        if self.weapon_point is not None and not self.safe_pickup_route(pos, end):
            return
        if self.arena is None or self.arena.corridor(pos, end, self.phys("radius", 2.5, stats), self.body_height):
            move["move"] = [dx, dy]

    def laser_evidence(self, obs, pos, now):
        radius = limit(self.phys("radius", 2.5, self.self_stats), 0.5, 25)
        height = limit(self.phys("height", 9, self.self_stats), 1, 80)
        hits = {}
        for raw in seq(obs.get("beams"))[:32]:
            beam = obj(raw)
            kind, source = beam.get("kind"), number(beam.get("by"), -1)
            path = seq(beam.get("path"))
            if (kind not in ("laser", "lightning") or source not in range(16) or source == self.slot
                    or len(path) < 2 or (origin := vec(path[0], 3)) is None):
                continue
            when = now - max(0, number(beam.get("age")))
            if when >= self.beam_origins.get(source, (-math.inf, None))[0]:
                self.beam_origins[source] = when, origin
            if FFA_LASER_COVER and kind == "laser":
                self.laser_shots[source] = max(when, self.laser_shots.get(source, -math.inf))
                end = vec(path[1], 3)
                if (0 <= now - when <= 0.25 and end is not None
                        and distance_sq(pos, end) <= (radius + 0.75) ** 2
                        and -0.5 <= end[2] - pos[2] <= height + 0.5):
                    hits[source] = bearing(pos, origin)
        if FFA_LASER_COVER:
            for raw in seq(obs.get("events"))[:200]:
                event = obj(raw)
                if event.get("weapon") == "laser" and (source := mech_attacker(event, self.slot)) is not None:
                    hits.setdefault(source, number(event.get("bearing"), None))
            self.laser_shots.update((source, now) for source in hits)
        return hits

    def shooter_origin(self, ident):
        seen = self.last_seen.get(ident)
        when, origin = self.beam_origins.get(ident, (-math.inf, None))
        if seen is not None and seen.time > when:
            scale = 1 + limit(seen.cubes or 0, 0, 100) * number(self.cubes.get("size_per_cube"), 0.05)
            return raised(seen.pos, self.phys("muzzle_height", 7) * scale)
        return origin

    def laser_blocked(self, origin, point):
        for fraction in (0.92, 0.25, 0.58):
            if self.laser_rays <= 0:
                return False
            self.laser_rays -= 1
            if self.arena.clear_ray(origin, raised(point, self.body_height * fraction)):
                return False
        return True

    def find_laser_cover(self, pos, vel, origin, others, zone, radius, walk, boost, stats, energy):
        arena = self.arena
        accel = limit(self.phys("ground_accel", 58.5, stats), 2, 500)
        drain = limit(self.phys("boost_drain", 17, stats), 0.1, 500)
        sprint_time = limit((energy - eb.BOOST_RESERVE) / drain, 0, FFA_LASER_TRAVEL_S)
        travel = sprint_time * boost + (FFA_LASER_TRAVEL_S - sprint_time) * walk
        pace = boost if sprint_time > 0 else walk
        start_cell = arena.cell(*pos[:2])
        elevated = start_cell is not None and pos[2] > arena.floor[start_cell] + arena.step_up + 1.5
        side = bearing(origin, pos) + math.pi / 2
        cs, sn = math.cos(side), math.sin(side)
        options = []
        for dx, dy in eb.COVER_ANGLES:
            ux, uy = dx * cs - dy * sn, dx * sn + dy * cs
            start_speed = vel[0] * ux + vel[1] * uy
            reach = travel - max(0, pace - start_speed) ** 2 / (2 * accel)
            for fraction in (0.45, 0.72, 1.0):
                span = reach * fraction
                if span < 2:
                    continue
                x, y = pos[0] + ux * span, pos[1] + uy * span
                cell = arena.cell(x, y)
                if cell is None or (not elevated and not arena.ground_ok(cell, radius)):
                    continue
                z = arena.roof[cell] if elevated else arena.floor[cell]
                point = x, y, z
                if (elevated and abs(z - pos[2]) > arena.step_up + 0.5
                        or min(zone.gap(point, FFA_LASER_TRAVEL_S),
                               zone.gap(point, FFA_LASER_TRAVEL_S + FFA_LASER_HOLD_S)) < 0):
                    continue
                options.append((span + 0.35 * min(30, arena.near_cover(point)), point))
        for _, point in sorted(options):
            if self.laser_rays < 3:
                break
            if (arena.corridor(pos, point, radius, self.body_height)
                    and self.laser_blocked(origin, point)
                    and all(self.laser_blocked(other, point) for other in others)):
                return point
        return None

    def laser_move(self, pos, vel, zone, stats, grounded, energy):
        now = zone.now
        hit = next(iter(self.laser_hits), None)
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        boost = limit(self.phys("boost_speed", 19.5, stats), walk, 90)
        sprint = grounded and energy > eb.BOOST_RESERVE
        pace = boost if sprint else walk
        arena = self.arena
        self.laser_rays = FFA_LASER_COVER_RAYS
        cover = self.laser_cover
        if cover is not None:
            others = self.other_shooters(self.laser_shooter, now)
            exposed = next((ident for ident, origin in others if not self.laser_blocked(origin, cover)), None)
            arrival = distance(pos, cover) <= 1.15
            if arrival and not self.laser_arrived:
                self.laser_arrived = True
                self.laser_hold_until = max(self.laser_hold_until, now + FFA_LASER_HOLD_S)
            zone_safe = zone.gap(cover, max(0, self.laser_hold_until - now)) >= 0
            if now < self.laser_hold_until and exposed is None and zone_safe:
                return self.move_to_laser_cover(pos, cover, pace, sprint)
            self.laser_cover = cover = None
            if hit is None:
                hit = exposed if exposed is not None else self.laser_shooter if not zone_safe else None
        if hit is not None:
            self.laser_shooter = hit
            self.laser_yaw = self.laser_hits.get(hit)
            origin = self.shooter_origin(hit)
            others = tuple(point for _, point in self.other_shooters(hit, now))
            if arena is not None and origin is not None and grounded:
                cover = self.find_laser_cover(pos, vel, origin, others, zone, radius, walk, boost, stats, energy)
            if cover is not None:
                self.laser_cover, self.laser_arrived = cover, False
                self.laser_hold_until = now + FFA_LASER_HOLD_S
                self.laser_dodge_until = -math.inf
                return self.move_to_laser_cover(pos, cover, pace, sprint)
            self.laser_dodge_until = now + FFA_LASER_TRAVEL_S
        if now >= self.laser_dodge_until:
            self.laser_response_pending = False
            return None

        origin = self.shooter_origin(self.laser_shooter)
        yaw = self.laser_yaw
        if yaw is None:
            yaw = bearing(pos, origin) if origin is not None else self.actual[0]
        best = None
        for offset in (math.pi / 2, -math.pi / 2, 1.1, -1.1, 2.0, -2.0):
            dx, dy = math.cos(yaw + offset), math.sin(yaw + offset)
            for horizon in (0.55, 0.25):
                end = pos[0] + dx * pace * horizon, pos[1] + dy * pace * horizon
                gap = zone.gap(end, horizon)
                if gap < min(0, zone.gap(pos, horizon)) or (
                        arena is not None and not arena.corridor(pos, end, radius, self.body_height)):
                    continue
                score = (abs(offset) == math.pi / 2, horizon, gap, dx * vel[0] + dy * vel[1])
                if best is None or score > best[0]:
                    best = score, [dx, dy]
                break
        if best is not None:
            self.mode = "laser-dodge"
            return {"move": best[1], "boost": sprint, "jump": False}
        return None

    def other_shooters(self, primary, now):
        shots = {ident: when for ident, (when, _) in self.attackers.items()}
        for ident, when in self.laser_shots.items():
            shots[ident] = max(shots.get(ident, -math.inf), when)
        for ident, when in sorted(shots.items(), key=lambda item: item[1], reverse=True):
            if ident == primary or ident in self.eliminated or not 0 <= now - when <= FFA_LASER_HOLD_S:
                continue
            origin = self.shooter_origin(ident)
            if origin is not None:
                yield ident, origin

    def move_to_laser_cover(self, pos, cover, pace, sprint):
        self.mode = "laser-cover"
        span = distance(pos, cover)
        scale = min(1, span / (pace * 0.28)) if span > 0.45 else 0
        yaw = bearing(pos, cover)
        return {"move": [scale * math.cos(yaw), scale * math.sin(yaw)], "boost": sprint and scale > 0, "jump": False}

    def no_escape(self, pos, enemy, zone):
        radius = self.phys("radius", 2.5, self.self_stats)
        height = self.phys("height", 9, self.self_stats)
        span = distance(pos, enemy.pos)
        center, size = zone.circle_in(0.8)
        for dx, dy in eb.COVER_ANGLES:
            end = pos[0] + 8 * dx, pos[1] + 8 * dy
            if distance(end, center) > size or distance(end, enemy.pos) <= span + 1:
                continue
            if self.arena is None or self.arena.corridor(pos, end, radius, height):
                return False
        return True

    def finish_damage(self, enemy, pos):
        
        total = 0.0
        muzzle = self.phys("muzzle_height", 7, self.self_stats)
        pitch = self.phys("min_pitch", -0.7, self.self_stats), self.phys("max_pitch", 1.3, self.self_stats)
        turn = max(0.1, self.phys("turn_rate", 4, self.self_stats))
        pitch_rate = max(0.1, self.phys("pitch_rate", 3, self.self_stats))
        for weapon in self.weapon_slots:
            kind = weapon.get("kind")
            if kind not in duel_bot.KNOWN_WEAPONS or (kind == "laser" and self.sprinting and not number(weapon.get("charge"))):
                continue
            if kind == "lightning" and self.energy < eb.BOOST_RESERVE:
                continue
            plan = self.aim_for(weapon, enemy, pos, muzzle, pitch)
            if plan is None:
                continue
            stats, defaults = obj(weapon.get("stats")), obj(self.weapon_config.get(kind))
            cooldown, damage = {"gun": (0.24, 45), "laser": (1.65, 315),
                                "mortar": (2.1, 200), "lightning": (0.25, 60)}[kind]
            interval = max(self.dt, number(stats.get("cooldown"), number(defaults.get("cooldown"), cooldown)))
            damage = number(stats.get("damage"), number(defaults.get("damage"), damage))
            aim_time = max(0, abs(angle(plan[0] - self.actual[0])) - plan[2]) / turn
            if kind != "lightning":
                aim_time = max(aim_time, (abs(plan[1] - self.actual[1]) - plan[3]) / pitch_rate)
            first = max(aim_time, number(weapon.get("cooldown")), number(weapon.get("reload")))
            if kind == "laser":
                charge = number(weapon.get("charge"))
                full_charge = number(stats.get("charge"), number(defaults.get("charge"), 0.75))
                first = max(first, full_charge - charge) if charge else first + full_charge
            if kind in ("gun", "mortar"):
                speed = number(stats.get("speed"), number(defaults.get("speed"), 252 if kind == "gun" else 72))
                first += enemy.dist / max(1, speed * (0.8 if kind == "mortar" else 1))
            shots = max(0, 1 + math.floor((1.5 - first) / interval))
            if kind == "gun":
                shots = min(shots, max(0, number(weapon.get("ammo"), 12)))
            reliability = {"gun": 0.72, "laser": 0.90, "mortar": 0.45, "lightning": 0.95}[kind]
            total += shots * damage * reliability
        return total

    def target(self, obs, pos, contacts, fraction, zone, must_move, safe, terminal_burn, repairing, incoming):
        if self.single_escape:
            return []
        options = []
        now = zone.now
        for enemy in contacts:
            if enemy.kind != "mech" or not enemy.clear or enemy.id in self.eliminated:
                continue
            if self.disengage:
                dx, dy = self.course
                end = pos[0] + 25 * dx, pos[1] + 25 * dy
                if (enemy.dist > 30 or (enemy.pos[0] - pos[0]) * dx + (enemy.pos[1] - pos[1]) * dy <= 0
                        or segment_distance_sq(pos, end, enemy.pos) > (enemy.scale * 2.5 + 4) ** 2):
                    continue
            when, _ = self.attackers.get(enemy.id, (-math.inf, None))
            if 0 <= now - when <= 6:
                options.append((100 - enemy.dist * 0.1, enemy))
                continue
            if enemy is self.fight:
                if (FFA_DUEL_OPEN and self.alive == 2) or self.can_open(enemy.id, pos):
                    options.append((100 - enemy.dist * 0.1, enemy))
                continue
            if enemy.dist <= 30 and self.can_open(enemy.id, pos):
                dx, dy = pos[0] - enemy.pos[0], pos[1] - enemy.pos[1]
                if dx * enemy.vel[0] + dy * enemy.vel[1] > 0 and self.no_escape(pos, enemy, zone):
                    options.append((100 - enemy.dist * 0.1, enemy))
                    continue
            if (math.isfinite(enemy.hp) and not self.near_sound
                    and all(i == enemy.id or distance(pos, point) > 150 and distance(enemy.pos, point) > 150
                            for i, point in self.known_enemies.items())
                    and self.can_open(enemy.id, pos) and enemy.hp < self.finish_damage(enemy, pos)):
                options.append((115 - enemy.dist * 0.1, enemy))
        if options:
            return sorted(options, key=lambda option: option[0], reverse=True)
        return [(50, self.farm)] if self.farm is not None and not self.farm_blocked else []

    def aim_for(self, weapon, target, base, muzzle, pitch_bounds):
        
        if target.kind != "mech" and weapon.get("kind") != "gun":
            return None
        return super().aim_for(weapon, target, base, muzzle, pitch_bounds)

    def contacts(self, obs, pos, eye):
        contacts = super().contacts(obs, pos, eye)
        self.exposed = any(c.kind == "mech" and c.clear and c.dist < 100 for c in contacts)
        if self.alive != 2 or self.disengage or self.single_escape:
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
            seen = self.last_seen.get(enemy.id)
            cube_edge = min(self.cube_count, 21) - min(limit(seen.cubes or 0, 0, 100), 21) if seen else self.cube_count
            advantage *= 1 + 0.022 * cube_edge
            if laser and not their_laser:
                advantage *= 1.45
            if "lightning" in enemy.armed and "lightning" not in self.kinds and enemy.dist < 55:
                advantage *= 0.65
            allowed = ((long_range and advantage >= 0.93)
                       or (enemy.dist >= 60 and advantage > 1.65)
                       or (enemy.dist < 40 and "lightning" in self.kinds and advantage > 1.3))
            if allowed:
                self.fight = enemy
                break
        return contacts

    def escape_facing(self):
        weighted = sorted(self.escape_bearings)
        if not weighted:
            return self.actual[0]
        yaw = weighted[0][1]
        if len(weighted) > 1:
            yaw = angle(yaw + angle(weighted[1][1] - yaw) * 0.5)
        return yaw

    def release_laser_safely(self, obs, action, pos):
        
        
        for index, weapon in enumerate(self.weapon_slots):
            if weapon.get("kind") != "laser" or number(weapon.get("charge")) <= 0 or action["fire"][index]:
                continue
            muzzle = raised(pos, self.phys("muzzle_height", 7, self.self_stats))
            yaw, pitch = self.actual
            for raw in (*seq(obs.get("mechs"))[:48], *seq(obs.get("crates"))[:36]):
                item = obj(raw)
                point = vec(item.get("pos"), 3)
                ident = number(item.get("id"), None)
                if point is None or ident in (self.slot, self.last_fire_target):
                    continue
                span = distance(muzzle, point)
                width = 3 + 0.13 * limit(number(item.get("cubes")), 0, 100)
                if (span <= 280 and abs(angle(yaw - bearing(muzzle, point))) <= math.atan2(width, span)
                        and point[2] - 1 <= muzzle[2] + span * math.tan(pitch) <= point[2] + 4 * width):
                    action["fire"][index] = True
                    action["aim"][1] = self.phys("max_pitch", 1.3, self.self_stats)
                    break

    def act(self, obs):
        errors = (ArithmeticError, LookupError, TypeError, ValueError, AttributeError)
        self.mode = "survive"
        self.weapon_point = self.loot_point = self.fight = self.farm = None
        self.climb = self.sprinting = False
        self.single_escape = False
        self.course = (0.0, 0.0)
        self.escape_bearings = []
        self.laser_response_pending = False
        self.nearby_take = (None, None)
        me = obj(obs.get("self"))
        now, pos = number(obs.get("t"), 0), vec(me.get("pos"), 3)
        self.actual = vec(me.get("aim"), 2) or (0, 0)
        self.self_stats = obj(me.get("stats"))
        offer = seq(obj(obs.get("offer")).get("choices"))[:3]
        try:
            if self.first_ffa_time is None:
                self.first_ffa_time = now
            self.opening = 0 <= now - self.first_ffa_time < 30
            items = seq(me.get("weapons"))
            self.weapon_slots = [obj(items[i]) if i < len(items) else {} for i in range(2)]
            self.kinds = {w.get("kind") for w in self.weapon_slots if w.get("kind") in duel_bot.KNOWN_WEAPONS}
            self.alive = number(obs.get("alive"), 16)
            self.hp = max(0, number(me.get("hp"), 0))
            self.hp_share = self.hp / max(1, number(me.get("max_hp"), 1400))
            self.cube_count = limit(number(me.get("cubes")), 0, 100)
            self.energy = limit(number(me.get("energy")), 0, 1000)
            self.record(obs, pos, now)
            if pos is not None:
                if FFA_PICKUP_TAPER or FFA_LASER_COVER:
                    self.laser_hits = self.laser_evidence(obs, pos, now)
                    self.laser_response_pending = bool(FFA_LASER_COVER and (
                        self.laser_hits or self.laser_cover is not None or now < self.laser_dodge_until))
                if FFA_PICKUP_TAPER:
                    self.pickup_clearances = self.pickup_threats(now)
                    self.pickup_retry = {ident: retry for ident, retry in self.pickup_retry.items() if retry > now}
                    self.nearby_take = self.nearby_weapon(pos)
                    self.nearby_cube = min(
                        (point for raw in seq(obs.get("cubes"))[:64]
                         if (point := vec(obj(raw).get("pos"), 3)) is not None
                         and abs(point[2] - pos[2]) <= FFA_PICKUP_NEAR_M
                         and distance_sq(pos, point) <= FFA_PICKUP_NEAR_M ** 2),
                        key=lambda point: distance_sq(pos, point), default=None)
                self.observe(me, pos, self.actual, now)
                
                self.hits.update({ident: when for ident, (when, _) in self.attackers.items()
                                  if 0 <= now - when < eb.HIT_MEMORY_S})
            self.last_fire_target = None
            action = super().act(obs)
            if pos is not None:
                if (self.disengage or self.single_escape) and self.last_fire_target is None and not self.laser_response_pending:
                    action["aim"] = [self.escape_facing(), 0.0]
                elif self.last_fire_target is None and self.weapon_point is not None and not self.exposed:
                    action["aim"] = [bearing(pos, self.weapon_point), 0.0]
                elif self.last_fire_target is None and now - self.last_damage >= eb.HIT_MEMORY_S:
                    if (FFA_PICKUP_TAPER and self.opening and self.kinds.isdisjoint(self.SECONDARIES)
                            and not self.farm_blocked and math.hypot(*self.course) > 0.2):
                        action["aim"] = [math.atan2(self.course[1], self.course[0]), 0.0]
                    elif not self.rivals:
                        action["aim"] = [angle(self.scout_yaw + now * 1.9), 0.0]
                action.setdefault("fire", [False, False])
                if self.mode in ("laser-cover", "laser-dodge") and math.hypot(*self.course) > 0:
                    for index, weapon in enumerate(self.weapon_slots):
                        if weapon.get("kind") == "laser":
                            action["fire"][index] = False
                if not self.single_escape:
                    self.release_laser_safely(obs, action, pos)
        except errors:
            try:
                self.duel.arena = self.arena
                action = self.duel.act(obs) or {}
                for key in ("fire", "take", "drop"):
                    action.pop(key, None)
            except errors:
                action = {}
        if FFA_PICKUP_TAPER and self.nearby_take[0] is not None:
            ident, swap = self.nearby_take
            action["take"] = ident
            if swap is None:
                action.pop("drop", None)
            else:
                action["drop"] = swap
        if offer:
            index = min(len(seq(me.get("upgrades"))), len(self.UPGRADES) - 1)
            rank = self.PLATING_FIRST if FFA_PLATING_FIRST and index == 0 else self.UPGRADES[index]
            def priority(i):
                upgrade = obj(offer[i]).get("id")
                if not isinstance(upgrade, str):
                    return 0
                if upgrade in rank:
                    return 200 - rank.index(upgrade)
                return eb.UPGRADE_RANK.get(upgrade, 0)
            action["pick"] = max(range(len(offer)), key=priority)
        return action


class PracticeRelay:
    ACTION_FIELDS = {"type", "tick", "move", "aim", "fire", "boost", "jump", "reload",
                     "pick", "take", "drop", "debug"}

    def __init__(self):
        self.child = None
        self.reaper = None
        self.kill_timer = None
        self.connected = False
        self.pending = deque()
        self.partial = b""
        self.discarding = False
        self.fallbacks = 0
        self.consecutive_fallbacks = 0

    def start(self, hello):
        deadline = time.perf_counter() + 8
        try:
            self.child = subprocess.Popen(
                ["./mechbot"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0, env={**os.environ, "MECHBOT_SALT": str(P4_SALT)},
            )
            self.reaper = threading.Thread(target=self.child.wait)
            self.reaper.start()
            os.set_blocking(self.child.stdin.fileno(), False)
            os.set_blocking(self.child.stdout.fileno(), False)
            self.connected = True
        except OSError as error:
            mf.log(f"Child could not start ({type(error).__name__})")
            self.stop()
            return
        self.pending.append(memoryview(hello))
        if self.exchange(deadline, None, 4096) is None:
            mf.log('m1')
            self.stop()

    @classmethod
    def matches(cls, line, tick):
        try:
            msg = json.loads(line.decode("utf-8"))
        except (ValueError, RecursionError):
            return False
        if not isinstance(msg, dict):
            return False
        if tick is None:
            return msg.get("type") == "ready"
        if (msg.get("type", "action") != "action" or type(msg.get("tick")) not in (int, float)
                or msg["tick"] != tick or not msg.keys() <= cls.ACTION_FIELDS):
            return False
        if any(name in msg and mf._pair(msg[name]) is None for name in ("move", "aim")):
            return False
        if "fire" in msg:
            fire = msg["fire"]
            if not isinstance(fire, list) or len(fire) != 2 or any(type(flag) is not bool for flag in fire):
                return False
        return (all(name not in msg or type(msg[name]) is bool for name in ("boost", "jump", "reload"))
                and all(name not in msg or type(msg[name]) in (int, float) and -1e15 <= msg[name] <= 1e15
                        for name in ("pick", "take", "drop"))
                and ("debug" not in msg or isinstance(msg["debug"], dict)))

    def read_lines(self, fd, limit):
        data = os.read(fd, 8192)
        if not data:
            self.connected = False
            return ()
        lines = (self.partial + data).split(b"\n")
        self.partial = lines.pop()
        if self.discarding and lines:
            del lines[0]
            self.discarding = False
        if self.discarding or len(self.partial) >= limit:
            self.partial = b""
            self.discarding = True
        return lines

    def exchange(self, deadline, tick, limit, refresh=None):
        if not self.connected:
            return None
        send_fd, recv_fd = self.child.stdin.fileno(), self.child.stdout.fileno()
        if self.partial:
            self.partial = b""
            self.discarding = True
        input_fd = None
        candidate = None
        try:
            while self.connected:
                if refresh is not None:
                    tick, deadline, input_fd = refresh()
                    if not self.connected:
                        break
                
                if candidate is not None:
                    if not self.pending and time.perf_counter() <= deadline:
                        return candidate
                    candidate = None
                remaining = max(0, deadline - time.perf_counter())
                sent = not self.pending
                readers = [recv_fd] if input_fd is None else [recv_fd, input_fd]
                readable, writable, _ = select.select(readers, [] if sent else [send_fd], [], remaining)
                if input_fd in readable:
                    continue
                if not readable and not writable:
                    if input_fd is not None and select.select([input_fd], [], [], 0)[0]:
                        continue
                    break
                if readable:
                    lines = self.read_lines(recv_fd, limit)
                    if sent:
                        for line in lines:
                            if (len(line) < limit and self.matches(line, tick)
                                    and time.perf_counter() <= deadline):
                                candidate = line + b"\n"
                                break
                    elif self.partial:
                        self.partial = b""
                        self.discarding = True
                if writable and self.connected:
                    frame = self.pending[0]
                    written = os.write(send_fd, frame)
                    if written == len(frame):
                        self.pending.popleft()
                    else:
                        self.pending[0] = frame[written:]
                if remaining == 0 and candidate is None:
                    if input_fd is not None and select.select([input_fd], [], [], 0)[0]:
                        continue
                    break
        except BlockingIOError:
            return None
        except OSError:
            self.connected = False
        return None

    def stop(self):
        child, self.child = self.child, None
        self.connected = False
        self.pending.clear()
        self.partial = b""
        if child is not None:
            child.terminate()
            child.stdin.close()
            child.stdout.close()
            if child.returncode is None:
                self.kill_timer = threading.Timer(0.1, child.kill)
                self.kill_timer.daemon = True
                self.kill_timer.start()

    def close(self):
        self.stop()
        if self.reaper is not None:
            self.reaper.join()
        if self.kill_timer is not None:
            self.kill_timer.cancel()

    def decide(self, bot, obs, raw, tick, received, frame_limit, pause_show, queued=None):
        def track(frame):
            try:
                now = bot.track_tick(obs)
            except Exception:
                return None
            if bot.mode == "free-for-all":
                self.stop()
            elif self.connected:
                self.pending.append(memoryview(frame))
            return now

        def refresh():
            nonlocal obs, tick, received, now
            if queued is not None:
                for next_obs, frame, next_tick, timestamp in queued.drain():
                    if self.connected and now is not None:
                        bot.practice.remember(obs, now)
                    obs, tick, received = next_obs, next_tick, timestamp
                    now = track(frame)
            return tick, received + P4_DEADLINE_MS / 1000, queued.fd if queued is not None else None

        now = track(raw)
        tick, child_deadline, _ = refresh()
        if now is not None and self.child is not None:
            payload = self.exchange(child_deadline, tick, frame_limit, refresh)
            if payload is not None:
                self.consecutive_fallbacks = 0
                bot.practice.remember(obs, now)
                return payload, received + P4_DEADLINE_MS / 1000 + mf.WRITE_RESERVE_S
            if self.child is not None:
                self.fallbacks += 1
                self.consecutive_fallbacks += 1
                if self.consecutive_fallbacks == 20:
                    self.stop()
        deadline = received + mf.DECISION_LIMIT_S
        if now is None:
            return None, deadline
        if bot.mode != "free-for-all":
            deadline = time.perf_counter() + mf.DECISION_LIMIT_S
        remaining = deadline - mf.WRITE_RESERVE_S - time.perf_counter()
        payload = (mf._watched(remaining, mf._decision, bot, obs, tick, pause_show, now)
                   if remaining > 0 else None)
        return payload, deadline


class Royale:
    def __init__(self, hello):
        duel_bot.SEED_SALT = 6
        self.practice = duel_bot.DuelBot(hello)
        self.practice.guarded = GUARDED_OPENER
        self.ffa = Selective(hello)
        self.detector = Detector(hello)
        self.mode = FORCE_MODE or "practice"
        self.first_ffa = None
        self.practice2 = None
        self.practice3 = None
        self.practice_fallbacks = 0
        if P_DRIVER in (2, 3, 4) and self.mode == "practice":
            try:
                if P_DRIVER == 2:
                    from practice2 import Practice
                else:
                    from practice3 import Practice
            except ImportError:
                mf.log(f"driver {min(P_DRIVER, 3)} unavailable")
            else:
                driver = Practice(hello, SEED)
                if P_DRIVER == 2:
                    self.practice2 = driver
                else:
                    self.practice3 = driver

    def __getattr__(self, name):
        if name in ("practice", "practice2", "practice3", "ffa", "detector", "mode", "first_ffa"):
            raise AttributeError(name)
        if self.mode == "free-for-all":
            return getattr(self.ffa, name)
        return getattr(self.practice2 or self.practice3 or self.practice, name)

    def load_map(self):
        if self.practice2 is not None:
            self.practice2.load_map()
        self.practice.load_map()
        self.ffa.arena = self.practice.arena
        if self.practice3 is not None:
            self.load_practice3_map()
        return True

    def load_practice3_map(self):
        from json import loads
        from pathlib import Path

        try:
            directory = self.practice.map_dir
            if isinstance(directory, str) and directory and len(directory) < 2048:
                root = Path(directory) / "v2"
                data = loads(eb.read_map_file(root / "world.json"))
                self.practice3.load_map(data, eb.read_map_file(root / "terrain.i16"))
            else:
                self.practice3.load_map()
        except Exception as error:
            mf.log(f"practice3 map: {type(error).__name__}")

    def track_tick(self, obs):
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
                mf.log(f"mode {want}")
        if self.mode != "free-for-all":
            self.ffa.record(obs, vec(obj(obs.get("self")).get("pos"), 3), now)
        return now

    def act(self, obs, now=None):
        obs = obj(obs)
        if now is None:
            now = self.track_tick(obs)
        if self.mode == "free-for-all":
            return self.ffa.act(obs)
        driver = self.practice2 or self.practice3
        if driver is not None:
            try:
                action = driver.act(obs)
                if driver is self.practice3:
                    self.practice.remember(obs, now)
                return action
            except Exception as error:
                self.practice_fallbacks += 1
                name = "practice3" if driver is self.practice3 else "practice2"
                mf.log(f"{name} fallback {self.practice_fallbacks}: {type(error).__name__}")
                try:
                    return self.practice.act(obs)
                except Exception:
                    return {"aim": driver.last_aim}
        return self.practice.act(obs)


def main():
    if P_DRIVER == 4 and FORCE_MODE != "free-for-all":
        relay = PracticeRelay()
        try:
            mf.run(Royale, pause_show=PAUSE_SHOW, raw_wire=relay)
        finally:
            relay.close()
    else:
        mf.run(Royale, pause_show=PAUSE_SHOW, practice_wire=P_DRIVER == 2 and FORCE_MODE != "free-for-all")


if __name__ == "__main__":
    main()
