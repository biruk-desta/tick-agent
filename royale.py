
import mechfight as mf
import example_bot as eb
import duel_bot
import heapq
import json
import math
import os
import select
import subprocess
import threading
import time
import zlib
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

eb.PLAN_BUDGET_S = 0.010
eb.ROUTE_SLICE_S = 0.004
from example_bot import obj, seq, number, vec, distance, bearing, angle, limit, raised

SEED = 6                    
P_DRIVER = 5
P4_SALT = 0
P4_ENV = {}
P4_DEADLINE_MS = 30
P5_GROUPS = 8
P5_TABLE = {0: (6, 0, 'u1'),
 1: (6, 0, 'u1'),
 2: (6, 0, 'u1'),
 3: (6, 0, 'u1'),
 4: (6, 0, 'u1'),
 5: (6, 0, 'u1'),
 6: (6, 0, 'u1'),
 7: (6, 0, 'u1')}
P6_ENV = {}
P6_PRESET = None
P7_ENV = {}
P7_PRESET = None
FORCE_MODE = None           
T_FFA = None
USE_Z = False
Z_SPLIT_S = 57.5
Z_ONLY = True               
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
FFA_BASELINE = True
F8_UNSTICK = True
F8_BREAK_SIGHT = True
F8_LASER_SCREEN = True
F8_CIRCLE_COVER = True

F8_MOVE_WINDOW = 3.0
F8_MOVE_MIN = 1.5
F8_HOLD_SAFE = 15.0
F8_ZONE_FIRST = 12.0
F8_HIT_WINDOW = 6.0
F8_QUIET = 5.0
F8_CLEAR_RANGE = 120.0
F8_LASER_RANGE = 90.0
F8_CIRCLE_LEAD = 10.0
F8_FFA_BUDGET = 0.0042

F9_NO_QUIET = True
F9_SECOND_LANE = True
F9_WEAK_SPACING = True
F9_HOLD_TRADE = True
F9_SUPPLY_RESET = False

F9_FRESH_S = 0.5
F9_LANE_M = 160.0
F9_AIM_RAD = math.radians(15)
F9_TRADE_S = 5.0
F9_TRADE_MIN_M = 30.0
F9_FINISH_HP = 0.30
F9_HP_METRES = 0.20
F9_RANGES = {"gun": 230, "laser": 280, "lightning": 45, "mortar": 170}

F10_OPENER = False
F10_T0_S = 45.0
F10_T0_MODE = "practice"
F10_P_MIN_S = 6.0
F10_P_HUNTERS = 3
F10_P_HOLD_S = 1.5
F10_ECONOMY = True
F10_AMBUSH = False
F10_DUEL = True
F10_CHARGE_DODGE = True

F16_UNDERFIRE = True
F16_NOQUIET = True
F16_DRONE = True
F16_RETURN = True
F16_RUSH = True

F16_HIT_S = 4.0
F16_BOOST_S = 2.0
F16_DRONE_S = 2.0
F16_DRONE_HOLD_S = 6.0
F16_DRONE_DEAD_HP = 135.0
F16_CUBE_ROUTE_M = 15.0
F16_CUBE_GRAVE_M = 8.0
F16_CUBE_S = 8.0
F16_RETURN_S = 3.0
F16_RETURN_REACH = 0.8
F16_RUSH_M = 70.0
F16_RUSH_FALL_M = 3.0
F16_RUSH_S = 6.0
F16_RUSH_END_M = 110.0
F16_RUSH_RETRY_S = 0.5
F16_FINAL_M = 60.0

F18_COVER = False
F18_BREAK = True
F18_QUIET = True
F18_NEAR = True

F18_WINDOW_S = 60.0
F18_HIT_S = 1.0
F18_PAIR_S = 10.0
F18_CLOSE_M = 70.0
F18_CLOSE_RATE = 2.0
F18_INWARD = 4.0
F18_WARN_M = 120.0
F18_WARN_RATE = 6.0
F18_WARN_AIM = math.radians(30)
F18_WARN_HOLD_S = 0.5
F18_HIDDEN_S = 1.0
F18_CALM_S = 2.0
F18_LOST_S = 5.0
F18_ROUTE_M = 120.0
F18_RINGS = (3, 6, 10, 14, 19, 25, 32, 40, 50, 62, 76, 92, 108, 120)
F18_DIRECTIONS = 16
F18_LEAD_S = 0.5
F18_REPLAN_S = 0.2
F18_MOVED_M = 6.0
F18_PLAN_S = 0.0007
F18_PLAN_RAYS = 60
F18_EXPOSE_BIN = 0.25
F18_ZONE_M = 3.0
F18_PURSUIT = 22.0
F18_STANDOFF_M = 20.0
F18_VIA_M = 62
F18_VIA_TRIES = 4
F18_FIELD_M = 8.0
F18_FLOOD_S = 0.0005
F18_PATH_STEP = 2
F18_STEER_TRIES = 6
F18_OTHERS = 2
F18_HORIZON_S = 2.0
F18_FALLBACK_S = 0.0004
F18_QUIET_HIT_S = 10.0
F18_QUIET_M = 70.0
F18_QUIET_AIM = 0.5
F18_NEAR_M = 25.0
F18_NEAR_COST = 0.3
F18_NEAR_CAP = 18.0
F18_OPEN_M = 45.0
F18_STILL_S = 2.0
F18_NEAR_SEARCH = (10, 20, 30)
F18_NEAR_HOLD_S = 4.0

F20_ENDGAME = True
F20_DUEL = True
F20_USE2 = True
F20_FINISH = False
F20_SCAV = False

F20_AFTER_S = 60.0
F20_STOP_M = 45.0
F20_STOP_ARC_M = 25.0
F20_HOLD_M = 6.0
F20_ZONE_M = 4.0
F20_PATH_CUBE_M = 10.0
F20_SOUND_S = 5.0
F20_REACH_GUN_M = 90.0
F20_REACH_ARC_M = 38.0
F20_HOP_GAIN_M = 8.0
F20_REPLAN_S = 0.5
F20_HOP_S = 0.0003
F20_HOP_RAYS = 24
F20_LOSS_S = 3.0
F20_LOSS_HP = 30.0
F20_FINISH_HP = 0.35
F20_FINISH_S = 5.0
F20_FINISH_BAN_S = 10.0
F20_LANE_M = 120.0
F20_RETURN_S = 3.0
F20_SCAV_EXTRA_M = 60.0
F20_SCAV_REACH_M = 90.0
F20_SCAV_HP = 0.6
F20_SCAV_SPARE_S = 5.0
F20_SCAV_HIT_S = 5.0
F20_ARC_ENERGY = 4.0

F21_ZONE = True
F21_STUCK_S = 2.0
F21_STUCK_M = 1.5
F21_FREE_M = 2.5
F21_JUMP_S = 1.5
F21_STRAFE_S = 1.5
F21_JET_S = 0.9
F21_STRAFE = 1.2
F21_TURN = 0.5
F21_EDGE_S = 10.0
F21_NODES = 24000
F21_NODES_TICK = 700
F21_CLIMB_M = 6.0
F21_CLIMB_COST = 6.0
F21_NARROW_COST = 30.0
F21_BLOCKS = 16
F21_CLIMB_ENERGY = 40.0
F21_KEEP_M = 20.0
F21_BASE_S = 10.0

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


def ffa_enabled(*rules):
    return not FFA_BASELINE and any(rules)


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


class PracticeEvidence:
    

    AIM = math.radians(15)
    HIT_AIM = math.radians(6)

    def __init__(self, hello):
        config = obj(hello.get("config"))
        self.slot = number(hello.get("slot"), -1)
        match = obj(config.get("match"))
        self.gap = max(0.25, 2.5 * number(match.get("decide_every"), 2)
                       / max(1, number(match.get("tick_hz"), 20)))
        self.muzzle = number(obj(config.get("mech")).get("muzzle_height"), 7)
        self.eye = number(obj(config.get("mech")).get("eye_height"), 8)
        self.scale = number(obj(config.get("cubes")).get("size_per_cube"), 0.05)
        vision = obj(config.get("vision"))
        self.reach = number(vision.get("range"), 200)
        self.near = number(vision.get("near_range"), 45)
        self.half_fov = math.radians(number(vision.get("fov_deg"), 120) / 2)
        self.hunters = {}
        self.passive_pairs = {}
        self.last_hit = None
        self.hp = {}
        self.previous = -math.inf
        self.blocked = False

    @staticmethod
    def closing(a, b, av, bv):
        dx, dy = b[0] - a[0], b[1] - a[1]
        return ((av[0] - bv[0]) * dx + (av[1] - bv[1]) * dy) / max(1, math.hypot(dx, dy))

    @staticmethod
    def error(origin, aim, point):
        if aim is None:
            return math.inf
        return max(abs(angle(aim[0] - bearing(origin, point))),
                   abs(aim[1] - math.atan2(point[2] - origin[2], distance(origin, point))))

    def update(self, obs, now, death_deficit, arena):
        if self.blocked or death_deficit > 0:
            self.blocked = True
            return False
        me = obj(obs.get("self"))
        pos = vec(me.get("pos"), 3)
        if pos is None:
            self.hunters.clear()
            return False
        vel = vec(me.get("vel"), 3) or eb.ZERO
        scale = 1 + self.scale * limit(number(me.get("cubes")), 0, 100)
        chest = raised(pos, 4.8 * scale)
        eye = raised(pos, number(obj(me.get("stats")).get("eye_height"), self.eye * scale))
        own_aim = vec(me.get("aim"), 2)
        sensors = seq(me.get("upgrades")).count("sensors")
        if not 0 <= now - self.previous <= self.gap:
            self.hunters.clear()
            self.passive_pairs.clear()
            self.hp.clear()
        self.previous = now
        tracks, hp = {}, {}
        for raw in seq(obs.get("mechs"))[:48]:
            rival = obj(raw)
            ident, point = number(rival.get("id"), -1), vec(rival.get("pos"), 3)
            if (rival.get("kind") != "mech" or ident not in range(16) or ident == self.slot
                    or point is None or number(rival.get("hp"), 1) <= 0):
                continue
            scale = 1 + self.scale * limit(number(rival.get("cubes")), 0, 100)
            hp[ident] = number(rival.get("hp"), math.inf)
            tracks[ident] = (point, raised(point, self.muzzle * scale), raised(point, 4.8 * scale),
                             vec(rival.get("vel"), 3) or eb.ZERO, vec(rival.get("aim"), 2),
                             rival.get("charging") is True, 2.5 * scale, 9 * scale)
        zone = obj(obs.get("zone"))
        center = vec(zone.get("center"), 2)
        radius = number(zone.get("radius"))
        losses = {ident for ident, value in hp.items()
                  if value < self.hp.get(ident, value) and center is not None
                  and distance_sq(tracks[ident][0], center) <= radius ** 2}
        if losses:
            losses.difference_update(event.get("target") for raw in seq(obs.get("events"))[:200]
                                     if (event := obj(raw)).get("type") == "hit"
                                     and type(event.get("target")) in (int, float))
        self.hp = hp
        
        for raw in seq(obs.get("beams"))[:32]:
            beam = obj(raw)
            path = seq(beam.get("path"))
            shooter = number(beam.get("by"), -1)
            if shooter not in range(16) or shooter == self.slot:
                continue
            for node in path[1:8]:
                point = vec(node, 3)
                if point is not None and any(
                        ident != shooter and distance_sq(point, base) <= (radius + 0.75) ** 2
                        and base[2] - 0.5 <= point[2] <= base[2] + height + 0.5
                        for ident, (base, _, _, _, _, _, radius, height) in tracks.items()):
                    self.blocked = True
                    return False
        chasing, visible = {}, {}
        for ident, (base, origin, body, speed, aim, charging, _, height) in tracks.items():
            our_error = self.error(origin, aim, chest)
            span = distance(pos, base)
            closing = (self.closing(base, pos, speed, vel) > 2
                       and self.closing(base, pos, speed, eb.ZERO) > 2)
            if (span <= min(220, self.reach + 25 * sensors)
                    and (own_aim is None or span <= self.near + 15 * sensors
                         or abs(angle(own_aim[0] - bearing(pos, base))) <= self.half_fov)
                    and (arena is None or arena.clear_ray(eye, body) or arena.clear_ray(eye, raised(base, height)))):
                visible[ident] = base, origin, body, aim, charging
                if closing or our_error <= self.AIM:
                    chasing[ident] = self.hunters.get(ident, now)
            for other, (target, _, body, target_speed, target_aim, _, _, _) in tracks.items():
                if other == ident:
                    continue
                span = distance_sq(base, target)
                if span > (280 if charging or other in losses else 120) ** 2:
                    continue
                error = self.error(origin, aim, body)
                hostile_charge = charging and error <= self.AIM and error < our_error
                possible_hit = other in losses and error <= self.HIT_AIM and error < our_error
                convergence = (span <= 120 ** 2 and error <= self.AIM and error < our_error
                               and self.closing(base, target, speed, target_speed) > 2
                               and (self.closing(base, target, speed, eb.ZERO) > 2
                                    or self.error(body, target_aim, origin) <= self.AIM))
                if (hostile_charge or possible_hit or convergence) and (arena is None or arena.clear_ray(origin, body)):
                    self.blocked = True
                    return False
        self.hunters = chasing
        sustained = sum(now - since + 1e-9 >= F10_P_HOLD_S for since in chasing.values())
        if now >= F10_P_MIN_S and sustained >= F10_P_HUNTERS:
            return True
        for raw in seq(obs.get("events"))[:200]:
            source = mech_attacker(obj(raw), self.slot)
            if source is not None:
                self.last_hit = source, now
        return self.passive_pursuit(visible, chasing, losses, now, arena)

    def passive_pursuit(self, visible, chasing, losses, now, arena):
        previous, self.passive_pairs = self.passive_pairs, {}
        if len(chasing) != 1 or len(visible) < 4 or arena is None:
            return False
        hunter, since = next(iter(chasing.items()))
        passive = [(ident, track) for ident, track in visible.items() if ident != hunter]
        witnessed = set()
        for index, (ident, (base, origin, body, aim, charging)) in enumerate(passive):
            for other, (target, muzzle, target_body, target_aim, target_charging) in passive[index + 1:]:
                if distance_sq(base, target) > min(45, self.near) ** 2:
                    continue
                if (aim is None or target_aim is None or charging or target_charging
                        or ident in losses or other in losses
                        or self.error(origin, aim, target_body) <= self.AIM
                        or self.error(muzzle, target_aim, body) <= self.AIM):
                    self.passive_pairs.clear()
                    return False
                if not (arena.clear_ray(origin, target_body) and arena.clear_ray(muzzle, body)):
                    continue
                pair = tuple(sorted((ident, other)))
                started = self.passive_pairs[pair] = previous.get(pair, now)
                if now - started + 1e-9 >= 3:
                    witnessed.update(pair)
        return (now >= F10_P_MIN_S and now - since + 1e-9 >= max(3, F10_P_HOLD_S)
                and self.last_hit is not None and self.last_hit[0] == hunter
                and now - self.last_hit[1] <= 3 and len(witnessed) >= 3)


class Observer(NamedTuple):
    pos: tuple
    eye: tuple
    facing: tuple | None
    wedge_weight: float


class Peek:
    def __init__(self, target, cover, firing_pos, now):
        self.target = target
        self.cover = cover
        self.firing_pos = firing_pos
        self.phase = "cover"
        self.until = now + 2.3
        self.damage_out = self.damage_in = 0
        self.released = -math.inf


class ChargeWarning:
    def __init__(self, shooter, yaw, origin, heard_at, now):
        self.shooter = shooter
        self.yaw = yaw
        self.origin = origin
        self.heard_at = heard_at
        self.until = now + 1.5
        self.cover = None
        self.side = 1


class ChargingRival(NamedTuple):
    origin: tuple
    bearing: float
    distance: float
    aim_error: float
    heading: float


class ClimbSearch:
    def __init__(self, arena, start, end, radius, blocked=(), circle=None):
        self.arena, self.start, self.end, self.radius = arena, start, end, radius
        self.blocked = frozenset(blocked)
        self.circle = circle
        self.destination = arena.point(end) if circle is None else circle[0]
        self.reach = 0.0 if circle is None else circle[1]
        self.queue = [(0, 0, start)]
        self.parent = {start: None}
        self.cost = {start: 0}
        self.total = 0
        self.done = False

    def advance(self, until):
        arena, w, h, roof = self.arena, self.arena.w, self.arena.h, self.arena.roof
        for _ in range(F21_NODES_TICK):
            if self.total >= F21_NODES or not self.queue:
                self.done = True
                return ()
            if time.perf_counter() >= until:
                break
            self.total += 1
            _, negative, current = heapq.heappop(self.queue)
            g = -negative
            if g > self.cost[current]:
                continue
            if current == self.end or (self.circle is not None and arena.ground_ok(current, self.radius)
                                       and distance(arena.point(current), self.destination) <= self.reach):
                path = []
                while current != self.start:
                    path.append(arena.point(current))
                    current = self.parent[current]
                self.done = True
                return tuple(reversed(path))
            y, x = divmod(current, w)
            for dx, dy in eb.NEIGHBORS:
                if not (1 <= x + dx < w - 1 and 1 <= y + dy < h - 1):
                    continue
                n = current + dy * w + dx
                rise = roof[n] - roof[current]
                if rise > F21_CLIMB_M or n in self.blocked:
                    continue
                cost = g + (1.414 if dx and dy else 1.0)
                if not arena.ground_ok(n, self.radius):
                    cost += F21_NARROW_COST if arena.clearance[n] else F21_CLIMB_COST
                if rise > arena.step_up:
                    cost += F21_CLIMB_COST
                if cost < self.cost.get(n, math.inf):
                    self.cost[n] = cost
                    self.parent[n] = current
                    heuristic = max(0.0, distance(arena.point(n), self.destination) - self.reach) / eb.GRID_M
                    heapq.heappush(self.queue, (cost + heuristic, -cost, n))
        return ()


class Selective(eb.Bot):
    SEPARATION = 145.0
    CHARGE_AIM_RAD = math.radians(15)
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
    ECONOMY_UPGRADES = ("plating", "laser_damage", "laser_charge", "armor", "nanites", "servos", "gyros")
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
        self.opener_undecided = False
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
        self.f8_hits = {}
        self.f8_last_hit = -math.inf
        self.f8_attacker = None
        self.f8_motion = deque()
        self.f8_recovery = None
        self.f8_replan_at = -math.inf
        self.f8_cached = None
        self.f8_failed_circle = None
        self.f8_rotation = None
        self.f9_shots = {}
        self.f9_rivals = {}
        self.f9_aim_since = {}
        self.f9_trades = {}
        self.f9_trade_tracks = {}
        self.f9_drop_config = obj(obj(hello.get("config")).get("drops"))
        self.f9_front_half_arc = math.radians(limit(self.phys("front_arc_deg", 180), 0, 360)) / 2
        self.f9_ranges = {kind: number(obj(self.weapon_config.get(kind)).get("range"), reach)
                          for kind, reach in obj(F9_RANGES).items()}
        self.ambush = self.duel_peek = None
        self.ambush_retry = -math.inf
        sound = obj(obj(hello.get("config")).get("sound"))
        self.charge_sound_tolerance = math.radians(2 * limit(number(sound.get("bearing_noise_deg"), 7), 1, 30))
        self.last_charge_sound = -math.inf
        self.charge_warning = None
        self.charge_handled = {}
        self.charge_started = {}
        self.f16_hits = {}
        self.f16_ranges = {}
        self.f16_drone = self.f16_drone_last = self.f16_grave = None
        self.f16_rush = self.f16_rusher = self.f16_cover = None
        self.f16_cover_retry = -math.inf
        self.f16_unquiet = False
        self.f18_tracks = {}
        self.f18_warn_since = {}
        self.f18_vel = {}
        self.f18_threat = self.f18_trigger = None
        self.f18_started = None
        self.f18_stopped = -math.inf
        self.f18_hidden_since = None
        self.f18_cover = self.f18_best = self.f18_search = self.f18_epoch = None
        self.f18_rays = 0
        self.f18_field = self.f18_flooding = self.f18_legs_now = None
        self.f18_flood_until = -math.inf
        self.f18_until = -math.inf
        self.f18_alarm = False
        self.f18_aim = None
        self.f18_prev_target = None
        self.f18_still = self.f18_near_point = None
        self.f18_near_until = -math.inf
        self.f21_track = deque()
        self.f21_blocked = deque(maxlen=F21_BLOCKS)
        self.f21_moving_since = self.f21_stuck_at = self.f21_search = self.f21_failed = None
        self.f21_path = self.f21_path_goal = self.f21_climb = self.f21_base_failed = None
        self.f21_attempts = 0
        self.f21_jump_at = self.f21_replanned = -math.inf
        self.f21_turn = 0.0
        self.f21_hurry = self.f21_hard = self.f21_inside = False
        self.f20_hp = {}
        self.f20_dealt = deque()
        self.f20_hits = {}
        self.f20_finish = None
        self.f20_banned = {}
        self.f20_epoch = self.f20_search = self.f20_best = None
        self.f20_scav_ban = {}
        self.f20_scav_goal = None
        self.f20_reset()

    def f20_reset(self):
        self.f20_duel = self.f20_moving = False
        self.f20_enemy = self.f20_point = self.f20_dest = self.f20_id = None
        self.f20_target = None
        self.f20_cubes = ()
        self.f20_lanes = 0

    def record(self, obs, pos, now):
        
        kills = set()
        break_sight = ffa_enabled(F8_BREAK_SIGHT)
        if break_sight:
            self.f8_hit_sources = set()
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
            if (F16_UNDERFIRE and kind == "damaged" and event.get("weapon") != "zone"
                    and number(event.get("amount")) > 0):
                ident = number(event.get("by"), None)
                if ident is not None and ident >= 0 and ident != self.slot and (
                        ident in self.f16_hits or len(self.f16_hits) < 64):
                    self.f16_hits[ident] = now, event.get("weapon")
            source = mech_attacker(event, self.slot)
            if break_sight:
                if kind == "damaged" and number(event.get("amount")) > 0:
                    self.f8_last_hit = now
                if source is not None:
                    _, previous = self.f8_hits.get(source, (-math.inf, -math.inf))
                    self.f8_hits[source] = previous, now
                    self.f8_hit_sources.add(source)
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
        if not (FFA_WEDGE or FFA_NOT_NEAREST or FFA_UNSEEN_OPEN or FFA_QUIET_WALK
                or ffa_enabled(F10_OPENER, F10_ECONOMY, F10_AMBUSH, F10_DUEL)):
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

    def walk_quietly(self, pos, urgent=False, in_zone=True):
        if not FFA_QUIET_WALK or (ffa_enabled(F9_NO_QUIET) and (urgent or not in_zone)):
            return False
        if F21_ZONE and not self.opener_undecided and (urgent or not in_zone or self.f21_hurry
                                                       or self.f21_stuck_at is not None):
            return False
        if any(distance_sq(pos, enemy.pos) <= 120 ** 2 for enemy in self.observers.values()):
            return False
        pickup = self.weapon_point or self.loot_point
        if pickup is not None:
            race_limit = 1.5 ** 2 * distance_sq(pos, pickup)
            if any(distance_sq(enemy.pos, pickup) < race_limit for enemy in self.observers.values()):
                return False
        quiet = not any(self.line_to_self(ident, enemy, pos) for ident, enemy in self.observers.items())
        if quiet and self.f16(F16_NOQUIET) and 0 <= self.f8_now - self.last_damage <= F16_HIT_S:
            self.f16_unquiet = True
            return False
        return quiet

    def f16(self, rule):
        return F16_UNDERFIRE and rule and not self.opener_undecided

    def f16_scan(self, contacts, pos):
        now = self.f8_now
        self.f16_hits = {ident: entry for ident, entry in self.f16_hits.items() if 0 <= now - entry[0] <= 10}
        gun = next((w for w in self.weapon_slots if w.get("kind") == "gun"), None)
        gun_range = self.weapon_setting(gun, "range", 230) if gun is not None else 0
        self.f16_rusher = rusher = drone = None
        visible = set()
        for c in contacts:
            visible.add(c.id)
            if c.kind == "npc":
                if not self.f16(F16_DRONE) or c.hp <= 0:
                    continue
                when, weapon = self.f16_hits.get(c.id, (-math.inf, None))
                engaged = c.id == self.f16_drone and now - when <= F16_DRONE_HOLD_S
                if engaged or (weapon == "npc" and now - when <= F16_DRONE_S):
                    if drone is None or engaged or (drone.id != self.f16_drone and c.dist < drone.dist):
                        drone = c
                continue
            if c.kind != "mech" or not self.f16(F16_RUSH):
                continue
            track = self.f16_ranges.setdefault(c.id, deque())
            track.append((now, c.dist))
            while len(track) > 1 and now - track[1][0] >= 1.0:
                track.popleft()
            if (c.clear and c.dist < F16_RUSH_M and c.id not in self.eliminated
                    and now - track[0][0] >= 0.9 and track[0][1] - c.dist >= F16_RUSH_FALL_M
                    and (rusher is None or c.dist < rusher.dist)):
                rusher = c
        self.f16_ranges = {ident: track for ident, track in self.f16_ranges.items() if ident in visible}

        if self.f16_drone is not None and (drone is None or drone.id != self.f16_drone):
            last = self.f16_drone_last
            if self.f16_drone not in visible and last is not None and last[1] <= F16_DRONE_DEAD_HP:
                self.f16_grave = last[0], now + F16_CUBE_S
            self.f16_drone = self.f16_drone_last = None
        if drone is not None:
            self.f16_drone, self.f16_drone_last = drone.id, (drone.pos, drone.hp)
            self.f16_drone_target = drone if drone.clear and drone.dist <= gun_range else None
        else:
            self.f16_drone_target = None

        if self.f16_rush is not None:
            ident, started = self.f16_rush
            current = next((c for c in contacts if c.id == ident and c.kind == "mech"), None)
            if (current is None or ident in self.eliminated or now - started >= F16_RUSH_S
                    or current.dist >= F16_RUSH_END_M):
                self.f16_rush = self.f16_cover = None
            else:
                self.f16_rusher = current
        if self.f16_rush is None and rusher is not None and self.kinds == {"gun"}:
            self.f16_rush, self.f16_rusher = (rusher.id, now), rusher
            self.f16_cover, self.f16_cover_retry = None, -math.inf

    def f16_gunners(self, pos, now):
        gun = next((w for w in self.weapon_slots if w.get("kind") == "gun"), None)
        reach = F16_RETURN_REACH * (self.weapon_setting(gun, "range", 230) if gun is not None else 0)
        for ident, (when, weapon) in sorted(self.f16_hits.items(), key=lambda item: -item[1][0]):
            if weapon != "gun" or not 0 <= ident < 16 or ident in self.eliminated or now - when > F16_RETURN_S:
                continue
            seen = self.last_seen.get(ident)
            if seen is not None and seen.time >= when - 1:
                if distance(pos, seen.pos) <= reach:
                    yield ident, seen.pos
            else:
                _, estimate = self.attackers.get(ident, (-math.inf, None))
                if estimate is not None:
                    yield ident, estimate

    def f16_cube(self, pos, waypoint, zone):
        grave = self.f16_grave
        if grave is None or zone.now >= grave[1]:
            self.f16_grave = None
            return None
        goal = self.f8_goal if self.f8_goal is not None else waypoint
        best = None
        for raw in seq(self.f16_cubes)[:64]:
            point = vec(obj(raw).get("pos"), 3)
            if point is None or distance(point, grave[0]) > F16_CUBE_GRAVE_M or zone.gap(point, 2) < 0:
                continue
            off = min(segment_distance_sq(pos, goal, point), segment_distance_sq(pos, waypoint, point))
            if off <= F16_CUBE_ROUTE_M ** 2 and (best is None or distance_sq(pos, point) < best[0]):
                best = distance_sq(pos, point), point
        return best[1][:2] if best is not None else None

    def f16_rush_move(self, pos, vel, zone, threats, hazards, stats, grounded, energy, now, until,
                      in_zone, terminal_burn):
        rusher = self.f16_rusher
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        boost = limit(self.phys("boost_speed", 19.5, stats), walk, 90)
        sprint = grounded and energy > eb.BOOST_RESERVE
        origin = self.shooter_origin(rusher.id) or raised(rusher.pos, 7 * rusher.scale)
        cover = self.f16_cover
        if cover is not None and not self.f8_blocked(origin, cover):
            cover = self.f16_cover = None
        if cover is None and now >= self.f16_cover_retry and self.arena is not None:
            left = max(0, self.f16_rush[1] + F16_RUSH_S - now)
            drain = limit(self.phys("boost_drain", 17, stats), 0.1, 500)
            burst = limit((energy - eb.BOOST_RESERVE) / drain, 0, left) if sprint else 0
            reach = burst * boost + (left - burst) * walk
            cover = self.f10_find_cover(pos, zone, rusher, radius, reach,
                                        min(until, time.perf_counter() + 0.0025), silent=True, next_ring=False)
            self.f16_cover = cover
            if cover is None:
                self.f16_cover_retry = now + F16_RUSH_RETRY_S
        if cover is not None:
            move = self.move_to_laser_cover(pos, cover, boost if sprint else walk, sprint)
            self.mode = "rush-cover"
            return move
        away = bearing(rusher.pos, pos)
        point = pos[0] + 30 * math.cos(away), pos[1] + 30 * math.sin(away)
        move = super().movement(pos, vel, point, zone, False, True, threats, hazards, None, stats, grounded,
                                energy, now, until, in_zone, terminal_burn, None)
        move["boost"] = sprint and not move.get("jump") and math.hypot(*move["move"]) > 0.2
        self.mode = "rush-away"
        return move

    def f18(self, rule):
        return F18_COVER and rule and not self.opener_undecided

    def f18_scan(self, contacts, pos):
        now = self.f8_now
        window = now <= F18_WINDOW_S
        visible, alarms = set(), []
        for c in contacts:
            if c.kind != "mech" or c.id in self.eliminated:
                continue
            visible.add(c.id)
            track = self.f18_tracks.setdefault(c.id, deque())
            track.append((now, c.dist, c.pos))
            while len(track) > 1 and now - track[1][0] >= 1.0:
                track.popleft()
            then, span, old = track[0]
            age = now - then
            self.f18_vel[c.id] = (((c.pos[0] - old[0]) / age, (c.pos[1] - old[1]) / age) if age >= 0.3
                                  else (c.vel[0], c.vel[1]))
            if not window or not c.clear or age < 0.45:
                self.f18_warn_since.pop(c.id, None)
                continue
            closing = (span - c.dist) / age
            dx, dy = pos[0] - c.pos[0], pos[1] - c.pos[1]
            inward = ((c.pos[0] - old[0]) * dx + (c.pos[1] - old[1]) * dy) / (max(1e-6, math.hypot(dx, dy)) * age)
            close = c.dist <= F18_CLOSE_M and age >= 0.9 and closing >= F18_CLOSE_RATE and inward >= F18_INWARD
            warn = (c.dist <= F18_WARN_M and closing >= F18_WARN_RATE and inward >= F18_INWARD
                    and c.face_error <= F18_WARN_AIM)
            if warn:
                warn = now - self.f18_warn_since.setdefault(c.id, now) >= F18_WARN_HOLD_S - 1e-6
            else:
                self.f18_warn_since.pop(c.id, None)
            if close or warn:
                alarms.append((c.dist, c.id, "close" if close else "warning"))
        self.f18_tracks = {i: t for i, t in self.f18_tracks.items() if i in visible}
        self.f18_warn_since = {i: t for i, t in self.f18_warn_since.items() if i in visible}
        self.f18_vel = {i: v for i, v in self.f18_vel.items() if i in visible or i == self.f18_threat}
        self.f18_alarm = bool(alarms)
        if self.f18(F18_BREAK):
            self.f18_update(pos, now, window, min(alarms) if alarms else None)
            self.f18_prepare(pos, contacts)

    def f18_update(self, pos, now, window, alarm):
        hits = sorted((when, ident) for ident, (when, _) in self.attackers.items()
                      if 0 <= now - when <= F18_HIT_S and when > self.f18_stopped and ident not in self.eliminated)
        ident = self.f18_threat
        if ident is not None:
            if hits and hits[-1][1] != ident and self.f18_threat_pos(hits[-1][1]) is not None:
                self.f18_start(hits[-1][1], "hit", now)
            elif self.f18_done(pos, now):
                self.f18_threat = None
                self.f18_stopped = now
                self.f18_cover = self.f18_best = self.f18_search = self.f18_epoch = None
            return
        if not window or self.kinds != {"gun"}:
            return
        recent = sorted((when, i) for i, (when, _) in self.attackers.items() if 0 <= now - when <= F18_PAIR_S)
        alive = [item for item in recent if item[1] not in self.eliminated]
        if hits:
            self.f18_start(hits[-1][1], "hit", now)
        elif alarm is not None:
            self.f18_start(alarm[1], alarm[2], now)
        elif len(recent) >= 2 and alive and recent[-1][0] > self.f18_stopped:
            self.f18_start(alive[-1][1], "pair", now)

    def f18_start(self, ident, trigger, now):
        if self.f18_threat_pos(ident) is None:
            return
        self.f18_threat, self.f18_trigger, self.f18_started = ident, trigger, now
        self.f18_hidden_since = None
        self.f18_cover = self.f18_best = self.f18_search = self.f18_epoch = None

    def f18_done(self, pos, now):
        ident = self.f18_threat
        seen = self.last_seen.get(ident)
        last = max(seen.time if seen is not None else -math.inf,
                   self.attackers.get(ident, (-math.inf, None))[0], self.f18_started)
        if self.kinds != {"gun"} or ident in self.eliminated or now - last >= F18_LOST_S:
            return True
        point = self.f18_threat_pos(ident)
        if point is not None and self.f8_blocked(raised(point, self.f18_muzzle(ident)), pos):
            if self.f18_hidden_since is None:
                self.f18_hidden_since = now
        else:
            self.f18_hidden_since = None
        return (self.f18_hidden_since is not None and now - self.f18_hidden_since >= F18_HIDDEN_S - 1e-6
                and now - self.last_damage >= F18_CALM_S)

    def f18_threat_pos(self, ident):
        seen = self.last_seen.get(ident)
        hit, estimate = self.attackers.get(ident, (-math.inf, None))
        if seen is not None and (estimate is None or seen.time >= hit - 1):
            return seen.pos
        return estimate

    def f18_muzzle(self, ident):
        seen = self.last_seen.get(ident)
        cubes = limit(seen.cubes or 0, 0, 100) if seen is not None else 0
        return self.phys("muzzle_height", 7) * (1 + cubes * number(self.cubes.get("size_per_cube"), 0.05))

    def f18_project(self, point, velocity, seconds, muzzle, reach=math.inf):
        speed = math.hypot(*velocity)
        scale = min(F18_PURSUIT * seconds, reach) / speed if speed > 0 else 0
        for fraction in (1, 0.5):
            moved = (point[0] + velocity[0] * scale * fraction, point[1] + velocity[1] * scale * fraction, point[2])
            if self.arena is None or not self.arena.solid(raised(moved, muzzle)):
                return raised(moved, muzzle)
        return raised(point, muzzle)

    def f18_ray(self, origin, point, height):
        self.f18_rays -= 1
        return self.arena.clear_ray(origin, raised(point, self.body_height * height))

    def f18_hidden(self, origin, point):
        return not any(self.f18_ray(origin, point, height) for height in (0.6, 0.9, 0.3))

    def f18_corridor(self, pos, goal, radius):
        arena = self.arena
        steps = max(1, min(48, math.ceil(distance(pos, goal) / 2.5)))
        self.f18_rays -= steps / 16
        x, y, z = pos
        dx, dy = (goal[0] - x) / steps, (goal[1] - y) / steps
        for i in range(1, steps + 1):
            px, py = x + i * dx, y + i * dy
            if arena.obstacle((px, py, z), radius, self.body_height, 0.55):
                return False
            idx = arena.cell(px, py)
            if idx is not None and abs(arena.floor[idx] - z) <= arena.step_up + 0.5:
                z = arena.floor[idx]
        return True

    def f18_travel(self, span, walk, boost, energy, stats, grounded):
        drain = limit(self.phys("boost_drain", 17, stats), 0.1, 500)
        burst = max(0, energy - eb.BOOST_RESERVE) / drain if grounded else 0
        if span <= boost * burst:
            return span / boost + 0.15
        return burst + (span - boost * burst) / walk + 0.15

    def f18_routes(self, pos, zone, threat, velocity, muzzle, pace, others):
        arena = self.arena
        radius, walk, boost, energy, stats, grounded = pace
        points = [(0.0, pos)]
        if self.f18_cover is not None:
            points.insert(0, (distance(pos, self.f18_cover), self.f18_cover))
        for span in F18_RINGS:
            for k in range(F18_DIRECTIONS):
                yaw = k * math.tau / F18_DIRECTIONS
                x, y = pos[0] + span * math.cos(yaw), pos[1] + span * math.sin(yaw)
                cell = arena.cell(x, y)
                if cell is not None and arena.ground_ok(cell, radius):
                    points.append((span, (x, y, arena.floor[cell])))
        floor_gap = min(F18_ZONE_M, zone.gap(pos))
        reach = max(0, distance(threat, pos) - F18_STANDOFF_M)
        ring = [point for span, point in points if 0 < span <= F18_VIA_M]
        reachable = {}
        for _, point in points:
            while self.f18_rays <= 0 or time.perf_counter() >= self.f18_until:
                yield None
            span = distance(pos, point)
            if span > F18_ROUTE_M:
                continue
            arrival = self.f18_travel(span, walk, boost, energy, stats, grounded)
            if zone.gap(point, arrival + 3) < floor_gap:
                continue
            if not all(self.f18_hidden(self.f18_project(threat, velocity, seconds, muzzle, reach), point)
                       for seconds in (0, arrival, arrival + F18_LEAD_S)):
                continue
            if any(self.f18_ray(eye, point, 0.6) for eye in others):
                continue
            legs = self.f18_legs(pos, point, radius, ring, reachable)
            if legs is None:
                continue
            length = sum(distance(a, b) for a, b in zip(legs, legs[1:]))
            if length > F18_ROUTE_M:
                continue
            arrival = self.f18_travel(length, walk, boost, energy, stats, grounded)
            if len(legs) > 2 and not all(
                    self.f18_hidden(self.f18_project(threat, velocity, seconds, muzzle, reach), point)
                    for seconds in (arrival, arrival + F18_LEAD_S)):
                continue
            samples = min(6, max(1, math.ceil(arrival / 0.5)))
            exposed = 0
            for i in range(samples):
                along = self.f18_along(legs, length * i / samples)
                exposed += self.f18_ray(self.f18_project(threat, velocity, arrival * i / samples, muzzle, reach),
                                        along, 0.6)
            yield (round(exposed * arrival / samples / F18_EXPOSE_BIN), round(arrival, 2)), point, legs

    def f18_legs(self, pos, point, radius, ring, reachable):
        span = distance(pos, point)
        if span <= 0.5 or self.f18_corridor(pos, point, radius):
            return pos, point
        field = self.f18_field
        if field is not None and field[3] and distance(field[0], pos) <= F18_FIELD_M:
            arena = self.arena
            cell = arena.cell(*point[:2])
            if cell not in field[1]:
                return None
            cells = []
            while cell is not None:
                cells.append(cell)
                cell = field[2][cell]
            cells.reverse()
            path = [pos]
            for cell in cells[F18_PATH_STEP::F18_PATH_STEP]:
                x, y = arena.point(cell)
                path.append((x, y, arena.floor[cell]))
            path.append(point)
            return tuple(path)
        vias = sorted((distance(pos, via) + distance(via, point), via) for via in ring
                      if 1 < distance(pos, via) and distance(via, point) < span)
        for length, via in vias[:F18_VIA_TRIES]:
            if length > F18_ROUTE_M:
                break
            if via not in reachable:
                reachable[via] = self.f18_corridor(pos, via, radius)
            if reachable[via] and self.f18_corridor(via, point, radius):
                return pos, via, point
        return None

    def f18_flood(self, pos, radius):
        arena = self.arena
        w = arena.w
        start = arena.cell(*pos[:2])
        cost, parent = {start: 0.0}, {start: None}
        field = self.f18_field = [pos, cost, parent, False]
        queue = [(0.0, start)]
        bound = F18_ROUTE_M / eb.GRID_M
        ok = {}
        count = 0
        while queue:
            count += 1
            if count % 24 == 0 and time.perf_counter() >= self.f18_flood_until:
                yield
            g, current = heapq.heappop(queue)
            if g > cost[current]:
                continue
            y, x = divmod(current, w)
            for dx, dy in eb.NEIGHBORS:
                if not (1 <= x + dx < w - 1 and 1 <= y + dy < arena.h - 1):
                    continue
                n = current + dy * w + dx
                if n not in ok:
                    ok[n] = arena.ground_ok(n, radius)
                if not ok[n]:
                    continue
                if dx and dy and not (arena.ground_ok(current + dx, radius) and arena.ground_ok(current + dy * w, radius)):
                    continue
                step = g + (1.414 if dx and dy else 1.0)
                if step <= bound and step < cost.get(n, math.inf):
                    cost[n], parent[n] = step, current
                    heapq.heappush(queue, (step, n))
        field[3] = True

    def f18_prepare(self, pos, contacts):
        if self.arena is None or pos is None or self.kinds != {"gun"}:
            return
        if self.f18_threat is None and not (self.f8_now <= F18_WINDOW_S and any(
                c.kind == "mech" and c.clear and c.dist <= F18_WARN_M for c in contacts)):
            return
        field = self.f18_field
        if field is None or distance(field[0], pos) > F18_FIELD_M * 0.5:
            self.f18_flooding = self.f18_flood(pos, limit(self.phys("radius", 2.5, self.self_stats), 0.5, 25))
        if self.f18_flooding is not None:
            self.f18_flood_until = time.perf_counter() + F18_FLOOD_S
            if next(self.f18_flooding, False) is False:
                self.f18_flooding = None

    @staticmethod
    def f18_along(legs, travelled):
        for a, b in zip(legs, legs[1:]):
            span = distance(a, b)
            if travelled <= span or b is legs[-1]:
                f = min(1, travelled / span) if span > 0 else 1
                return tuple(x + (y - x) * f for x, y in zip(a, b))
            travelled -= span
        return legs[-1]

    def f18_reach(self, pos, ux, uy, span, radius):
        arena = self.arena
        x, y, z = pos
        travelled = 0.0
        for i in range(1, int(span / 2.5) + 1):
            px, py = x + ux * 2.5 * i, y + uy * 2.5 * i
            if arena.obstacle((px, py, z), radius, self.body_height, 0.55):
                break
            travelled = 2.5 * i
            idx = arena.cell(px, py)
            if idx is not None and abs(arena.floor[idx] - z) <= arena.step_up + 0.5:
                z = arena.floor[idx]
        return travelled

    def f18_fallback(self, pos, zone, threat, velocity, muzzle, radius, pace, until):
        arena = self.arena
        away = bearing(threat, pos)
        step = math.tau / F18_DIRECTIONS
        base = round(away / step)
        speed = min(F18_PURSUIT, math.hypot(*velocity))
        seen = self.last_seen.get(self.f18_threat)
        lightning = seen is not None and "lightning" in seen.weapons
        others = [enemy.pos for ident, enemy in self.observers.items() if ident != self.f18_threat]
        floor_gap = min(0, zone.gap(pos))
        deadline = min(until, time.perf_counter() + F18_FALLBACK_S)
        best = None
        for n in range(F18_DIRECTIONS):
            if n and time.perf_counter() >= deadline:
                break
            yaw = angle((base + (n + 1) // 2 * (1 if n % 2 else -1)) * step)
            ux, uy = math.cos(yaw), math.sin(yaw)
            reach = self.f18_reach(pos, ux, uy, pace * F18_HORIZON_S, radius)
            end = pos[0] + ux * reach, pos[1] + uy * reach
            if zone.gap(end, F18_HORIZON_S) < floor_gap:
                continue
            cost = 0.0
            for seconds in (F18_HORIZON_S / 3, F18_HORIZON_S * 2 / 3, F18_HORIZON_S):
                along = min(reach, pace * seconds)
                cell = arena.cell(pos[0] + ux * along, pos[1] + uy * along)
                point = (pos[0] + ux * along, pos[1] + uy * along, arena.floor[cell] if cell is not None else pos[2])
                gap = distance(threat, point)
                moved = min(speed * seconds, max(0, gap - 4)) / gap if gap > 0 else 0
                chaser = tuple(a + (b - a) * moved for a, b in zip(threat[:2], point[:2])) + (threat[2],)
                span = distance(chaser, point)
                if arena.clear_ray(raised(chaser, muzzle), raised(point, self.body_height * 0.6)):
                    cost += limit(60 / max(1, span), 0.4, 1.6) + (1.5 if lightning and span < 60 else 0)
            cost += 0.5 * sum(distance(end, other) < 50 for other in others)
            key = round(cost, 3), distance(pos, threat) - distance(end, threat)
            if best is None or key < best[0]:
                best = key, yaw
        return best[1] if best is not None else away

    def f18_move(self, pos, zone, stats, grounded, energy, now, until):
        ident = self.f18_threat
        threat = self.f18_threat_pos(ident)
        if threat is None or self.arena is None:
            return None
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        boost = limit(self.phys("boost_speed", 19.5, stats), walk, 90)
        velocity = self.f18_vel.get(ident, (0.0, 0.0))
        muzzle = self.f18_muzzle(ident)
        exposed = self.arena.clear_ray(raised(threat, muzzle), raised(pos, self.body_height * 0.6))
        sprint = grounded and energy > eb.BOOST_RESERVE
        epoch = self.f18_epoch
        if epoch is None or now - epoch[0] >= F18_REPLAN_S - 1e-6 or distance(threat, epoch[1]) > F18_MOVED_M:
            others = [enemy.eye for i, enemy in sorted(self.observers.items(), key=lambda item: distance_sq(pos, item[1].pos))
                      if i != ident and distance_sq(pos, enemy.pos) <= 150 ** 2][:F18_OTHERS]
            self.f18_epoch = now, threat
            self.f18_best = None
            self.f18_search = self.f18_routes(pos, zone, threat, velocity, muzzle,
                                              (radius, walk, boost, energy, stats, grounded), others)
        self.f18_rays = F18_PLAN_RAYS
        self.f18_until = min(until, time.perf_counter() + F18_PLAN_S)
        search = self.f18_search
        if search is not None:
            for result in search:
                if result is None:
                    break
                if self.f18_best is None or result[0] < self.f18_best[0]:
                    self.f18_best = result
            else:
                self.f18_search = None
        if self.f18_best is not None:
            self.f18_cover, self.f18_legs_now = self.f18_best[1], self.f18_best[2]
        elif self.f18_search is None:
            self.f18_cover = self.f18_legs_now = None
        cover = self.f18_cover
        if cover is not None:
            legs = self.f18_legs_now or (pos, cover)
            near = min(range(len(legs)), key=lambda i: distance_sq(pos, legs[i]))
            goal = legs[min(near + 1, len(legs) - 1)]
            stride = max(1, (len(legs) - near - 2) // F18_STEER_TRIES + 1)
            for index in range(len(legs) - 1, near + 1, -stride):
                if self.f18_corridor(pos, legs[index], radius):
                    goal = legs[index]
                    break
            move = self.move_to_laser_cover(pos, goal, boost if sprint and exposed else walk, sprint and exposed)
            self.mode = "f18-cover" if distance(pos, cover) > 0.45 else "f18-hold"
            return move
        yaw = self.f18_fallback(pos, zone, threat, velocity, muzzle, radius, boost if sprint else walk, until)
        self.mode = "f18-open"
        return {"move": [math.cos(yaw), math.sin(yaw)], "boost": sprint and exposed, "jump": False}

    def f18_supersedes_rush(self):
        return self.f18(F18_BREAK) and (self.f8_now <= F18_WINDOW_S or self.f18_threat is not None)

    def f18_aimed(self, enemy):
        reach = max((self.f9_ranges.get(kind, 0) for kind in enemy.armed), default=0) or self.f9_ranges.get("gun", 230)
        return enemy.clear and enemy.face_error <= F18_QUIET_AIM and enemy.dist <= reach

    def f18_finish(self, enemy):
        if not math.isfinite(enemy.hp):
            return False
        total = 0.0
        for weapon in self.weapon_slots:
            kind = weapon.get("kind")
            if kind == "gun" and number(weapon.get("reload")) <= 0:
                hit = limit(0.9 - enemy.dist * 0.005, 0.3, 0.8)
                total += max(0, number(weapon.get("ammo"))) * self.weapon_setting(weapon, "damage", 45) * hit
            elif kind == "laser" and number(weapon.get("cooldown")) <= 0 and enemy.dist <= self.weapon_setting(weapon, "range", 280):
                total += self.weapon_setting(weapon, "damage", 315) * 0.9
        return enemy.hp <= total

    def f18_quiet(self, options, now):
        kept = []
        for merit, enemy in options:
            if enemy.kind == "mech":
                when, _ = self.attackers.get(enemy.id, (-math.inf, None))
                if not (enemy.id == self.f18_threat or 0 <= now - when <= F18_QUIET_HIT_S or enemy.dist <= F18_QUIET_M
                        or self.f18_aimed(enemy) or self.f18_finish(enemy)):
                    continue
            elif self.f18_alarm and enemy.id != self.f18_prev_target:
                continue
            kept.append((merit, enemy))
        return kept

    def f18_near_rule(self):
        return (self.f18(F18_NEAR) and self.f8_now <= F18_WINDOW_S and self.kinds == {"gun"}
                and self.f18_threat is None and self.arena is not None)

    def f18_open_hold(self, pos, zone, radius, now):
        still = self.f18_still
        if still is None or distance(pos, still[0]) > 1.5:
            self.f18_still = still = pos, now
        point = self.f18_near_point
        if point is not None:
            if now < self.f18_near_until and distance(pos, point) > 1.5 and zone.gap(point, 3) > F18_ZONE_M:
                return point
            self.f18_near_point = None
        if (self.weapon_point is not None or self.loot_point is not None or self.farm is not None
                or self.disengage or self.single_escape or now - still[1] < F18_STILL_S
                or self.arena.near_cover(pos) <= F18_OPEN_M):
            return None
        arena = self.arena
        best = None
        for span in F18_NEAR_SEARCH:
            for dx, dy in eb.COVER_ANGLES:
                x, y = pos[0] + span * dx, pos[1] + span * dy
                cell = arena.cell(x, y)
                if cell is None or not arena.ground_ok(cell, radius):
                    continue
                near = arena.near_cover((x, y))
                point = x, y, arena.floor[cell]
                if (near >= F18_NEAR_M or zone.gap(point, 5) < F18_ZONE_M + 2
                        or best is not None and near + span * 0.2 >= best[0]):
                    continue
                if self.f18_corridor(pos, point, radius):
                    best = near + span * 0.2, point
        if best is None:
            return None
        self.f18_near_point, self.f18_near_until = best[1][:2], now + F18_NEAR_HOLD_S
        return self.f18_near_point

    def f20(self, rule):
        return F20_ENDGAME and rule and not self.opener_undecided

    def f20_scan(self, obs, contacts, pos):
        now = self.f8_now
        for raw in seq(obs.get("events"))[:200]:
            event = obj(raw)
            if event.get("type") == "hit" and number(event.get("amount")) > 0:
                ident = number(event.get("target"), None)
                if ident is not None and 0 <= ident < 16:
                    self.f20_hits[ident] = now
                    self.f20_dealt.append((now, ident, number(event.get("amount"))))
        while self.f20_dealt and now - self.f20_dealt[0][0] > F20_LOSS_S:
            self.f20_dealt.popleft()
        for c in contacts:
            if c.kind == "mech" and math.isfinite(c.hp) and 0 <= c.id < 16:
                track = self.f20_hp.setdefault(c.id, deque())
                track.append((now, c.hp))
                while track and now - track[0][0] > F20_LOSS_S:
                    track.popleft()
        self.f20_lanes = sum(1 for c in contacts if c.kind == "mech" and c.clear and c.dist <= F20_LANE_M)
        self.f20_cubes = tuple(point for raw in seq(obs.get("cubes"))[:64]
                               if (point := vec(obj(raw).get("pos"), 3)) is not None)
        if pos is None:
            return
        if self.f20(F20_DUEL) and self.alive == 2:
            self.f20_duel = True
            mechs = [c for c in contacts if c.kind == "mech" and c.id not in self.eliminated]
            enemy = min(mechs, key=lambda c: (not c.clear, c.dist), default=None)
            if enemy is not None:
                self.f20_enemy, self.f20_id, self.f20_point = enemy, enemy.id, enemy.pos
                return
            seen = max(((i, s) for i, s in self.last_seen.items() if i not in self.eliminated),
                       key=lambda item: item[1].time, default=None)
            hit = max(((i, w) for i, w in self.attackers.items() if i not in self.eliminated and w[1] is not None),
                      key=lambda item: item[1][0], default=None)
            if hit is not None and (seen is None or hit[1][0] > seen[1].time + 1):
                self.f20_id, self.f20_point = hit[0], hit[1][1]
            elif seen is not None:
                self.f20_id, self.f20_point = seen[0], seen[1].pos
            elif self.heard_rival is not None and 0 <= now - self.last_near_sound <= F20_SOUND_S:
                self.f20_point = self.heard_rival
            return
        if self.f20(F20_FINISH) and now > F20_AFTER_S:
            self.f20_target = self.f20_finish_pick(contacts, pos, now)

    def f20_loss(self, ident, now):
        track = self.f20_hp.get(ident)
        if not track:
            return 0.0
        lost = sum(max(0, a[1] - b[1]) for a, b in zip(track, list(track)[1:]))
        ours = sum(amount for when, i, amount in self.f20_dealt if i == ident)
        return lost - ours

    def f20_reachable(self, enemy, pos):
        muzzle = self.phys("muzzle_height", 7, self.self_stats)
        pitch = self.phys("min_pitch", -0.7, self.self_stats), self.phys("max_pitch", 1.3, self.self_stats)
        return any(w.get("kind") in duel_bot.KNOWN_WEAPONS and self.aim_for(w, enemy, pos, muzzle, pitch) is not None
                   for w in self.weapon_slots)

    def f20_finish_pick(self, contacts, pos, now):
        if self.f18_threat is not None or str(self.mode).startswith("f18") or self.f20_lanes >= 2:
            return None
        if any(0 <= now - when <= F20_RETURN_S for when, _ in self.attackers.values()):
            return None
        state = self.f20_finish
        if state is not None:
            ident, start = state
            enemy = next((c for c in contacts if c.id == ident and c.kind == "mech" and c.clear), None)
            if (enemy is not None and now - max(start, self.f20_hits.get(ident, -math.inf)) <= F20_FINISH_S
                    and self.f20_reachable(enemy, pos)):
                return enemy
            self.f20_finish = None
            self.f20_banned[ident] = now + F20_FINISH_BAN_S
        best = None
        for c in contacts:
            if (c.kind != "mech" or not c.clear or c.id in self.eliminated or not math.isfinite(c.hp)
                    or self.f20_banned.get(c.id, -math.inf) > now):
                continue
            if c.hp >= c.max_hp * F20_FINISH_HP and self.f20_loss(c.id, now) < F20_LOSS_HP:
                continue
            if (best is None or c.hp < best.hp) and self.f20_reachable(c, pos):
                best = c
        if best is not None:
            self.f20_finish = best.id, now
        return best

    def f20_goal(self, pos, zone, radius, height, until):
        if not self.f20_duel or self.arena is None:
            return None
        walk = limit(self.phys("walk_speed", 11.7, self.self_stats), 2, 60)
        _, urgent = zone.anchor(pos, walk)
        if urgent or zone.gap(pos) < 0:
            return None
        if (self.weapon_point is not None and "laser" not in self.kinds
                and self.pickups.get(getattr(self, "weapon_id", None), (0, None))[1] == "laser"):
            return None
        point = self.f20_point
        if point is None:
            point = (*zone.next_center, pos[2])
        enemy = self.f20_enemy
        span = distance(pos, point)
        stop = F20_STOP_ARC_M if "lightning" in self.kinds else F20_STOP_M
        goal = point
        if enemy is not None and enemy.clear and span <= stop:
            goal = pos
        elif ("laser" not in self.kinds and self.f20_id is not None
              and "laser" in (self.last_seen[self.f20_id].weapons if self.f20_id in self.last_seen else ())
              and span > (F20_REACH_ARC_M if "lightning" in self.kinds else F20_REACH_GUN_M)):
            hop = self.f20_hop(pos, zone, point, radius, until)
            if hop is not None:
                goal = hop
        boost = limit(self.phys("boost_speed", 19.5, self.self_stats), walk, 90)
        center, size = zone.circle_in(distance(pos, goal) / boost + 2)
        inner = max(0, size - F20_ZONE_M)
        gap = distance(goal, center)
        if gap > inner:
            f = inner / gap
            goal = (center[0] + (goal[0] - center[0]) * f, center[1] + (goal[1] - center[1]) * f, pos[2])
        if goal is not pos:
            dx, dy = goal[0] - pos[0], goal[1] - pos[1]
            length = math.hypot(dx, dy)
            best = None
            for cube in self.f20_cubes:
                if abs(cube[2] - pos[2]) > 4 or length <= 0:
                    continue
                along = ((cube[0] - pos[0]) * dx + (cube[1] - pos[1]) * dy) / length
                if 0 < along < length and segment_distance_sq(pos, goal, cube) <= F20_PATH_CUBE_M ** 2:
                    if best is None or along < best[0]:
                        best = along, cube
            if best is not None and zone.gap(best[1], 2) > F20_ZONE_M:
                goal = best[1]
        self.f20_dest = goal
        return goal[:2]

    def f20_hop(self, pos, zone, threat, radius, until):
        now = self.f8_now
        stats = self.self_stats
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        boost = limit(self.phys("boost_speed", 19.5, stats), walk, 90)
        epoch = self.f20_epoch
        best = self.f20_best
        if (epoch is None or self.f20_search is None and now - epoch[0] >= F20_REPLAN_S
                or distance(threat, epoch[1]) > F18_MOVED_M
                or best is not None and distance(pos, best[1]) < 1.5):
            self.f20_epoch = now, threat
            self.f20_best = best = None
            muzzle = self.f18_muzzle(self.f20_id)
            self.f20_search = self.f18_routes(pos, zone, threat, (0.0, 0.0), muzzle,
                                              (radius, walk, boost, self.energy, stats, True), ())
        self.f18_rays = F20_HOP_RAYS
        self.f18_until = min(until, time.perf_counter() + F20_HOP_S)
        here = distance(pos, threat)
        if self.f20_search is not None:
            for result in self.f20_search:
                if result is None:
                    break
                gain = here - distance(result[1], threat)
                if gain < F20_HOP_GAIN_M:
                    continue
                rank = result[0][0], -gain
                if best is None or rank < best[0]:
                    best = rank, result[1]
            else:
                self.f20_search = None
        self.f20_best = best
        return None if best is None else best[1]

    def f20_duel_move(self, pos, vel, waypoint, zone, threats, hazards, direction, stats, grounded, energy, now,
                      until, in_zone, terminal_burn, drop_hint):
        move = super().movement(pos, vel, waypoint, zone, False, False, threats, hazards, direction, stats,
                                grounded, energy, now, until, in_zone, terminal_burn, drop_hint)
        if (grounded and not move.get("jump") and energy > eb.BOOST_RESERVE
                and distance(pos, self.f20_dest) > F20_HOLD_M and math.hypot(*move["move"]) > 0.2):
            move["boost"] = True
        self.mode = "f20-duel"
        return move

    def f20_fire(self, pos, weapons, actual, stats, target, energy, action):
        firing = action["fire"] = [False, False]
        muzzle = self.phys("muzzle_height", 7, stats)
        pitch = self.phys("min_pitch", -0.7, stats), self.phys("max_pitch", 1.3, stats)
        yaw_allow = min(eb.ARMING_YAW_ALLOW_RAD, self.phys("turn_rate", 4, stats) * self.physics_dt * 0.52)
        pitch_allow = min(eb.ARMING_PITCH_ALLOW_RAD, self.phys("pitch_rate", 3, stats) * self.physics_dt * 0.52)
        plans = []
        for index, weapon in enumerate(weapons):
            kind = weapon.get("kind")
            if kind not in duel_bot.KNOWN_WEAPONS:
                continue
            plan = self.aim_for(weapon, target, pos, muzzle, pitch) if target.clear else None
            plans.append((index, kind, weapon, plan))
        aim = None
        order = []
        for index, kind, weapon, plan in plans:
            if plan is None:
                continue
            charge = number(weapon.get("charge"))
            if kind == "laser" and charge >= self.weapon_setting(weapon, "charge", 0.75) - 0.15:
                order.append((0, plan))
            elif kind == "gun" and number(weapon.get("reload")) <= 0 and number(weapon.get("ammo"), 1) > 0:
                order.append((1, plan))
            else:
                order.append(({"laser": 2, "lightning": 3, "gun": 4, "mortar": 5}[kind], plan))
        if order:
            aim = min(order, key=lambda item: item[0])[1]
            action["aim"] = list(aim[:2])
        else:
            action["aim"] = [bearing(pos, target.pos), 0.0]
        for index, kind, weapon, plan in plans:
            cooldown = number(weapon.get("cooldown"))
            if kind == "gun" and number(weapon.get("ammo"), 1) <= 0 and not number(weapon.get("reload")):
                action["reload"] = True
            if kind == "laser":
                charge = number(weapon.get("charge"))
                if charge > 0:
                    aligned = plan is not None and abs(angle(plan[0] - actual[0])) <= plan[2] + yaw_allow and abs(
                        plan[1] - actual[1]) <= plan[3] + pitch_allow
                    full = self.weapon_setting(weapon, "charge", 0.75)
                    firing[index] = not (aligned and charge >= full - self.physics_dt)
                else:
                    firing[index] = plan is not None and cooldown <= self.physics_dt
                continue
            if plan is None or cooldown > self.dt + 0.025:
                continue
            aligned = abs(angle(plan[0] - actual[0])) <= plan[2] + yaw_allow and (
                kind == "lightning" or abs(plan[1] - actual[1]) <= plan[3] + pitch_allow)
            if kind == "gun":
                firing[index] = aligned and number(weapon.get("reload")) <= 0 and number(weapon.get("ammo"), 1) > 0
            elif kind == "lightning":
                firing[index] = aligned and energy >= F20_ARC_ENERGY
            else:
                firing[index] = aligned and aim is plan
        self.last_fire_target = target.id

    def f20_second(self, pos, weapons, actual, stats, contacts, energy, action):
        ident = self.last_fire_target
        fire = action.get("fire")
        if ident is None or not fire:
            return
        target = next((c for c in contacts if c.id == ident and c.kind == "mech" and c.clear), None)
        if target is None:
            return
        gun = any(fire[i] and w.get("kind") == "gun" for i, w in enumerate(weapons))
        muzzle = self.phys("muzzle_height", 7, stats)
        pitch = self.phys("min_pitch", -0.7, stats), self.phys("max_pitch", 1.3, stats)
        yaw_allow = min(eb.ARMING_YAW_ALLOW_RAD, self.phys("turn_rate", 4, stats) * self.physics_dt * 0.52)
        pitch_allow = min(eb.ARMING_PITCH_ALLOW_RAD, self.phys("pitch_rate", 3, stats) * self.physics_dt * 0.52)
        for index, weapon in enumerate(weapons):
            kind = weapon.get("kind")
            if kind == "laser":
                charge = number(weapon.get("charge"))
                if not (gun or charge > 0):
                    continue
                plan = self.aim_for(weapon, target, pos, muzzle, pitch)
                if plan is None:
                    continue
                if charge > 0:
                    full = self.weapon_setting(weapon, "charge", 0.75)
                    aligned = (abs(angle(plan[0] - actual[0])) <= plan[2] + yaw_allow
                               and abs(plan[1] - actual[1]) <= plan[3] + pitch_allow)
                    fire[index] = not (aligned and charge >= full - self.physics_dt)
                    if charge >= full - 0.15:
                        action["aim"] = list(plan[:2])
                elif number(weapon.get("cooldown")) <= self.physics_dt:
                    fire[index] = True
            elif kind == "lightning" and gun and not fire[index]:
                if number(weapon.get("cooldown")) > self.dt + 0.025 or energy < F20_ARC_ENERGY:
                    continue
                plan = self.aim_for(weapon, target, pos, muzzle, pitch)
                if plan is not None and abs(angle(plan[0] - actual[0])) <= plan[2] + yaw_allow:
                    fire[index] = True

    def f20_cube(self, pos, waypoint, zone, now):
        if (now <= F20_AFTER_S or self.alive < 3 or self.hp_share < F20_SCAV_HP or self.f20_lanes
                or self.arena is None or self.weapon_point is not None or self.loot_point is not None):
            return None
        if 0 <= now - self.last_damage <= F20_SCAV_HIT_S:
            if self.f20_scav_goal is not None:
                self.f20_scav_ban[self.f20_scav_goal[:2]] = now + F20_SCAV_HIT_S
                self.f20_scav_goal = None
            return None
        if len(self.f20_scav_ban) > 64:
            self.f20_scav_ban = {key: until for key, until in self.f20_scav_ban.items() if until > now}
        walk = limit(self.phys("walk_speed", 11.7, self.self_stats), 2, 60)
        base = distance(pos, waypoint)
        best = None
        for cube in self.f20_cubes:
            if abs(cube[2] - pos[2]) > 4 or self.f20_scav_ban.get(cube[:2], -math.inf) > now:
                continue
            span = distance(pos, cube)
            if span > F20_SCAV_REACH_M:
                continue
            extra = span + distance(cube, waypoint) - base
            if extra > F20_SCAV_EXTRA_M or zone.gap(cube, span / walk + F20_SCAV_SPARE_S) < F20_ZONE_M:
                continue
            if best is None or extra < best[0]:
                best = extra, cube
        if best is None:
            return None
        radius = limit(self.phys("radius", 2.5, self.self_stats), 0.5, 25)
        if not self.arena.corridor(pos, best[1], radius, self.body_height):
            self.f20_scav_ban[best[1][:2]] = now + 1.0
            return None
        self.f20_scav_goal = best[1]
        return best[1][:2]

    def f9_aim_error(self, yaw, pitch, origin, point):
        return max(abs(angle(yaw - bearing(origin, point))),
                   abs(pitch - math.atan2(point[2] - origin[2], distance(origin, point))))

    def f9_evidence(self, obs, pos, now):
        
        rivals = {ident: data for ident, data in self.f9_rivals.items()
                  if now - data[0].time <= F9_FRESH_S and ident not in self.eliminated}
        for raw in seq(obs.get("mechs"))[:48]:
            enemy = obj(raw)
            ident = number(enemy.get("id"), None)
            seen = self.last_seen.get(ident)
            if enemy.get("kind") != "mech" or seen is None or seen.time != now:
                continue
            if seen.hp == 0:
                rivals.pop(ident, None)
                self.f9_trade_tracks.pop(ident, None)
                continue
            weapon_range = max((self.f9_ranges[kind] for kind in self.f9_ranges if kind in seen.weapons), default=0)
            origin = self.shooter_origin(ident)
            if origin is not None and weapon_range > 0:
                rivals[ident] = (seen, origin, weapon_range, vec(enemy.get("aim"), 2),
                                 number(enemy.get("max_hp"), math.inf))
        self.f9_rivals = rivals
        aimed, aimed_elsewhere = {}, set()
        body = raised(pos, self.body_height * 0.65)
        body_radius = limit(self.phys("radius", 2.5, self.self_stats), 0.5, 25)
        for ident, (seen, origin, reach, aim, _) in rivals.items():
            span = distance_sq(pos, seen.pos)
            if aim is None or span > reach ** 2:
                continue
            error = self.f9_aim_error(*aim, origin, body)
            if error > F9_AIM_RAD:
                continue
            if error > math.atan2(body_radius, math.sqrt(span)) and any(
                    other != ident and distance_sq(origin, track.pos) <= reach ** 2
                    and self.f9_aim_error(*aim, origin, raised(track.pos, 5.0)) < min(error, math.radians(6))
                    and self.arena.clear_ray(origin, raised(track.pos, 5.0))
                    for other, (track, _, _, _, _) in rivals.items()):
                aimed_elsewhere.add(ident)
            elif not self.f8_blocked(origin, pos):
                aimed[ident] = origin
        if ffa_enabled(F9_HOLD_TRADE):
            
            
            self.f9_shots = {pair: when for pair, when in self.f9_shots.items()
                             if now - when <= F9_TRADE_S}
            for raw in seq(obs.get("beams"))[:32]:
                if time.perf_counter() >= self.f8_deadline - 0.0021:
                    break
                beam = obj(raw)
                shooter = number(beam.get("by"), None)
                age = max(0, number(beam.get("age")))
                path = seq(beam.get("path"))
                if (shooter not in rivals or age > F9_FRESH_S
                        or beam.get("kind") not in ("laser", "lightning") or len(path) < 2):
                    continue
                for end in path[1:8]:
                    point = vec(end, 3)
                    if point is None:
                        continue
                    for other, (track, eye, _, _, _) in rivals.items():
                        if (other != shooter and distance_sq(point, track.pos) <= (3 + 0.13 * (track.cubes or 0)) ** 2
                                and track.pos[2] - 0.5 <= point[2] <= eye[2] + 4):
                            self.f9_shots[shooter, other] = now - age
        return rivals, aimed, aimed_elsewhere

    def f9_trading(self, rivals, now):
        
        self.f9_trade_tracks = {ident: data for ident, data in self.f9_trade_tracks.items()
                                if now - data[0].time <= F9_TRADE_S and ident not in self.eliminated}
        self.f9_trade_tracks.update(rivals)
        for (shooter, target), when in self.f9_shots.items():
            if shooter not in self.f9_trade_tracks or target not in rivals:
                continue
            pair = tuple(sorted((shooter, target)))
            shooter_track, _, _, _, _ = self.f9_trade_tracks[shooter]
            _, origin, reach, aim, _ = rivals[target]
            target_body = raised(shooter_track.pos, 5.0)
            if (pair in self.f9_trades or (target, shooter) in self.f9_shots
                    or (aim is not None and distance_sq(origin, target_body) <= reach ** 2
                        and self.f9_aim_error(*aim, origin, target_body) <= F9_AIM_RAD
                        and self.arena.clear_ray(origin, target_body))):
                self.f9_trades[pair] = max(when, self.f9_trades.get(pair, -math.inf))
        self.f9_trades = {pair: when for pair, when in self.f9_trades.items()
                          if now - when <= F9_TRADE_S
                          and all(i in self.f9_trade_tracks and self.f9_trade_tracks[i][0].hp is not None
                                  and self.f9_trade_tracks[i][0].hp >= F9_FINISH_HP * self.f9_trade_tracks[i][4]
                                  for i in pair)}
        return tuple(sorted({ident for pair in self.f9_trades for ident in pair}))

    def f9_weak_rival(self, pos, rivals, aimed, aimed_elsewhere, now):
        
        def priority(item):
            ident, (seen, _, _, _, _) = item
            hit_at = self.attackers.get(ident, (-math.inf, None))[0]
            return now - hit_at > F9_TRADE_S, ident not in aimed, distance_sq(pos, seen.pos)

        for ident, (seen, origin, reach, aim, _) in sorted(rivals.items(), key=priority):
            if time.perf_counter() >= self.f9_search_until:
                break
            span = distance(pos, seen.pos)
            if span > reach or ident in aimed_elsewhere:
                continue
            rear = abs(angle(self.actual[0] - bearing(pos, origin))) > self.f9_front_half_arc
            recent_hit = now - self.attackers.get(ident, (-math.inf, None))[0] <= F9_TRADE_S
            in_front = aim is not None and abs(angle(aim[0] - bearing(origin, pos))) <= self.half_fov
            if not (rear or recent_hit or ident in aimed or self.hp_share <= 0.55
                    or in_front):
                continue
            if ident not in aimed and self.f8_blocked(origin, pos):
                continue
            if rear and (ident in aimed or recent_hit or span <= self.near_vision):
                return ident, origin, reach
            
            
            alternatives = []
            for other, (track, eye, _, _, max_hp) in rivals.items():
                if (other == ident or track.hp is None or track.hp <= 0
                        or (d2 := distance_sq(origin, track.pos)) > reach ** 2):
                    continue
                hp_lead = max(0, track.hp - self.hp)
                meters = math.sqrt(d2)
                weighted_score = meters + F9_HP_METRES * hp_lead + 100 * (
                    self.hp_share <= F9_FINISH_HP < track.hp / max(1, max_hp))
                alternatives.append((meters, weighted_score, eye))
            alternatives.sort()
            scores = [score for _, score, eye in alternatives[:3]
                      if time.perf_counter() < self.f9_search_until and self.arena.clear_ray(origin, eye)]
            if (scores and span <= min(scores)) or (
                    not alternatives and recent_hit and self.hp_share <= 0.55):
                return ident, origin, reach
        return None

    def f9_cover(self, pos, zone, rivals, focus, kind, walk, radius):
        
        arena = self.arena
        second = kind == "second-lane"
        trade = kind == "hold-trade"
        others = [(origin, reach) for ident, (seen, origin, reach, _, _) in rivals.items()
                  if ident not in focus and distance_sq(pos, seen.pos) <= (reach + 30) ** 2]
        third = [seen.pos for ident, seen in self.last_seen.items() if ident not in focus
                 and 0 <= zone.now - seen.time <= F9_FRESH_S and seen.hp != 0] if second else ()
        baseline = {}
        best = None
        nearest = {ident: distance_sq(pos, origin) for ident, (origin, _) in focus.items()}
        screened = {
            ident for ident, (origin, reach) in focus.items()
            if trade and (nearest[ident] > reach ** 2 or self.f8_blocked(origin, pos))
        }
        samples = ((0, 0, 0),) if trade else ()
        samples += tuple((run, dx, dy) for run in ((5, 10, 17, 26) if not trade else (5, 12, 22))
                         for dx, dy in eb.COVER_ANGLES)
        for run, dx, dy in samples:
            if time.perf_counter() >= self.f9_search_until:
                break
            point = self.f8_ground(pos, pos[0] + run * dx, pos[1] + run * dy, radius, standing=not run)
            if point is None:
                continue
            eta = run / walk + 2
            if (zone.gap(point) < 0 or zone.gap(point, eta) < min(5, zone.gap(pos, eta))
                    or (second and (zone.gap(point) < zone.gap(pos)
                                    or zone.gap(point, eta) < zone.gap(pos, eta)))):
                continue
            mid = tuple((a + b) * 0.5 for a, b in zip(pos, point))
            if any((rival[0] - pos[0]) * dx + (rival[1] - pos[1]) * dy > 1e-6 for rival in third):
                continue
            if trade and any(segment_distance_sq(pos, point, origin) + 1e-6
                             < min(F9_TRADE_MIN_M ** 2, nearest[ident])
                             or (nearest[ident] < F9_TRADE_MIN_M ** 2 and run
                                 and distance_sq(point, origin) <= nearest[ident])
                             for ident, (origin, _) in focus.items()):
                continue
            if run and not arena.corridor(pos, point, radius, self.body_height):
                continue
            closed = 0
            gain = math.inf
            for ident, (origin, reach) in focus.items():
                if time.perf_counter() >= self.f9_search_until:
                    return best[1] if best else None
                span = distance(point, origin)
                gain = min(gain, span - math.sqrt(nearest[ident]))
                closed += span > reach or self.f8_blocked(origin, point)
            if (second and not closed) or (not second and not trade and not closed and gain < 3):
                continue
            if trade and closed != len(focus):
                continue
            if trade and run and any(
                    distance_sq(focus[ident][0], mid) <= focus[ident][1] ** 2
                    and not self.f8_blocked(focus[ident][0], mid) for ident in screened):
                continue
            
            
            for origin, reach in others:
                if time.perf_counter() >= self.f9_search_until:
                    return best[1] if best else None
                if not trade:
                    if origin not in baseline:
                        baseline[origin] = (distance_sq(origin, pos) > reach ** 2
                                            or self.f8_blocked(origin, pos))
                    if not baseline[origin]:
                        continue
                if ((distance_sq(origin, point) <= reach ** 2 and not self.f8_blocked(origin, point))
                        or (run and distance_sq(origin, mid) <= reach ** 2 and not self.f8_blocked(origin, mid))):
                    break
            else:
                score = (closed, -run if closed else gain)
                if best is None or score > best[0]:
                    best = score, point
                    if closed == len(focus):
                        return point
        return best[1] if best else None

    def f9_prepare(self, obs, pos, zone, urgent):
        supply_reset = ffa_enabled(F9_SUPPLY_RESET)
        if self.arena is None or (self.alive <= 2 and not supply_reset):
            return
        now = zone.now
        me = obj(obs.get("self"))
        rivals, aimed, aimed_elsewhere = self.f9_evidence(obs, pos, now)
        hits = {ident for ident, (when, _) in self.attackers.items()
                if 0 <= now - when <= F8_HIT_WINDOW and ident not in self.eliminated}
        stats = self.self_stats
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        safe_to_divert = not urgent and me.get("in_zone") is not False and zone.gap(pos, F8_ZONE_FIRST) > 0
        self.f9_search_until = min(self.f8_deadline - 0.0011, time.perf_counter() + 0.00125)
        late_duel = ffa_enabled(F10_DUEL) and 2 < self.alive <= 4
        second_lane = ffa_enabled(F9_SECOND_LANE) or late_duel
        if second_lane:
            self.f9_aim_since = {i: self.f9_aim_since.get(i, now) for i in aimed}
        if second_lane and self.alive > 2 and aimed:
            aimed_first = min(aimed, key=lambda i: (self.f9_aim_since[i], -distance_sq(pos, aimed[i])))
            primary = next((ident for ident in sorted(hits, key=lambda i: -self.attackers[i][0])
                            if ident in rivals and not self.f8_blocked(rivals[ident][1], pos)), aimed_first)
            secondary = min((ident for ident in aimed if (late_duel or ident not in hits) and ident != primary
                             and distance_sq(pos, aimed[ident]) <= F9_LANE_M ** 2),
                            key=lambda i: distance_sq(pos, aimed[i]), default=None)
            if secondary is not None:
                pair = primary, secondary
                self.f9_lane = pair
                if safe_to_divert:
                    focus = {ident: (rivals[ident][1], math.inf) for ident in pair}
                    self.f9_point = self.f9_cover(pos, zone, rivals, focus, "second-lane", walk, radius)
                    if self.f9_point is not None:
                        self.f9_kind = "second-lane"
                        return
        if ffa_enabled(F9_HOLD_TRADE) and self.alive > 2:
            trading = self.f9_trading(rivals, now)
            if trading and not aimed and not hits:
                self.f9_trade = trading
                if safe_to_divert:
                    focus = {ident: self.f9_trade_tracks[ident][1:3] for ident in trading}
                    self.f9_point = self.f9_cover(pos, zone, rivals, focus, "hold-trade", walk, radius)
                    if self.f9_point is None:
                        self.f9_point = pos
                    self.f9_kind = "hold-trade"
                    return
        if ffa_enabled(F9_WEAK_SPACING) and self.alive > 2 and safe_to_divert:
            weak = self.f9_weak_rival(pos, rivals, aimed, aimed_elsewhere, now)
            if weak is not None:
                ident, origin, reach = weak
                self.f9_weak = ident
                self.f9_point = self.f9_cover(pos, zone, rivals, {ident: (origin, reach)}, "weak-spacing", walk, radius)
                if self.f9_point is not None:
                    self.f9_kind = "weak-spacing"
                    return
        if supply_reset and safe_to_divert and not (hits or aimed):
            self.f9_point = self.f9_supply(obs, pos, zone, walk, radius)
            if self.f9_point is not None:
                self.f9_kind = "supply-reset"

    def f9_supply(self, obs, pos, zone, walk, radius):
        if self.kinds.isdisjoint(self.SECONDARIES) or (self.hp_share >= 0.65 and self.energy >= 30):
            return None
        arena = self.arena
        config = self.f9_drop_config
        me = obj(obs.get("self"))
        boost = max(walk, self.phys("boost_speed", 19.5, self.self_stats))
        best = None
        for raw in seq(obs.get("drops"))[:8]:
            if time.perf_counter() >= self.f9_search_until:
                break
            drop = obj(raw)
            point = vec(drop.get("pos"), 3)
            if point is None or drop.get("holder") not in (None, self.slot):
                continue
            span = distance(pos, point)
            ring = limit(number(drop.get("radius"), number(config.get("radius"), 8)), 0.5, 25)
            if span > 80 or abs(pos[2] - point[2]) > max(3, span * 0.6):
                continue
            landing = max(0, number(drop.get("lands_in")))
            remaining = number(drop.get("capture_s"), number(config.get("capture_s"), 4))
            if drop.get("holder") == self.slot:
                remaining -= max(0, number(drop.get("progress")))
            sprint_s = (max(0, self.energy - eb.BOOST_RESERVE)
                        / max(1, self.phys("boost_drain", 17, self.self_stats))) if me.get("grounded") else 0
            run = max(0, span - ring + 1)
            travel = min(sprint_s, run / boost) + max(0, run - sprint_s * boost) / walk
            finish = max(travel, landing) + max(0, remaining)
            if zone.gap(point, finish + 2) < 2 or any(
                    (distance(seen.pos, point) - ring) / (boost * 1.3) <= finish
                    for seen in self.last_seen.values() if zone.now - seen.time <= FFA_SIGHT_MEMORY_S):
                continue
            if not arena.corridor(pos, point, radius, self.body_height):
                continue
            exit_yaw = bearing(point, zone.next_center)
            exit_point = (point[0] + 2 * walk * math.cos(exit_yaw), point[1] + 2 * walk * math.sin(exit_yaw))
            if zone.gap(exit_point, finish + 2) < 2 or not arena.corridor(point, exit_point, radius, self.body_height):
                continue
            if best is None or finish < best[0]:
                best = finish, point if span > ring - 1 or abs(pos[2] - point[2]) > 3 else pos
        return best[1] if best else None

    def clear_approach(self, pos, goal, clearance, strict=False):
        for d, enemy in self.rivals:
            minimum = clearance if strict else min(clearance, max(0, d - 1))
            if segment_distance_sq(pos, goal, enemy) <= minimum ** 2:
                return False
            if not strict and distance(goal, enemy) < min(clearance, d + 10):
                return False
        return True

    def f8_hit_response(self, pos, now):
        if self.alive <= 2:
            self.f8_attacker = None
            return
        ident = self.f8_attacker
        if ident is not None:
            seen = self.last_seen.get(ident)
            if (ident in self.eliminated or (now - self.f8_last_hit >= F8_QUIET
                    and (seen is None or seen.time != now or distance(pos, seen.pos) > F8_CLEAR_RANGE
                         or self.f8_blocked(self.shooter_origin(ident), pos)))):
                self.f8_attacker = None
            return
        if len(self.escape_attackers) != 1:
            return
        ident = next(iter(self.escape_attackers))
        previous, last = self.f8_hits.get(ident, (-math.inf, -math.inf))
        fresh_hit = ident in self.f8_hit_sources or self.first_ffa_time == now and now - last <= F8_HIT_WINDOW
        if fresh_hit and (last - previous <= F8_HIT_WINDOW
                          or self.kinds == {"gun"} or self.hp_share < 0.55):
            self.f8_attacker = ident

    def f8_line(self, origin, point, height=0.62):
        return origin is None or self.arena is None or self.arena.clear_ray(
            origin, raised(point, self.body_height * height))

    def f8_blocked(self, origin, point):
        return not (self.f8_line(origin, point, 0.90) or self.f8_line(origin, point, 0.30)
                    or self.f8_line(origin, point, 0.60))

    def f8_ground(self, pos, x, y, radius, *, standing=False):
        if self.arena is None:
            return x, y, pos[2]
        cell = self.arena.cell(x, y)
        if standing:
            return pos
        if self.arena.ground_ok(cell, radius):
            return x, y, self.arena.floor[cell]
        return None

    def f8_lasers(self, obs, pos):
        if not ffa_enabled(F8_LASER_SCREEN) or self.kinds != {"gun"}:
            return {}, None
        charging = {obj(enemy).get("id") for enemy in seq(obs.get("mechs"))[:48]
                    if obj(enemy).get("charging") is True
                    and number(obj(enemy).get("id"), None) is not None}
        lasers, aimed = {}, []
        for ident, seen in self.last_seen.items():
            span = distance(pos, seen.pos)
            if ("laser" not in seen.weapons or self.f8_now - seen.time > FFA_SIGHT_MEMORY_S
                    or ident in self.eliminated):
                continue
            origin = self.shooter_origin(ident)
            lasers[ident] = origin
            if seen.yaw is None or span < F8_LASER_RANGE or seen.time != self.f8_now:
                continue
            offset = abs(angle(seen.yaw - bearing(seen.pos, pos)))
            
            
            wedge = math.radians(30 if ident in charging else 15)
            if offset <= wedge and not self.f8_blocked(origin, pos):
                aimed.append((span, ident))
        return lasers, min(aimed)[1] if aimed else None

    def f8_origins(self, pos):
        return {ident: self.shooter_origin(ident) for ident, seen in self.last_seen.items()
                if ident not in self.eliminated and self.f8_now - seen.time <= 5
                and distance_sq(pos, seen.pos) < 310 ** 2}

    def f8_cover(self, pos, zone, radius, height, kind, primary, origins, walk):
        
        arena = self.arena
        if arena is None:
            return None
        margin = min(15, zone.next_radius * 0.25)
        circle = kind == "circle"
        origin = self.shooter_origin(primary) if primary is not None else None
        if not circle and origin is None:
            return None
        candidates = []
        current_gap = zone.gap(pos)
        urgent = self.f8_hard_zone
        current_first = urgent and current_gap < 0 and zone.gap(pos, 12) < 0
        if current_first:
            center, target_radius = zone.center, zone.radius
            margin = min(6, target_radius * 0.25)
        else:
            center, target_radius = zone.next_center, zone.next_radius
        if circle:
            
            
            samples = [(pos[0], pos[1], True), (*center, False)]
            samples += [(center[0] + dx * run, center[1] + dy * run, False)
                        for share in (0.25, 0.55, 0.95)
                        for run in (max(0, target_radius - margin) * share,)
                        for dx, dy in eb.COVER_ANGLES]
            samples += [(pos[0] + dx * run, pos[1] + dy * run, False)
                        for run in (12, 26, 48) for dx, dy in eb.COVER_ANGLES]
        else:
            side = bearing(origin, pos) + math.pi / 2
            cs, sn = math.cos(side), math.sin(side)
            samples = [(pos[0], pos[1], True)]
            samples += [(pos[0] + run * (dx * cs - dy * sn), pos[1] + run * (dx * sn + dy * cs), False)
                        for run in (5, 10, 17, 26, 38) for dx, dy in eb.COVER_ANGLES]
        for x, y, standing in samples:
            point = self.f8_ground(pos, x, y, radius, standing=standing)
            if point is None:
                continue
            span = distance(pos, point)
            if span > 30:
                continue
            eta = span / walk + 0.5
            if zone.gap(point, eta + (2 if circle else F8_QUIET)) < min(0, current_gap + 2):
                continue
            deep = target_radius - distance(point, center)
            if circle and deep < margin - 0.05:
                continue
            if circle:
                preference = (-deep, span)
            else:
                preference = (deep < margin, span)
            candidates.append((preference, point, span))

        checked_start = {}
        best = None
        checks = 0
        for preference, point, span in sorted(candidates):
            if checks >= 18 or time.perf_counter() >= self.f8_search_until:
                break
            checks += 1
            if not circle and not self.f8_blocked(origin, point):
                continue
            if span > 0.5 and not arena.corridor(pos, point, radius, height):
                continue
            crossings, exposed = 0, 0
            mid = tuple((a + b) * 0.5 for a, b in zip(pos, point))
            for ident, other in origins.items():
                if ident == primary:
                    continue
                if time.perf_counter() >= self.f8_search_until:
                    crossings += 1
                    break
                if ident not in checked_start:
                    checked_start[ident] = self.f8_line(other, pos)
                end_open = not self.f8_blocked(other, point)
                exposed += end_open
                if not checked_start[ident]:
                    crossings += end_open or (span > 3 and self.f8_line(other, mid))
                if circle and checked_start[ident] and span > 3:
                    crossings += self.f8_line(other, mid)
            if circle and not self.f8_rotate:
                if not origins or exposed or crossings:
                    continue
            score = (crossings, exposed, preference)
            if best is None or score < best[0]:
                best = score, point
                if not crossings and not exposed:
                    break
        return best[1] if best is not None else None

    def f8_circle_anchor(self, pos, zone, radius):
        
        
        arena = self.arena
        current_first = self.f8_hard_zone and zone.gap(pos) < 0
        center, size = (zone.center, zone.radius) if current_first else (zone.next_center, zone.next_radius)
        margin = min(15, size * 0.25)
        aim_radius = max(0, size - margin - 4)
        yaw = bearing(center, pos)
        anchor = (center[0] + aim_radius * math.cos(yaw), center[1] + aim_radius * math.sin(yaw))
        if arena is None:
            return (*anchor, pos[2])
        def inside(point):
            return distance(point, center) <= size - margin
        
        
        side = yaw + math.pi / 2
        offset = aim_radius * 0.6
        for point in (center, (center[0] + offset * math.cos(side), center[1] + offset * math.sin(side)),
                      (center[0] - offset * math.cos(side), center[1] - offset * math.sin(side)), anchor):
            cell = arena.nearest_open(point, radius, acceptable=inside, rings=8)
            if cell is not None and arena.point(cell) != self.f8_failed_circle:
                return (*arena.point(cell), arena.floor[cell])
        return None

    def f8_prepare(self, obs, pos, zone, urgent):
        now = zone.now
        self.f8_laser_origins, laser = self.f8_lasers(obs, pos)
        self.f8_origins_now = None
        self.f8_hard_zone = ffa_enabled(F8_UNSTICK) and zone.gap(pos, F8_ZONE_FIRST) <= 0
        stats = self.self_stats
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        beyond = distance(pos, zone.next_center) - zone.next_radius + min(15, zone.next_radius * 0.25)
        rotate_by = F8_CIRCLE_LEAD + max(0, beyond) / walk + 4
        endgame = ffa_enabled(F8_CIRCLE_COVER) and self.alive <= 3 and zone.next_radius > 0
        circle_key = zone.next_center, zone.next_radius
        self.f8_rotate = self.f8_hard_zone or (endgame and beyond > 0
                            and (self.f8_rotation == circle_key or zone.gap(pos, rotate_by) <= 0
                                 or urgent or beyond / walk > 2))
        self.f8_rotation = circle_key if self.f8_rotate else None
        attacker = self.f8_attacker if ffa_enabled(F8_BREAK_SIGHT) and not self.disengage else None
        if self.f8_rotate and zone.next_radius > 0:
            kind, primary = "circle", None
        elif self.disengage:
            self.f8_cached = None
            return
        elif attacker is not None:
            kind, primary = "break", attacker
        elif laser is not None:
            kind, primary = "screen", laser
        elif endgame and beyond <= 0 and self.last_seen:
            kind, primary = "circle", None
        else:
            self.f8_cached = None
            return
        signature = kind, primary, zone.next_center, zone.next_radius, self.f8_hard_zone
        hit_at = self.attackers.get(primary, (-math.inf, None))[0]
        cached = self.f8_cached
        if (cached is None or cached[0] != signature or now >= cached[1]
                or (kind != "circle" and hit_at > cached[2])):
            self.f8_search_until = min(self.f8_deadline - 0.0007, time.perf_counter() + 0.00115)
            self.f8_origins_now = self.f8_origins(pos)
            point = self.f8_cover(pos, zone, radius, self.body_height, kind, primary,
                                  self.f8_origins_now, walk)
            if point is None and kind == "circle" and self.f8_rotate:
                point = self.f8_circle_anchor(pos, zone, radius)
            cached = signature, now + (0.8 if point is not None else 0.45), now, point
            self.f8_cached = cached
        point = cached[3]
        if point is not None or kind != "circle":
            self.f8_kind, self.f8_primary, self.f8_point = kind, primary, point

    def f8_laser_leg(self, pos, end):
        for ident, origin in self.f8_laser_origins.items():
            if origin is None:
                continue
            if distance_sq(end, origin) >= distance_sq(pos, origin) - 1:
                continue
            mid = ((pos[0] + end[0]) / 2, (pos[1] + end[1]) / 2, pos[2])
            if self.f8_line(origin, (*end[:2], pos[2])) or self.f8_line(origin, mid):
                self.f8_primary = ident
                return False
        return True

    def f8_progress(self, pos, goal, zone, radius, height):
        now = zone.now
        hold_distance = 0.8 if self.f8_kind is not None else eb.HOLD_M
        moving = distance_sq(pos, goal) > hold_distance ** 2 or (
            self.weapon_point is not None and self.weapon_point[2] > pos[2] + 3.5)
        moving |= self.f8_kind in ("break", "screen") and self.f8_point is None
        moving |= self.disengage and self.f8_kind != "circle"
        if not moving:
            self.f8_motion.clear()
            self.f8_recovery = None
            return None
        history = self.f8_motion
        history.append((now, pos))
        while len(history) > 1 and history[1][0] <= now - F8_MOVE_WINDOW + 1e-8:
            history.popleft()
        then, start = history[0]
        if (now - then >= F8_MOVE_WINDOW - 1e-8 and math.dist(pos, start) < F8_MOVE_MIN
                and now - self.f8_replan_at >= F8_MOVE_WINDOW - 1e-8):
            self.f8_replan_at = now
            if self.f8_kind == "circle" and self.path:
                goal = self.path[self.path_index]
            self.goal = self.search = self.route_goal = None
            self.path, self.path_index = (), 0
            self.f8_cached = None
            if self.weapon_point is not None and hasattr(self, "weapon_id"):
                self.pickup_retry[self.weapon_id] = now + 2
                self.weapon_point = None
            self.loot_point = None
            if distance_sq(pos, goal) <= hold_distance ** 2:
                threats = [p for p in self.escape_attackers.values() if p is not None]
                origin = self.shooter_origin(self.f8_primary)
                if origin is not None:
                    threats.append(origin)
                if threats:
                    yaw = bearing(min(threats, key=lambda p: distance_sq(pos, p)), pos)
                    goal = pos[0] + 12 * math.cos(yaw), pos[1] + 12 * math.sin(yaw)
            previous = self.f8_recovery[1] if self.f8_recovery is not None else goal
            self.f8_recovery = self.f8_alternate(pos, goal, previous, zone, radius, height)
        if self.f8_recovery is not None:
            expiry, point, jet = self.f8_recovery
            if now < expiry and (distance_sq(pos, point) > 1 or jet):
                self.f8_jet = jet
                return point
        return None

    def f8_alternate(self, pos, goal, previous, zone, radius, height):
        arena = self.arena
        yaw = bearing(pos, goal)
        old_yaw = bearing(pos, previous)
        best = None
        for offset in (0, 0.55, -0.55, 1.1, -1.1, 1.65, -1.65, 2.35, -2.35, math.pi):
            dx, dy = math.cos(yaw + offset), math.sin(yaw + offset)
            for span in (11, 5):
                end = pos[0] + dx * span, pos[1] + dy * span
                if arena is not None and not arena.corridor(pos, end, radius, height):
                    continue
                if self.f8_laser_origins and not self.f8_laser_leg(pos, end):
                    continue
                gap = zone.gap(end, 1.5)
                if gap < min(0, zone.gap(pos, 1.5)) - 4:
                    continue
                score = ((3 if self.f8_hard_zone else 1) * (distance(pos, goal) - distance(end, goal))
                         - 8 * max(0, math.cos(yaw + offset - old_yaw)) ** 6)
                if best is None or score > best[0]:
                    best = score, end
                break
        if (arena is not None and self.energy > eb.BOOST_RESERVE + 25
                and not arena.solid(raised(pos, height + 2))):
            probe = pos[0] + math.cos(yaw) * 7, pos[1] + math.sin(yaw) * 7
            cell = arena.cell(*probe)
            if (cell is not None and arena.step_up < arena.roof[cell] - pos[2] <= 10
                    and (best is None or best[0] < 0)
                    and not arena.obstacle((*probe, arena.roof[cell] + 0.6), radius, height)):
                return zone.now + 1.0, probe, True
        return (zone.now + 1.25, best[1], False) if best is not None else None

    def f8_travel(self, pos, point, vel, zone, radius, height, stats, grounded, energy, hold):
        span = distance(pos, point)
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        sprint = grounded and energy > eb.BOOST_RESERVE
        pace = limit(self.phys("boost_speed", 19.5, stats), walk, 90) if sprint else walk
        yaw = bearing(pos, point)
        scale = min(1, span / (walk * 0.26))
        if self.f8_jet:
            return {"move": [0.55 * math.cos(yaw), 0.55 * math.sin(yaw)],
                    "jump": grounded, "boost": not grounded and energy > eb.JET_RESERVE}
        if hold or span <= 0.75:
            return {"move": [0.0, 0.0], "boost": False, "jump": False}
        dx, dy = math.cos(yaw), math.sin(yaw)
        if self.arena is not None:
            span = min(span, max(3, pace * 0.42))
            for offset in (0, 0.38, -0.38, 0.8, -0.8):
                ux, uy = math.cos(yaw + offset), math.sin(yaw + offset)
                for drift in (1, 0.5):
                    end = (pos[0] + ux * span * drift + vel[0] * 0.07,
                           pos[1] + uy * span * drift + vel[1] * 0.07)
                    if (zone.gap(end, 0.6) >= min(-0.3, zone.gap(pos, 0.6) - 1)
                            and self.arena.corridor(pos, end, radius, height)):
                        dx, dy = ux, uy
                        scale = min(scale, 0.65) if drift < 1 else scale
                        break
                else:
                    continue
                break
            else:
                return {"move": [0.0, 0.0], "boost": False, "jump": False}
        return {"move": [dx * scale, dy * scale], "boost": sprint and scale >= 0.8, "jump": False}

    def f8_open_lanes(self, pos, exclude=()):
        if self.arena is None:
            return ()
        origins = self.f8_origins_now
        if origins is None:
            origins = self.f8_origins_now = self.f8_origins(pos)
        return tuple(origin for ident, origin in origins.items() if ident not in exclude
                     and not self.f8_line(origin, pos))

    def f8_escape_leg(self, pos, zone, radius, height):
        ident = self.f8_primary
        origin = self.shooter_origin(ident)
        if origin is not None and self.f8_blocked(origin, pos) and zone.gap(pos, F8_QUIET) >= 0:
            return pos
        _, estimate = self.attackers.get(ident, (-math.inf, None))
        threat = origin or estimate
        yaw = bearing(threat, pos) if threat is not None else bearing(pos, zone.next_center)
        shielded = self.f8_open_lanes(pos, (ident,))
        best = None
        span = distance(pos, threat) if threat is not None else 0
        for offset in (0, 0.6, -0.6, 1.2, -1.2, 1.65, -1.65, 2.4, -2.4):
            dx, dy = math.cos(yaw + offset), math.sin(yaw + offset)
            for run in (12, 5):
                end = pos[0] + dx * run, pos[1] + dy * run
                gap = zone.gap(end, 1.5)
                if gap < min(-0.3, zone.gap(pos, 1.5)) or (
                        self.arena is not None and not self.arena.corridor(pos, end, radius, height)):
                    continue
                end3 = self.f8_ground(pos, *end, radius) or (*end, pos[2])
                score = (sum(not self.f8_line(other, end3) for other in shielded),
                         self.f8_blocked(origin, end3), zone.gap(end, 6) >= 0,
                         min(0, zone.next_radius - distance(end, zone.next_center)),
                         distance(end, threat) - span if threat is not None else gap)
                if best is None or score > best[0]:
                    best = score, end
                break
            if time.perf_counter() >= self.f8_deadline - 0.0004:
                break
        return best[1] if best is not None else pos

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
            
            if ffa_enabled(F10_OPENER) and zone.now < 25 and self.kinds == {"gun"}:
                cost += (0, 13, 26)[priority]
                priority = 0
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

    def opening_escape(self, pos, zone, contacts, me):
        if zone.now >= 25 or self.f8_kind is not None or self.f9_lane or self.disengage:
            return False
        velocity = vec(me.get("vel"), 3) or eb.ZERO
        for enemy in contacts:
            if enemy.kind != "mech" or not enemy.clear or enemy.dist > 200:
                continue
            origin = self.shooter_origin(enemy.id)
            aim = PracticeEvidence.error(origin or enemy.pos, enemy.aim, raised(pos, self.body_height * 0.6))
            closing = PracticeEvidence.closing(enemy.pos, pos, enemy.vel, velocity)
            if not (aim <= PracticeEvidence.AIM or enemy.dist <= 45 or enemy.dist <= 160 and closing >= 8):
                continue
            if self.f8_blocked(origin, pos):
                continue
            stats = self.self_stats
            radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
            pace = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
            if me.get("grounded") is not False and self.energy > eb.BOOST_RESERVE + 34:
                pace = limit(self.phys("boost_speed", 19.5, stats), pace, 90)
            point = self.f10_find_cover(pos, zone, enemy, radius, min(36, pace * 2),
                                        self.f8_deadline - 0.0014, silent=True, next_ring=False)
            self.f8_kind, self.f8_primary, self.f8_point = "screen", enemy.id, point
            self.f10_opening_escape = True
            return True
        return False

    def opening_leg(self, pos, goal):
        if not ffa_enabled(F10_OPENER) or self.f8_now >= 25 or self.arena is None:
            return True
        if distance_sq(pos, goal) <= 1:
            return True
        radius = self.phys("radius", 2.5, self.self_stats)
        end = self.f8_ground(pos, *goal[:2], radius) or (*goal[:2], pos[2])
        mid = tuple((a + b) * 0.5 for a, b in zip(pos, end))
        for ident, enemy in self.observers.items():
            if time.perf_counter() >= self.f8_deadline - 0.0002:
                return False
            if distance_sq(end, enemy.pos) > 230 ** 2:
                continue
            if (not self.line_to_self(ident, enemy, pos)
                    and any(self.in_wedge(enemy, p, distance_sq(p, enemy.pos), margin=True)
                            and not self.f8_blocked(enemy.eye, p) for p in (mid, end))):
                return False
            if (distance_sq(end, enemy.pos) < min(160 ** 2, distance_sq(pos, enemy.pos))
                    and self.in_wedge(enemy, end, distance_sq(end, enemy.pos), margin=True)
                    and not self.f8_blocked(enemy.eye, end)):
                return False
        return True

    def economy_leg(self, pos, point, zone, until):
        span = distance(pos, point)
        radius = self.phys("radius", 2.5, self.self_stats)
        if (self.arena is None or span > 25 or zone.gap(point, 4) <= 2
                or distance(point, zone.next_center) > zone.next_radius - 3
                or not self.arena.corridor(pos, point, radius, self.body_height)):
            return False
        steps = max(1, math.ceil(span / 5))
        for i in range(steps + 1):
            sample = tuple(a + (b - a) * (i / steps) for a, b in zip(pos, point))
            if (time.perf_counter() >= until or self.arena.near_cover(sample) > radius + 14
                    or any(distance_sq(enemy.pos, sample) <= 280 ** 2
                           and not self.f8_blocked(enemy.eye, sample) for enemy in self.observers.values())
                    or any(distance_sq(enemy, sample) <= 120 ** 2 for _, enemy in self.rivals)):
                return False
        return True

    def economy_goal(self, obs, pos, zone, urgent):
        if (zone.now >= 120 or urgent or self.arena is None or self.farm_blocked or self.alive <= 2
                or zone.radius < 20 or distance(pos, zone.next_center) > zone.next_radius - 3
                or self.rivals and self.rivals[0][0] <= 120
                or any(distance_sq(enemy.pos, pos) <= 280 ** 2 and self.line_to_self(i, enemy, pos)
                       for i, enemy in self.observers.items())):
            return None
        target_cubes = 10 if zone.now >= 60 else 6 if zone.now >= 30 else 2
        if self.cube_count >= target_cubes:
            return None
        until = min(self.f8_deadline - 0.0010, time.perf_counter() + 0.00065)
        items = []
        for field in ("cubes", "crates") if self.alive > 3 else ("cubes",):
            for raw in seq(obs.get(field))[:64]:
                item = obj(raw)
                point, ident = vec(item.get("pos"), 3), number(item.get("id"), None)
                if point is None or ident is None or abs(point[2] - pos[2]) >= 4:
                    continue
                span = distance(pos, point)
                if span <= (25 if field == "cubes" else 65):
                    items.append((span + 12 * (field == "crates"), ident, point, field, item))
        for _, ident, point, field, item in sorted(items, key=lambda option: option[:2])[:8]:
            if time.perf_counter() >= until:
                break
            if field == "cubes":
                if not self.economy_leg(pos, point, zone, until):
                    continue
                self.economy_target = field, ident
                self.loot_point, self.mode = point, "loot"
                return point[:2]
            if (self.hp_share < 0.70 or distance(point, zone.next_center) > zone.next_radius - 3
                    or not self.economy_leg(pos, pos, zone, until)):
                continue
            d = distance(pos, point)
            if self.arena.clear_ray(raised(pos, self.phys("muzzle_height", 7, self.self_stats)), raised(point, 1.2)):
                self.economy_target = field, ident
                hp = number(item.get("hp"), 300)
                self.farm = eb.Contact(ident, "crate", point, eb.ZERO, None, hp, 300, 1, d, 0, True, False, False, ())
                return pos[:2]
        return None

    def f10_seen(self, point, skip, until, *, firing_lane=False):
        for ident, enemy in self.observers.items():
            if ident == skip:
                continue
            if time.perf_counter() >= until:
                return True
            span = distance_sq(point, enemy.pos)
            reach = max((self.f9_ranges.get(kind, 0) for kind in self.last_seen[ident].weapons),
                        default=230) if firing_lane else 0
            if ((span <= reach ** 2 or self.in_wedge(enemy, point, span, margin=True))
                    and not self.f8_blocked(enemy.eye, point)):
                return True
        return False

    def f10_find_cover(self, pos, zone, target, radius, reach, until, *, silent, next_ring=True):
        if self.arena is None:
            return None
        origin = self.shooter_origin(target.id) or raised(target.pos, 7 * target.scale)
        angle_to = bearing(pos, target.pos) + math.pi / 2
        cs, sn = math.cos(angle_to), math.sin(angle_to)
        for span in (0, 3.5, 6.5, 9.5, 13, 18, 24, 32, 36):
            if span > reach:
                break
            for dx, dy in eb.COVER_ANGLES if span else ((0, 0),):
                if time.perf_counter() >= until:
                    return None
                point = self.f8_ground(pos, pos[0] + span * (dx * cs - dy * sn),
                                       pos[1] + span * (dx * sn + dy * cs), radius, standing=not span)
                if (point is None or zone.gap(point, 3) < min(0, zone.gap(pos))
                        or next_ring and distance(point, zone.next_center) > zone.next_radius - 3
                        or not self.f8_blocked(origin, point)):
                    continue
                if span and not self.arena.corridor(pos, point, radius, self.body_height):
                    continue
                mid = tuple((a + b) * 0.5 for a, b in zip(pos, point))
                if silent and (self.f10_seen(mid, target.id, until) or self.f10_seen(point, target.id, until)):
                    continue
                return point
        return None

    def weapon_setting(self, weapon, key, fallback):
        return number(obj(weapon.get("stats")).get(key),
                      number(obj(self.weapon_config.get(weapon.get("kind"))).get(key), fallback))

    def prepare_ambush(self, obs, pos, zone, contacts, urgent):
        now = zone.now
        state = self.ambush
        laser = next((weapon for weapon in self.weapon_slots if weapon.get("kind") == "laser"), None)
        unsafe = (now < 25 or self.hp_share < 0.70 or laser is None or self.arena is None
                  or urgent or self.disengage or self.single_escape or self.f9_lane
                  or self.f9_weak is not None or self.f8_kind in ("break", "screen")
                  or self.f8_rotate or self.alive <= 2
                  or ffa_enabled(F10_DUEL) and self.alive <= 4 and now - self.last_mech_damage <= 6)
        if unsafe and state is None:
            return False
        until = min(self.f8_deadline - 0.0013, time.perf_counter() + 0.00082)
        radius = self.phys("radius", 2.5, self.self_stats)
        target = None
        if state is not None:
            target = next((c for c in contacts if c.kind == "mech" and c.id == state.target and c.hp > 0), None)
            for raw in seq(obs.get("events"))[:200]:
                event = obj(raw)
                if event.get("type") == "hit" and event.get("target") == state.target:
                    state.damage_out += max(0, number(event.get("amount")))
                elif mech_attacker(event, self.slot) == state.target:
                    state.damage_in += max(0, number(event.get("amount")))
            third_line = self.f10_seen(pos, state.target, until, firing_lane=True)
            if (state.phase != "abort" and (unsafe or third_line or target is None or state.damage_in > state.damage_out
                    or target.dist > min(200, self.weapon_setting(laser, "range", 280)))):
                state.phase, state.until = "abort", now + 2
        elif (now >= self.ambush_retry and time.perf_counter() < until
              and number(laser.get("charge")) <= 0 and number(laser.get("cooldown")) <= self.dt):
            muzzle = self.phys("muzzle_height", 7, self.self_stats)
            pitch = self.phys("min_pitch", -0.7, self.self_stats), self.phys("max_pitch", 1.3, self.self_stats)
            reach = min(200, self.weapon_setting(laser, "range", 280))
            candidates = sorted((c for c in contacts if c.kind == "mech" and c.clear and 0 < c.hp
                                 and c.dist <= reach and c.aim is not None and not c.attacker),
                                key=lambda c: (c.hp / c.max_hp - 0.3 * any(
                                    c.id in pair for pair in self.f9_shots), c.dist))
            for candidate in candidates:
                if time.perf_counter() >= until:
                    break
                origin = self.shooter_origin(candidate.id) or raised(candidate.pos, 7 * candidate.scale)
                if (PracticeEvidence.error(origin, candidate.aim, raised(pos, self.body_height * 0.60)) <= PracticeEvidence.AIM
                        or self.f10_seen(pos, candidate.id, until, firing_lane=True)
                        or self.aim_for(laser, candidate, pos, muzzle, pitch) is None):
                    continue
                self.ambush_opportunity = candidate.id
                walk = limit(self.phys("walk_speed", 11.7, self.self_stats), 2, 60)
                pace = walk * limit(self.phys("charge_move_mult", 0.5, self.self_stats), 0.1, 1)
                hold = self.weapon_setting(laser, "hold_s", 2)
                cover = self.f10_find_cover(pos, zone, candidate, radius, min(2 * walk, pace * (hold - 0.4)),
                                            until, silent=True)
                if cover is not None and distance_sq(pos, cover) > 1:
                    state = self.ambush = Peek(candidate.id, cover, pos, now)
                    target = candidate
                    self.ambush_started = candidate.id
                    break
            self.ambush_retry = now + (0.35 if state is None else 0.0)
        if state is None:
            return False
        if state.phase == "abort" or now >= state.until:
            if state.phase != "abort":
                state.phase, state.until = "abort", now + 2
            self.ambush_retry = now + 2
            if (now < state.until and not urgent and not self.f8_rotate and self.f9_point is None
                    and self.arena is not None and distance_sq(pos, state.cover) > 1.5 ** 2
                    and not self.f10_seen(state.cover, state.target, until, firing_lane=True)
                    and self.arena.corridor(pos, state.cover, radius, self.body_height)):
                self.f10_move = state.cover
            else:
                self.ambush = None
            self.ambush_abort = True
            return self.f10_move is not None
        if state.phase in ("cover", "return") and distance_sq(pos, state.cover) <= 1.5 ** 2:
            if state.phase == "return" and state.damage_out <= state.damage_in:
                if now - state.released <= 0.45:
                    self.f10_move = state.cover
                    self.f10_target = target
                    return True
                self.ambush = None
                self.ambush_retry = now + 2
                return False
            state.phase, state.until = "charge", now + 4
        if state.phase == "charge" and number(laser.get("charge")) >= self.weapon_setting(laser, "charge", 0.75) - 1e-6:
            state.phase, state.until = "peek", now + max(0.3, self.weapon_setting(laser, "hold_s", 2) - 0.1)
        elif state.phase == "charge" and not self.f8_blocked(
                self.shooter_origin(target.id) or raised(target.pos, 7 * target.scale), pos):
            self.ambush = None
            self.ambush_abort = True
            self.ambush_retry = now + 2
            return False
        self.f10_move = state.firing_pos if state.phase == "peek" else state.cover
        self.f10_target = target
        return True

    def duel_target(self, pos, zone, contacts):
        if not ffa_enabled(F10_DUEL) or self.alive > 4:
            return None
        walk = limit(self.phys("walk_speed", 11.7, self.self_stats), 2, 60)
        next_gap = zone.next_radius - distance(pos, zone.next_center)
        self.duel_rotate = (zone.next_radius > 0 and next_gap < min(10, zone.next_radius * 0.25)
                            and zone.end - zone.now <= max(0, 10 - next_gap) / walk + 8)
        burning = zone.gap(pos) <= 0 and zone.dps > 0
        if self.alive > 2 and zone.now - self.last_mech_damage > 6 and not burning and not self.duel_rotate:
            return None
        targets = [c for c in contacts if c.kind == "mech" and c.hp > 0 and c.id not in self.eliminated
                   and (c.clear or c.attacker or self.alive == 2)]
        return min(targets, key=lambda c: (not c.clear, not c.attacker, c.hp / c.max_hp, c.dist), default=None)

    def duel_movement(self, pos, zone, target, urgent):
        if (urgent or self.duel_rotate or self.f8_rotate or self.f9_lane
                or ffa_enabled(F10_CHARGE_DODGE) and self.charge_warning is not None):
            self.duel_peek = None
            return None
        now = zone.now
        state = self.duel_peek
        if state is not None and (state.target != target.id or now >= state.until
                                  or zone.gap(state.cover, 3) < 0):
            state = self.duel_peek = None
        if state is None and target.clear and self.arena is not None:
            radius = self.phys("radius", 2.5, self.self_stats)
            walk = self.phys("walk_speed", 11.7, self.self_stats)
            until = min(self.f8_deadline - 0.00135, time.perf_counter() + 0.00065)
            cover = self.f10_find_cover(pos, zone, target, radius, min(23, walk * 2), until, silent=self.alive > 2)
            if cover is not None and distance_sq(pos, cover) > 1:
                state = self.duel_peek = Peek(target.id, cover, pos, now)
        elif state is None and self.alive <= 2 and self.arena is not None:
            radius = self.phys("radius", 2.5, self.self_stats)
            muzzle = self.phys("muzzle_height", 7, self.self_stats)
            pitch = self.phys("min_pitch", -0.7, self.self_stats), self.phys("max_pitch", 1.3, self.self_stats)
            until = min(self.f8_deadline - 0.00135, time.perf_counter() + 0.00065)
            probe = self.duel_firing_position(pos, zone, target, radius, muzzle, pitch, until)
            if probe is not None:
                state = self.duel_peek = Peek(target.id, pos, probe, now)
                state.phase = "peek"
        if state is None:
            return None
        if state.phase in ("cover", "return") and distance_sq(pos, state.cover) <= 1.5 ** 2:
            state.phase, state.until = "peek", now + 2.3
        self.f10_move = state.firing_pos if state.phase == "peek" else state.cover
        return self.f10_move[:2]

    def duel_firing_position(self, pos, zone, target, radius, muzzle, pitch, until):
        weapons = [w for w in self.weapon_slots if w.get("kind") in duel_bot.KNOWN_WEAPONS]
        for run in (4, 8, 13, 20):
            for dx, dy in eb.COVER_ANGLES:
                if time.perf_counter() >= until:
                    return None
                point = self.f8_ground(pos, pos[0] + run * dx, pos[1] + run * dy, radius)
                if (point is not None and zone.gap(point, 3) >= 0
                        and distance(point, zone.next_center) <= zone.next_radius - 3
                        and self.arena.corridor(pos, point, radius, self.body_height)
                        and any(self.aim_for(w, target, point, muzzle, pitch) for w in weapons)):
                    return point
        return None

    def loot_goal(self, obs, pos, zone, contacts, weapons, hp_fraction, cubes, safe, urgent, action):
        self.f10_duel_target = self.duel_target(pos, zone, contacts)
        late_duel = ffa_enabled(F10_DUEL) and 2 < self.alive <= 4
        ambush = ffa_enabled(F10_AMBUSH)
        f8_active = ffa_enabled(F8_UNSTICK, F8_BREAK_SIGHT, F8_LASER_SCREEN, F8_CIRCLE_COVER)
        if ffa_enabled(F9_SECOND_LANE, F9_WEAK_SPACING, F9_HOLD_TRADE, F9_SUPPLY_RESET) or late_duel:
            self.f9_prepare(obs, pos, zone, urgent)
            if late_duel and self.f9_lane is not None:
                self.f10_duel_target = self.duel_peek = None
            if (self.f9_kind is not None and not self.duel_rotate and self.ambush is None
                    and (self.f9_kind != "hold-trade" or not ambush)):
                return self.f9_point[:2]
        if f8_active:
            self.f8_prepare(obs, pos, zone, urgent)
        if self.duel_rotate:
            radius = self.phys("radius", 2.5, self.self_stats)
            if not self.f8_rotate or self.f8_point is None:
                self.f8_point = self.f8_circle_anchor(pos, zone, radius)
            self.f8_kind, self.f8_rotate = "circle", True
            self.f9_kind = self.f9_point = None
        if ambush and self.prepare_ambush(obs, pos, zone, contacts, urgent):
            if self.ambush is not None:
                self.f9_kind = self.f9_point = None
            return self.f10_move[:2]
        if self.f9_point is not None and self.f9_kind != "hold-trade":
            return self.f9_point[:2]
        if ffa_enabled(F10_OPENER) and not urgent and self.opening_escape(pos, zone, contacts, obj(obs.get("self"))):
            return None
        if self.f10_duel_target is not None:
            goal = self.duel_movement(pos, zone, self.f10_duel_target, urgent)
            if goal is not None:
                self.f9_kind = self.f9_point = None
                return goal
        if self.f9_kind == "hold-trade":
            return self.f9_point[:2]
        if f8_active and self.f8_kind is not None:
            return None
        if FFA_LASER_COVER and self.laser_response_pending:
            return None
        if self.disengage or self.single_escape:
            self.mode = "escape"
            self.goal = self.search = self.route_goal = None
            self.path, self.path_index = (), 0
            return None
        if self.f9_weak is not None:
            
            return None
        economy = ffa_enabled(F10_ECONOMY)
        upgrade_weapon_safe = not economy or self.kinds == {"gun"} or (
            not self.farm_blocked and (not self.rivals or self.rivals[0][0] > 120)
            and not any(self.line_to_self(i, enemy, pos) for i, enemy in self.observers.items()))
        goal = self.weapon_goal(pos, zone, weapons, urgent or not upgrade_weapon_safe, action)
        if goal is not None:
            return goal
        if economy:
            return self.economy_goal(obs, pos, zone, urgent)
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
        for raw in () if ffa_enabled(F9_SUPPLY_RESET) else seq(obs.get("drops"))[:8]:
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
        if self.f8_kind is not None:
            return self.f8_point[:2] if self.f8_point is not None else pos[:2]
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
        near_rule = self.f18_near_rule()
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
                    if near_rule:
                        score -= min(F18_NEAR_CAP, max(0, near - F18_NEAR_M) * F18_NEAR_COST)
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

    def f21_interior(self, pos, zone):
        center = zone.next_center
        inside = zone.next_radius * eb.ZONE_INTERIOR if zone.next_radius > eb.DEATH_CIRCLE_M else 0.0
        radial = distance(pos, center)
        if radial <= inside:
            return pos[:2]
        point = tuple(c + (p - c) * inside / radial for p, c in zip(pos, center))
        if self.f21_turn:
            yaw = bearing(center, point) + self.f21_turn
            point = center[0] + inside * math.cos(yaw), center[1] + inside * math.sin(yaw)
        return self.arena.inset(point, 3) if self.arena is not None else point

    def f21_zone_first(self):
        return F21_ZONE and not self.opener_undecided and (self.f21_hurry or self.f21_stuck_at is not None)

    def f21_route(self, pos, goal, zone, radius, height, stuck, until):
        walk = limit(self.phys("walk_speed", 11.7, self.self_stats), 2, 60)
        urgent = zone.anchor(pos, walk)[1]
        out = zone.gap(pos) < 0
        late = (not urgent and not out and zone.next_radius < zone.radius and distance(pos, goal) > eb.HOLD_M
                and zone.anchor(goal, walk)[1])
        self.f21_hurry = urgent or out or late
        self.f21_hard = out or zone.gap(pos, F21_EDGE_S) < 0
        if not self.f21_hurry:
            self.f21_turn = 0.0
        elif late or self.f21_turn:
            goal = self.f21_interior(pos, zone)
            self.weapon_point = self.loot_point = None
        duel = self.f20_duel and not self.f21_zone_first()
        free = self.f9_point is None and self.f10_move is None and self.arena is not None and not duel
        if free and self.f21_path is not None and self.path is self.f21_path and (
                distance(goal, self.f21_path_goal) <= F21_KEEP_M or (
                    self.f21_hurry and distance(self.f21_path_goal, zone.next_center) < zone.next_radius - F21_KEEP_M)):
            return self.f21_follow(pos, goal, radius, height)
        self.f21_path = None
        failed = self.f21_base_failed
        if (free and failed is not None and not self.path and zone.now < failed[1]
                and distance(goal, failed[0]) <= F21_KEEP_M):
            if self.route_goal is None or distance(goal, self.route_goal) > eb.ROUTE_REPLAN_M:
                self.search, self.route_goal, self.path, self.path_index = None, goal, (), 0
            return self.f21_fallback(pos, goal, goal, zone, radius, height, until)
        saved = self.disengage, self.single_escape
        if self.f21_hard:
            self.disengage = self.single_escape = False
        self.f21_inside = True
        try:
            waypoint = self.route(pos, goal, zone, radius, height, stuck, until)
        finally:
            self.f21_inside = False
            self.disengage, self.single_escape = saved
        if not free:
            return waypoint
        return self.f21_fallback(pos, goal, waypoint, zone, radius, height, until)

    def f21_fallback(self, pos, goal, waypoint, zone, radius, height, until):
        now = zone.now
        target = self.route_goal
        if (self.search is not None or self.path or target is None
                or distance(goal, target) > eb.ROUTE_REPLAN_M):
            return waypoint
        if self.f21_base_failed is None or distance(self.f21_base_failed[0], target) > F21_KEEP_M:
            self.f21_base_failed = target, now + F21_BASE_S
        failed = self.f21_failed
        if failed is not None and (now < failed[1] or distance(failed[0], target) <= eb.ROUTE_REPLAN_M):
            return waypoint
        search = self.f21_search
        if search is None or search[0] != target:
            arena = self.arena
            start = arena.cell(*pos[:2])
            end = arena.nearest_open(target, radius, rings=6)
            if start is None or end is None or start == end:
                self.f21_failed = target, now + F21_STUCK_S
                return waypoint
            circle = None
            if self.f21_hurry and zone.next_radius > eb.DEATH_CIRCLE_M:
                circle = zone.next_center, zone.next_radius * eb.ZONE_INTERIOR
            search = self.f21_search = target, ClimbSearch(arena, start, end, radius, self.f21_blocked, circle)
        path = search[1].advance(min(until, time.perf_counter() + eb.ROUTE_SLICE_S))
        if not search[1].done:
            return waypoint
        self.f21_search = None
        if not path:
            self.f21_failed = target, now + F21_STUCK_S
            return waypoint
        self.path, self.path_index = path, 0
        self.f21_path, self.f21_path_goal = path, target
        return self.f21_follow(pos, goal, radius, height)

    def f21_follow(self, pos, goal, radius, height):
        path, arena = self.path, self.arena
        i = self.path_index
        while i + 1 < len(path) and distance(pos, path[i]) < 2.7:
            i += 1
        if i + 1 == len(path) and distance(pos, path[i]) < 2.7:
            self.path_index = i
            return goal
        for j in range(min(i + eb.ROUTE_LOOKAHEAD_CELLS, len(path) - 1), i, -1):
            if (all(arena.roof[arena.cell(*point)] <= pos[2] + arena.step_up for point in path[i:j + 1])
                    and arena.corridor(pos, path[j], radius, height)):
                i = j
                break
        self.path_index = i
        return path[i]

    def f21_movement(self, pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction, stats,
                     grounded, energy, now, until, in_zone, terminal_burn, drop_hint):
        saved = self.disengage, self.single_escape
        if self.f21_hard:
            self.disengage = self.single_escape = False
        self.f21_inside = True
        try:
            move = self.movement(pos, vel, waypoint, zone, urgent or self.f21_hurry, evade, threats, hazards,
                                 direction, stats, grounded, energy, now, until, in_zone, terminal_burn, drop_hint)
        finally:
            self.f21_inside = False
            self.disengage, self.single_escape = saved
        climbing = self.f21_path is not None and self.path is self.f21_path
        move = self.f21_unstick(pos, waypoint, move, grounded, energy, now, climbing)
        reserve = F21_CLIMB_ENERGY if climbing else eb.BOOST_RESERVE
        if (self.f21_hurry and grounded and not move.get("jump") and energy > reserve
                and math.hypot(*move["move"]) > 0.2):
            move["boost"] = self.sprinting = True
        return move

    def f21_leap(self, yaw, grounded, energy, now):
        jump = grounded and energy > eb.JET_RESERVE
        if jump:
            self.f21_jump_at = now
        jet = not grounded and now - self.f21_jump_at < F21_JET_S and energy > eb.JET_RESERVE
        self.course = [math.cos(yaw), math.sin(yaw)]
        self.sprinting = jet
        return {"move": list(self.course), "boost": jet, "jump": jump}

    def f21_unstick(self, pos, waypoint, move, grounded, energy, now, climbing):
        track = self.f21_track
        span = math.hypot(*move["move"])
        unit = (move["move"][0] / span, move["move"][1] / span) if span > 0.2 else (0.0, 0.0)
        track.append((now, pos, unit))
        while len(track) > 1 and track[1][0] <= now - F21_STUCK_S:
            track.popleft()
        then, start, _ = track[0]
        if self.f21_stuck_at is None:
            if self.f21_climb is None or self.f21_climb[0] != self.path_index:
                self.f21_climb = self.path_index, now
            if (climbing and self.arena is not None and distance(pos, waypoint) < 6
                    and now - self.f21_climb[1] < 2 * F21_JUMP_S):
                cell = self.arena.cell(*waypoint[:2])
                if cell is not None and (self.arena.roof[cell] > pos[2] + self.arena.step_up + 0.3
                                         or (not grounded and now - self.f21_jump_at < F21_JET_S)):
                    return self.f21_leap(bearing(pos, waypoint), grounded, energy, now)
            if span <= 0.2 or not grounded:
                self.f21_moving_since = None
                return move
            if self.f21_moving_since is None:
                self.f21_moving_since = now
            heading = math.hypot(sum(u[0] for _, _, u in track), sum(u[1] for _, _, u in track)) / len(track)
            progress = distance(start, waypoint) - distance(pos, waypoint)
            if (now - self.f21_moving_since < F21_STUCK_S or now - then < F21_STUCK_S - 0.15
                    or distance(pos, start) >= F21_STUCK_M or distance(pos, waypoint) <= 3
                    or (heading < 0.35 and progress >= 0.5)):
                return move
            self.f21_stuck_at = now
            self.f21_attempts += 1
        else:
            recent = next(p for t, p, _ in track if t >= now - 1.0)
            if (span <= 0.2 and not self.f21_hurry) or (
                    now - self.f21_stuck_at >= 1.0 and distance(pos, recent) >= F21_FREE_M):
                self.f21_stuck_at = self.f21_moving_since = None
                return move
        age = now - self.f21_stuck_at
        cycle = F21_JUMP_S + F21_STRAFE_S
        side = 1 if (self.f21_attempts + int(age // cycle)) % 2 else -1
        yaw = bearing(pos, waypoint) if distance(pos, waypoint) > 0.5 else math.atan2(unit[1], unit[0])
        strafe = age % cycle >= F21_JUMP_S
        if strafe:
            yaw += side * F21_STRAFE
            if self.f21_replanned < now - age % cycle + F21_JUMP_S - 1e-6:
                self.f21_replanned = now
                if self.arena is not None and (cell := self.arena.cell(*waypoint[:2])) is not None:
                    self.f21_blocked.append(cell)
                self.search = self.route_goal = self.goal = self.f21_search = self.f21_failed = None
                self.f21_path = None
                self.path, self.path_index = (), 0
                if self.f21_hurry:
                    self.f21_turn = angle(self.f21_turn + side * F21_TURN)
        return self.f21_leap(yaw, grounded, energy, now)

    def route(self, pos, goal, zone, radius, height, stuck, until):
        if F21_ZONE and not self.f21_inside and not self.opener_undecided:
            return self.f21_route(pos, goal, zone, radius, height, stuck, until)
        if (self.f20_duel and not self.f21_zone_first()
                and (duel := self.f20_goal(pos, zone, radius, height, until)) is not None):
            self.f20_moving = True
            return super().route(pos, duel, zone, radius, height, stuck, until)
        if self.f9_point is not None:
            return self.f9_point[:2]
        if self.f10_move is not None:
            return self.f10_move[:2]
        if self.f10_duel_target is not None:
            until = min(until, self.f8_deadline - 0.0006)
        if self.f8_point is not None:
            goal = self.f8_point[:2]
        elif self.f8_kind in ("break", "screen"):
            goal = pos[:2]
        elif ffa_enabled(F8_CIRCLE_COVER) and self.alive <= 3 and not self.disengage and zone.next_radius > 0:
            interior = zone.next_radius - min(15, zone.next_radius * 0.25)
            if distance(pos, zone.next_center) <= interior < distance(goal, zone.next_center):
                goal = pos[:2]
        self.f8_goal = goal
        if ffa_enabled(F8_UNSTICK):
            alternate = self.f8_progress(pos, goal, zone, radius, height)
            if alternate is not None:
                self.f8_goal = alternate
                return alternate
        if self.f8_kind is not None:
            arena = self.arena
            if (self.f8_kind != "circle" or arena is None or distance_sq(pos, goal) <= 1
                    or (distance_sq(pos, goal) <= 24 ** 2 and arena.corridor(pos, goal, radius, height))):
                return goal
            waypoint = super().route(pos, goal, zone, radius, height, False,
                                     min(until, time.perf_counter() + 0.0015), waypoint_span=14)
            if self.search is None and not self.path and self.route_goal == goal:
                self.f8_failed_circle = goal
                self.f8_cached = self.route_goal = None
            return waypoint if self.path or waypoint != goal else pos[:2]
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
        if self.f8_laser_origins and not self.f8_laser_leg(pos, waypoint):
            self.f8_kind = "screen"
            self.weapon_point = None
            return pos[:2]
        if pickup is not None:
            follows_path = (self.path and (self.route_goal == goal or
                            (FFA_PICKUP_TAPER and waypoint == self.path[self.path_index])))
            points = self.path[self.path_index:] if follows_path else ()
            unsafe = not self.safe_pickup_route(pos, waypoint) or not self.opening_leg(pos, waypoint) or any(
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
        shielded = self.f8_open_lanes(pos) if ffa_enabled(F8_BREAK_SIGHT) and self.disengage else ()
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
            new_lines = sum(time.perf_counter() >= self.f8_deadline - 0.0004
                            or self.f8_line(origin, (*end, pos[2])) for origin in shielded)
            option = (worst > 0, -new_lines, score)
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
        if F21_ZONE and not self.f21_inside and not self.opener_undecided:
            return self.f21_movement(pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction, stats,
                                     grounded, energy, now, until, in_zone, terminal_burn, drop_hint)
        move = self.ffa_movement(pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction,
                                 stats, grounded, energy, now, until, in_zone, terminal_burn, drop_hint)
        if ffa_enabled(F9_NO_QUIET) and (urgent or not in_zone) and grounded and not move.get("jump"):
            reserve = eb.BOOST_RESERVE if in_zone else eb.JET_RESERVE
            if energy > reserve and math.hypot(*move["move"]) > 0.2:
                move["boost"] = self.sprinting = True
        if (self.f16_unquiet and 0 <= now - self.last_damage <= F16_BOOST_S and grounded and not move.get("jump")
                and energy > eb.BOOST_RESERVE and math.hypot(*move["move"]) > 0.2):
            move["boost"] = self.sprinting = True
        return move

    def ffa_movement(self, pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction, stats,
                     grounded, energy, now, until, in_zone, terminal_burn, drop_hint):
        if self.f10_duel_target is not None:
            until = min(until, self.f8_deadline - 0.00045)
        if self.f20_moving:
            move = self.f20_duel_move(pos, vel, waypoint, zone, threats, hazards, direction, stats, grounded, energy,
                                      now, until, in_zone, terminal_burn, drop_hint)
            self.course, self.sprinting = move["move"], bool(move.get("boost"))
            return move
        if self.f10_move is not None:
            span = distance(pos, self.f10_move)
            yaw = bearing(pos, self.f10_move)
            scale = 0 if span <= 0.85 else min(1, span / 2.5)
            self.course = [scale * math.cos(yaw), scale * math.sin(yaw)]
            return {"move": self.course, "boost": False, "jump": False}
        if self.f9_point is not None:
            span = distance(pos, self.f9_point)
            walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
            scale = 0 if span <= 0.75 else min(1, span / (walk * 0.26))
            yaw = bearing(pos, self.f9_point)
            self.course = [scale * math.cos(yaw), scale * math.sin(yaw)]
            self.sprinting = grounded and energy > eb.BOOST_RESERVE and scale >= 0.8
            self.mode = self.f9_kind
            return {"move": self.course, "boost": self.sprinting, "jump": False}
        recovery = self.f8_recovery
        recovering = recovery is not None and waypoint == recovery[1] and now < recovery[0]
        if self.f8_kind is not None or recovering:
            radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
            point = waypoint
            hold = False
            if not recovering and self.f8_kind in ("break", "screen") and self.f8_point is None:
                point = self.f8_escape_leg(pos, zone, radius, self.body_height)
                self.f8_goal = point[:2]
            elif not recovering and self.f8_point is not None:
                hold = distance_sq(pos, self.f8_point) <= 0.85 ** 2 and (
                    zone.gap(pos, F8_HOLD_SAFE) >= 0 or self.f8_kind == "circle")
            action = self.f8_travel(pos, point, vel, zone, radius, self.body_height, stats, grounded, energy, hold)
            self.course, self.sprinting = action["move"], action["boost"]
            self.mode = self.f8_kind or "unstick"
            return action
        if FFA_LASER_COVER and self.laser_response_pending:
            response = self.laser_move(pos, vel, zone, stats, grounded, energy)
            if response is not None:
                self.course, self.sprinting = response["move"], response["boost"]
                return response
        free = not urgent and in_zone and not terminal_burn and zone.radius >= F16_FINAL_M
        if free and self.f18(F18_BREAK) and self.f18_threat is not None:
            response = self.f18_move(pos, zone, stats, grounded, energy, now, until)
            if response is not None:
                self.course, self.sprinting = response["move"], bool(response.get("boost"))
                return response
        if free and self.f16(F16_RUSH) and self.f16_rusher is not None and not self.f18_supersedes_rush():
            response = self.f16_rush_move(pos, vel, zone, threats, hazards, stats, grounded, energy, now, until,
                                          in_zone, terminal_burn)
            self.course, self.sprinting = response["move"], bool(response.get("boost"))
            return response
        if free and self.f16(F16_DRONE) and self.f16_grave is not None and not self.exposed:
            cube = self.f16_cube(pos, waypoint, zone)
            if cube is not None:
                waypoint = cube
                self.mode = "drone-cube"
        if free and self.f18_near_rule():
            point = self.f18_open_hold(pos, zone, limit(self.phys("radius", 2.5, stats), 0.5, 25), now)
            if point is not None:
                waypoint = point
                self.mode = "near-cover"
        if free and self.f20(F20_SCAV) and not self.f20_duel:
            cube = self.f20_cube(pos, waypoint, zone, now)
            if cube is not None:
                waypoint = cube
                self.mode = "f20-scav"
        fast_arm = (FFA_ARM_FAST and self.weapon_point is not None and self.kinds == {"gun"}
                    and 0 <= now - self.first_ffa_time < FFA_ARM_S and self.hp >= FFA_ARM_HP and not urgent)
        quiet = (not (fast_arm or self.single_escape or (ffa_enabled(F8_UNSTICK) and urgent))
                 and not self.laser_response_pending
                 and self.walk_quietly(pos, urgent, in_zone))
        economy = ffa_enabled(F10_ECONOMY)
        speed_cap = self.quiet_speed if quiet else None
        steer_score = self.steer_score if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) else None
        if self.disengage or self.single_escape:
            escape = self.escape_move(pos, vel, waypoint, zone, hazards, stats, grounded, energy, urgent, quiet)
            if escape is not None:
                if FFA_PICKUP_TAPER and not self.single_escape and not economy:
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
            if not self.safe_pickup_route(pos, projected) or not self.opening_leg(pos, projected):
                self.weapon_point = None
                self.mode = "survive"
                cover = self.shelter_point(pos, zone, (), direction, self.phys("radius", 2.5, stats),
                                           self.phys("height", 9, stats), now, until, terminal_burn)
                quiet = self.walk_quietly(pos, urgent, in_zone)
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
        if FFA_PICKUP_TAPER and not self.single_escape and not economy:
            self.sweep_cube(pos, zone, stats, move)
        if economy and self.loot_point is not None:
            end = (pos[0] + move["move"][0] * 5, pos[1] + move["move"][1] * 5)
            point = self.f8_ground(pos, *end, self.phys("radius", 2.5, stats))
            if point is None or not self.economy_leg(pos, point, zone, until):
                self.loot_point = self.economy_target = None
                move = {"move": [0.0, 0.0], "boost": False, "jump": False}
        if self.f8_laser_origins:
            span = min(12, distance(pos, waypoint))
            projected = pos[0] + span * move["move"][0], pos[1] + span * move["move"][1]
            if not self.f8_laser_leg(pos, projected):
                self.f8_kind = self.mode = "screen"
                self.weapon_point = None
                radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
                point = self.f8_escape_leg(pos, zone, radius, self.body_height)
                self.f8_goal = point[:2]
                move = self.f8_travel(pos, point, vel, zone, radius, self.body_height, stats,
                                      grounded, energy, False)
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
        if (self.f9_kind is not None or self.f9_trade or self.f9_weak is not None
                or ffa_enabled(F10_DUEL) and 2 < self.alive <= 4 and self.f9_lane is not None):
            return []
        if self.single_escape or self.f8_attacker is not None and self.alive > 2 and not self.disengage:
            return []
        options = []
        now = zone.now
        returning = {ident for ident, _ in self.f16_gunners(pos, now)} if self.f16(F16_RETURN) else ()
        rusher = self.f16_rusher.id if self.f16(F16_RUSH) and self.f16_rusher is not None else None
        threat = self.f18_threat if self.f18(F18_BREAK) else None
        for enemy in contacts:
            if enemy.kind != "mech" or not enemy.clear or enemy.id in self.eliminated:
                continue
            if self.f8_kind == "screen" and enemy.dist > 30:
                continue
            if enemy.id == threat:
                options.append((120 - enemy.dist * 0.1, enemy))
                continue
            if enemy.id in returning or enemy.id == rusher:
                options.append((100 - enemy.dist * 0.1, enemy))
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
        if self.f16(F16_DRONE) and self.f16_drone_target is not None:
            options.append((70 - self.f16_drone_target.dist * 0.1, self.f16_drone_target))
        quiet = self.f18(F18_QUIET) and now <= F18_WINDOW_S
        if quiet:
            options = self.f18_quiet(options, now)
        if options:
            return sorted(options, key=lambda option: option[0], reverse=True)
        if quiet and self.farm is not None and self.f18_alarm and self.farm.id != self.f18_prev_target:
            return []
        return [(50, self.farm)] if self.farm is not None and not self.farm_blocked else []

    def aim_for(self, weapon, target, base, muzzle, pitch_bounds):
        
        if target.kind != "mech" and weapon.get("kind") != "gun":
            return None
        return super().aim_for(weapon, target, base, muzzle, pitch_bounds)

    def combat(self, obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy, fraction, zone,
               action, until, terminal_burn, repairing, incoming):
        ambush = self.ambush if self.f10_target is not None else None
        target = self.f10_target or self.f10_duel_target
        if target is None:
            if self.ambush_abort:
                action["fire"] = [False, False]
                action["aim"] = [actual[0], self.phys("max_pitch", 1.3, stats)]
                return
            chosen = self.f20_enemy if self.f20_duel else self.f20_target
            if chosen is not None:
                return self.f20_fire(pos, weapons, actual, stats, chosen, energy, action)
            if self.f20_duel and self.f20_point is not None:
                action["fire"] = [False, False]
                action["aim"] = [bearing(pos, self.f20_point), 0.0]
                return
            super().combat(obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy,
                           fraction, zone, action, until, terminal_burn, repairing, incoming)
            if self.f20(F20_USE2):
                self.f20_second(pos, weapons, actual, stats, contacts, energy, action)
            return

        state = ambush or self.duel_peek
        firing = action["fire"] = [False, False]
        muzzle = self.phys("muzzle_height", 7, stats)
        pitch = self.phys("min_pitch", -0.7, stats), self.phys("max_pitch", 1.3, stats)
        yaw_step = self.phys("turn_rate", 4, stats) * self.physics_dt * 0.50
        pitch_step = self.phys("pitch_rate", 3, stats) * self.physics_dt * 0.50
        plans = []
        for index, weapon in enumerate(weapons):
            kind = weapon.get("kind")
            if (kind not in duel_bot.KNOWN_WEAPONS or ambush is not None and kind != "laser"
                    or kind == "gun" and (number(weapon.get("reload")) > 0 or number(weapon.get("ammo"), 1) <= 0)
                    or kind == "lightning" and energy < 4):
                if kind == "gun" and number(weapon.get("ammo"), 1) <= 0 and not number(weapon.get("reload")):
                    action["reload"] = True
                continue
            plan = self.aim_for(weapon, target, pos, muzzle, pitch)
            cooldown = number(weapon.get("cooldown"))
            charge = number(weapon.get("charge"))
            full = self.weapon_setting(weapon, "charge", 0.75) if kind == "laser" else 0
            is_full = charge >= full - 1e-6
            if ambush is not None:
                if state.phase == "charge":
                    firing[index] = cooldown <= self.physics_dt or charge > 0
                elif state.phase == "peek":
                    firing[index] = charge > 0
                if state.phase != "peek" or not is_full:
                    plan = None
            elif kind == "laser" and charge > 0 and not (must_move or self.duel_rotate):
                firing[index] = True
            if plan is None:
                if kind == "laser" and state is not None:
                    peek_plan = self.aim_for(weapon, target, state.firing_pos, muzzle, pitch)
                    if peek_plan is not None:
                        action["aim"] = list(peek_plan[:2])
                        if ambush is None and state.phase == "peek" and not target.clear and cooldown <= self.physics_dt:
                            firing[index] = True
                continue
            aligned = (abs(angle(plan[0] - actual[0])) <= plan[2] + yaw_step
                       and (kind == "lightning" or abs(plan[1] - actual[1]) <= plan[3] + pitch_step))
            ready = cooldown <= (self.physics_dt if kind == "laser" else self.dt + 0.025)
            shoot = aligned and ready and (kind != "laser" or is_full or charge > 0 and (must_move or self.duel_rotate))
            prepare = (kind == "laser" and ambush is None and ready and not (must_move or self.duel_rotate)
                       and (state is None or state.phase in ("cover", "peek")))
            priority = (shoot, {"laser": 4, "gun": 3, "lightning": 2, "mortar": 1}[kind] if ready else 0)
            plans.append((priority, index, kind, plan, aligned, shoot, prepare))
        if not plans:
            return
        _, index, kind, plan, aligned, shot, prepare = max(plans, key=lambda item: item[0])
        action["aim"] = list(plan[:2])
        self.last_fire_target = target.id
        if kind == "laser":
            firing[index] = not shot and (firing[index] or prepare and aligned)
        else:
            firing[index] = shot
            for _, other, other_kind, side, other_aligned, _, other_prepare in plans:
                if (other_kind == "laser" and other_prepare and other_aligned
                        and abs(angle(plan[0] - side[0])) <= side[2] and abs(plan[1] - side[1]) <= side[3]):
                    firing[other] = True
        if shot:
            self.f10_shot = kind
            if state is not None and (ambush is not None or state.phase == "peek"):
                state.phase, state.until, state.released = "return", zone.now + 2.3, zone.now
                if not must_move and not self.duel_rotate:
                    span = distance(pos, state.cover)
                    yaw = bearing(pos, state.cover)
                    pace = min(1, span / 2.5)
                    action["move"] = [pace * math.cos(yaw), pace * math.sin(yaw)]
                    action["boost"] = False

    def contacts(self, obs, pos, eye):
        contacts = super().contacts(obs, pos, eye)
        self.exposed = any(c.kind == "mech" and c.clear and c.dist < 100 for c in contacts)
        if self.f16(True):
            self.f16_scan(contacts, pos)
        if self.f18(True):
            self.f18_scan(contacts, pos)
        if self.f20(True):
            self.f20_scan(obs, contacts, pos)
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

    def watch_charge(self, obs, me, pos, now):
        warning = self.charge_warning
        starts, releases = [], []
        for raw in seq(obs.get("sounds"))[:40]:
            sound = obj(raw)
            kind = sound.get("kind")
            if kind not in ("laser_charge", "laser"):
                continue
            yaw, age = number(sound.get("bearing"), None), number(sound.get("age"))
            if yaw is None or not 0 <= age <= 0.8:
                continue
            when = now - age
            if kind == "laser_charge" and when > self.last_charge_sound + 1e-6:
                starts.append((when, yaw, sound.get("dist")))
            elif kind == "laser":
                releases.append((when, yaw))
        if starts:
            self.last_charge_sound = max(start[0] for start in starts)

        visible, charging, stopped = {}, {}, set()
        scale_per_cube = number(self.cubes.get("size_per_cube"), 0.05)
        eye = raised(pos, number(self.self_stats.get("eye_height"),
                                 self.phys("eye_height", 8) * (1 + scale_per_cube * self.cube_count)))
        body = raised(pos, self.body_height * 0.58)
        sensors = seq(me.get("upgrades")).count("sensors")
        for raw in seq(obs.get("mechs"))[:48]:
            enemy = obj(raw)
            ident = number(enemy.get("id"), -1)
            if enemy.get("kind") != "mech" or ident not in range(16) or ident == self.slot:
                continue
            if enemy.get("charging") is not True or number(enemy.get("hp"), 1) <= 0:
                stopped.add(ident)
                self.charge_handled.pop(ident, None)
                continue
            if ident in self.charge_handled:
                self.charge_handled[ident] = now
            point = vec(enemy.get("pos"), 3)
            aim = vec(enemy.get("aim"), 2)
            if point is None:
                continue
            span, yaw = distance(pos, point), bearing(pos, point)
            size = 1 + scale_per_cube * limit(number(enemy.get("cubes")), 0, 100)
            origin = raised(point, self.phys("muzzle_height", 7) * size)
            charging[ident] = origin
            error = self.f9_aim_error(*aim, origin, body) if aim is not None else math.inf
            if (error > self.CHARGE_AIM_RAD and not starts and (warning is None or warning.shooter is not None)
                    or span > self.vision + 25 * sensors
                    or span > self.near_vision + 15 * sensors and abs(angle(yaw - self.actual[0])) > self.half_fov):
                continue
            if self.arena is None or any(self.arena.clear_ray(eye, raised(point, height * size))
                                         for height in (4.5, 9)):
                visible[ident] = ChargingRival(origin, yaw, span, error, angle(aim[0] + math.pi) if aim else yaw)
        self.charge_handled = {ident: last for ident, last in self.charge_handled.items() if now - last <= 3}
        self.charge_started = {ident: self.charge_started.get(ident, now) for ident in charging}
        fired = {beam.get("by") for raw in seq(obs.get("beams"))[:32]
                 if (beam := obj(raw)).get("kind") == "laser" and type(beam.get("by")) in (int, float)}
        for raw in seq(obs.get("events"))[:200] if warning is not None else ():
            event = obj(raw)
            if event.get("weapon") == "laser" and (source := mech_attacker(event, self.slot)) is not None:
                fired.add(source)

        def heard_release(when, yaw):
            return any(released + 1e-6 >= when and abs(angle(sound_yaw - yaw)) <= self.charge_sound_tolerance
                       for released, sound_yaw in releases)

        if warning is not None:
            shooter = warning.shooter
            if shooter in stopped or shooter in fired or (shooter not in charging
                    and heard_release(warning.heard_at, bearing(pos, warning.origin))) or now >= warning.until:
                self.charge_warning = None
            else:
                if shooter is None and visible:
                    yaw = bearing(pos, warning.origin)
                    closest = min(visible, key=lambda ident: abs(angle(yaw - visible[ident].bearing)))
                    if abs(angle(yaw - visible[closest].bearing)) <= self.charge_sound_tolerance:
                        warning.shooter = shooter = closest
                        self.charge_handled[shooter] = now
                        warning.cover = None
                if shooter in charging:
                    warning.origin = charging[shooter]
                if shooter in visible and visible[shooter].aim_error <= self.CHARGE_AIM_RAD:
                    warning.yaw = visible[shooter].heading
                return warning

        directed = [(error, span, ident, origin, heading) for ident, (origin, _, span, error, heading) in visible.items()
                    if error <= self.CHARGE_AIM_RAD and ident not in self.charge_handled and ident not in fired]
        if directed:
            _, _, shooter, origin, yaw = min(directed)
            self.charge_handled[shooter] = now
            self.charge_warning = ChargeWarning(shooter, yaw, origin, self.charge_started[shooter], now)
        else:
            for when, yaw, band in sorted(starts, reverse=True, key=lambda start: start[0]):
                if heard_release(when, yaw) or any(
                        (span < 62 if band == "near" else 58 <= span < 162 if band == "mid"
                         else span >= 158 if band == "far" else True)
                        and abs(angle(yaw - direction)) <= self.charge_sound_tolerance
                        for _, direction, span, _, _ in visible.values()):
                    continue
                reach = {"near": 42, "mid": 100, "far": 175}.get(band, 100) if isinstance(band, str) else 100
                origin = pos[0] + reach * math.cos(yaw), pos[1] + reach * math.sin(yaw), pos[2] + 7
                self.charge_warning = ChargeWarning(None, yaw, origin, when, now)
                break
        return self.charge_warning

    def dodge_charge(self, obs, me, pos, now):
        stats = self.self_stats
        self.body_height = limit(self.phys("height", 9, stats), 1, 80)
        warning = self.watch_charge(obs, me, pos, now)
        if warning is None:
            return None
        self.ambush = self.duel_peek = None
        arena = self.arena
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        grounded = me.get("grounded") is not False
        drain = self.phys("boost_drain", 17, stats) if grounded else self.phys("jet_drain", 28, stats)
        boost = self.energy > self.dt * max(0, drain)
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        pace = limit(self.phys("boost_speed", 19.5, stats), walk, 90) if boost and grounded else walk
        zone = obj(obs.get("zone"))
        center = vec(zone.get("center"), 2) or pos[:2]
        safe_radius = max(number(zone.get("radius"), 560), distance(pos, center))
        route = warning.cover
        cs, sn = -math.sin(warning.yaw), math.cos(warning.yaw)
        if route is not None and not self.f8_blocked(warning.origin, route):
            route = warning.cover = None
        if arena is not None and route is None and grounded:
            
            remaining = max(0, 0.8 - (now - warning.heard_at))
            accel = max(2, self.phys("ground_accel", 58.5, stats))
            acceleration_time = min(remaining, pace / accel)
            reach = pace * (remaining - acceleration_time) + accel * acceleration_time ** 2 / 2
            until = min(self.f8_deadline - 0.0004, time.perf_counter() + 0.00065)
            if reach >= 2 and arena.near_cover(pos) <= reach + radius + 12:
                for span in (reach / 3, 2 * reach / 3, reach):
                    for dx, dy in eb.COVER_ANGLES:
                        if time.perf_counter() >= until:
                            break
                        point = self.f8_ground(pos, pos[0] + span * (dx * cs - dy * sn),
                                              pos[1] + span * (dx * sn + dy * cs), radius)
                        if (point is not None and distance(point, center) <= safe_radius
                                and arena.corridor(pos, point, radius, self.body_height)
                                and self.f8_blocked(warning.origin, point)):
                            route = warning.cover = point
                            break
                    if route is not None or time.perf_counter() >= until:
                        break
        if route is not None and distance_sq(pos, route) > 1.0:
            yaw = bearing(pos, route)
            speed = min(1, distance(pos, route) / (pace * max(self.dt, 0.16)))
            move = [speed * math.cos(yaw), speed * math.sin(yaw)]
            jump = False
        else:
            options = []
            for side in (warning.side, -warning.side):
                for span in (max(3, pace * 0.28), 2):
                    end = pos[0] + side * span * cs, pos[1] + side * span * sn, pos[2]
                    clear = arena is None or arena.corridor(pos, end, radius, self.body_height)
                    screened = route is not None and clear and self.f8_blocked(warning.origin, end)
                    options.append(((clear, distance(end, center) <= safe_radius, screened, span),
                                    side, min(1, span / max(3, pace * 0.28))))
            _, warning.side, speed = max(options, key=lambda option: option[0])
            move = [speed * warning.side * cs, speed * warning.side * sn]
            lifted = arena is None or not arena.obstacle(raised(pos, self.phys("step_up", 1.2, stats) + 1),
                                                        radius, self.body_height, 0.55)
            jump = route is None and grounded and lifted
            if not grounded and not lifted:
                boost = False
        return {"move": move, "boost": boost, "jump": jump}

    def act(self, obs):
        f8_active = ffa_enabled(F8_UNSTICK, F8_BREAK_SIGHT, F8_LASER_SCREEN, F8_CIRCLE_COVER,
                                F9_SECOND_LANE, F9_WEAK_SPACING, F9_HOLD_TRADE, F9_SUPPLY_RESET,
                                F10_OPENER, F10_ECONOMY, F10_AMBUSH, F10_DUEL, F10_CHARGE_DODGE)
        self.f8_deadline = time.perf_counter() + F8_FFA_BUDGET if f8_active else math.inf
        self.f8_kind = self.f8_primary = self.f8_point = self.f8_goal = None
        self.f8_hard_zone = self.f8_rotate = self.f8_jet = False
        self.f8_laser_origins = {}
        self.f8_origins_now = None
        self.f9_kind = self.f9_point = self.f9_lane = self.f9_weak = self.f9_trade = None
        self.f10_move = self.f10_target = self.f10_duel_target = self.f10_shot = None
        self.ambush_opportunity = self.ambush_started = self.economy_target = None
        self.ambush_abort = self.duel_rotate = self.f10_opening_escape = False
        errors = (ArithmeticError, LookupError, TypeError, ValueError, AttributeError)
        self.mode = "survive"
        self.weapon_point = self.loot_point = self.fight = self.farm = None
        self.climb = self.sprinting = False
        self.single_escape = False
        self.course = (0.0, 0.0)
        self.escape_bearings = []
        self.laser_response_pending = False
        self.nearby_take = (None, None)
        self.f16_unquiet = False
        self.f16_rusher = self.f16_drone_target = None
        self.f16_cubes = obs.get("cubes") if F16_UNDERFIRE else None
        self.f18_alarm = False
        self.f20_reset()
        me = obj(obs.get("self"))
        now, pos = number(obs.get("t"), 0), vec(me.get("pos"), 3)
        self.f8_now = now
        self.actual = vec(me.get("aim"), 2) or (0, 0)
        self.self_stats = obj(me.get("stats"))
        offer = seq(obj(obs.get("offer")).get("choices"))[:3]
        dodge = None
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
            self.last_fire_target = None
            if pos is not None:
                if ffa_enabled(F10_CHARGE_DODGE):
                    dodge = self.dodge_charge(obs, me, pos, now)
                    if dodge is not None and not (ffa_enabled(F10_DUEL) and self.alive == 2):
                        self.mode = "charge-cover" if self.charge_warning.cover is not None else "charge-dodge"
                        self.course, self.sprinting = dodge["move"], dodge["boost"]
                        dodge.update(aim=list(self.actual), fire=[False, False])
                        self.release_laser_safely(obs, dodge, pos)
                        return self.pick_upgrade(offer, me, dodge)
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
                if ffa_enabled(F8_BREAK_SIGHT):
                    self.f8_hit_response(pos, now)
                
                self.hits.update({ident: when for ident, (when, _) in self.attackers.items()
                                  if 0 <= now - when < eb.HIT_MEMORY_S})
            action = super().act(obs, deadline=self.f8_deadline if f8_active else None)
            if pos is not None:
                if self.f10_target is not None or self.f10_duel_target is not None or self.ambush_abort:
                    pass
                elif self.f20_duel and self.f20_point is not None:
                    if self.last_fire_target is None:
                        action["aim"] = [bearing(pos, self.f20_point), 0.0]
                elif self.f8_kind in ("break", "screen") and self.last_fire_target is None:
                    _, estimate = self.attackers.get(self.f8_primary, (-math.inf, None))
                    origin = self.shooter_origin(self.f8_primary) or estimate
                    if origin is not None:
                        action["aim"] = [bearing(pos, origin), 0.0]
                elif (self.last_fire_target is None and self.f18(F18_BREAK) and self.f18_threat is not None
                      and (point := self.f18_threat_pos(self.f18_threat)) is not None):
                    action["aim"] = [bearing(pos, point), 0.0]
                elif (self.disengage or self.single_escape) and self.last_fire_target is None and not self.laser_response_pending:
                    action["aim"] = [self.escape_facing(), 0.0]
                elif (self.last_fire_target is None and self.f16(F16_RETURN)
                      and (gunner := next(self.f16_gunners(pos, now), None)) is not None):
                    action["aim"] = [bearing(pos, gunner[1]), 0.0]
                elif self.last_fire_target is None and self.weapon_point is not None and not self.exposed:
                    action["aim"] = [bearing(pos, self.weapon_point), 0.0]
                elif self.last_fire_target is None and now - self.last_damage >= eb.HIT_MEMORY_S:
                    if (FFA_PICKUP_TAPER and self.opening and self.kinds.isdisjoint(self.SECONDARIES)
                            and not self.farm_blocked and math.hypot(*self.course) > 0.2):
                        action["aim"] = [math.atan2(self.course[1], self.course[0]), 0.0]
                    elif not self.rivals:
                        action["aim"] = [angle(self.scout_yaw + now * 1.9), 0.0]
                action.setdefault("fire", [False, False])
                if (self.f8_attacker is not None and self.alive > 2 and not self.disengage
                        and self.f10_duel_target is None):
                    action["fire"] = [False, False]
                if self.mode in ("laser-cover", "laser-dodge") and math.hypot(*self.course) > 0:
                    for index, weapon in enumerate(self.weapon_slots):
                        if weapon.get("kind") == "laser":
                            action["fire"][index] = False
                if not self.single_escape and self.f10_target is None:
                    self.release_laser_safely(obs, action, pos)
                self.f18_prev_target = self.last_fire_target
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
        if dodge is not None:
            self.mode = "charge-cover" if self.charge_warning.cover is not None else "charge-dodge"
            self.course, self.sprinting = dodge["move"], dodge["boost"]
            action.update(dodge)
        return self.pick_upgrade(offer, me, action)

    def pick_upgrade(self, offer, me, action):
        if offer:
            index = min(len(seq(me.get("upgrades"))), len(self.UPGRADES) - 1)
            if ffa_enabled(F10_ECONOMY):
                rank = self.ECONOMY_UPGRADES
            else:
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
    KINDS = (4, 6, 7)
    PROGRAMS = {6: ("./automata", "automata", "a6"), 7: ("./automata2", "automata2", "a7")}
    ACTION_FIELDS = {"type", "tick", "move", "aim", "fire", "boost", "jump", "reload",
                     "pick", "take", "drop", "debug"}

    def __init__(self, salt=None, extra_env=(), *, kind=4, preset=None):
        self.kind = kind
        self.preset = preset
        self.salt = salt
        self.extra_env = extra_env
        self.child = None
        self.reaper = None
        self.connected = False
        self.pending = deque()
        self.partial = b""
        self.discarding = False
        self.fallbacks = 0
        self.consecutive_fallbacks = 0

    def start(self, hello):
        deadline = time.perf_counter() + 8
        if self.kind in self.PROGRAMS:
            command, folder, presets = self.PROGRAMS[self.kind]
            config = P6_ENV if self.kind == 6 else P7_ENV
            params = os.path.join(os.path.dirname(__file__), "third_party", folder, "bot.json")
            if self.preset is not None:
                name = self.preset if isinstance(self.preset, str) else ""
                params = os.path.join(os.path.dirname(__file__), "presets", presets, f"{name}.json")
                if not (name.isascii() and name.isalnum() and os.path.isfile(params)):
                    mf.log(f"Child preset {name!r} unavailable")
                    self.stop()
                    return
            required_env = {"MECH_PARAMS": os.path.abspath(params)}
        else:
            command = "./mechbot"
            config = P4_ENV
            salt = P4_SALT if self.salt is None else self.salt
            required_env = {"MECHBOT_SALT": str(salt)}
        env = {**os.environ, **{name: str(value) for name, value in config.items()},
               **dict(self.extra_env), **required_env}
        try:
            self.child = subprocess.Popen(
                [command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0, env=env,
            )
            reaper = threading.Thread(target=self.child.wait)
            reaper.start()
            self.reaper = reaper
            os.set_blocking(self.child.stdin.fileno(), False)
            os.set_blocking(self.child.stdout.fileno(), False)
            self.connected = True
        except (OSError, RuntimeError) as error:
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
            child.kill()
            child.stdin.close()
            child.stdout.close()
            if self.reaper is None:
                child.wait()

    def close(self):
        self.stop()
        if self.reaper is not None:
            self.reaper.join()

    def warm(self):
        
        if not self.connected:
            return
        send_fd, recv_fd = self.child.stdin.fileno(), self.child.stdout.fileno()
        until = time.perf_counter() + 0.00045
        try:
            while time.perf_counter() < until:
                readable, writable, _ = select.select([recv_fd], [send_fd] if self.pending else [], [], 0)
                if not readable and not writable:
                    return
                if readable:
                    self.read_lines(recv_fd, 4096)
                if writable and self.connected:
                    frame = self.pending[0]
                    written = os.write(send_fd, frame)
                    if written == len(frame):
                        self.pending.popleft()
                    else:
                        self.pending[0] = frame[written:]
        except BlockingIOError:
            return
        except OSError:
            self.stop()

    def decide(self, bot, obs, raw, tick, received, frame_limit, pause_show, queued=None):
        def track(frame):
            try:
                now = bot.track_tick(obs)
            except Exception:
                return None
            if bot.mode == "free-for-all":
                if self.pending and ffa_enabled(F10_OPENER):
                    self.warm()
                self.stop()
            elif self.connected:
                self.pending.append(memoryview(frame))
                if bot.mode == "undecided":
                    self.warm()
            return now

        def refresh():
            nonlocal obs, tick, received, now
            if queued is not None:
                for next_obs, frame, next_tick, timestamp in queued.drain():
                    if self.connected and now is not None and bot.mode == "practice":
                        bot.practice.remember(obs, now)
                    obs, tick, received = next_obs, next_tick, timestamp
                    zone_pending = USE_Z and FORCE_MODE is None and bot.zone_pending
                    now = track(frame)
                    if zone_pending and not bot.zone_pending and bot.mode == "free-for-all":
                        break
            return tick, received + P4_DEADLINE_MS / 1000, queued.fd if queued is not None else None

        now = track(raw)
        tick, child_deadline, _ = refresh()
        if now is not None and self.child is not None and bot.mode == "practice":
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
        if bot.mode == "practice":
            deadline = time.perf_counter() + mf.DECISION_LIMIT_S
        remaining = deadline - mf.WRITE_RESERVE_S - time.perf_counter()
        payload = (mf._watched(remaining, mf._decision, bot, obs, tick, pause_show, now)
                   if remaining > 0 else None)
        if bot.mode == "undecided":
            self.warm()
        return payload, deadline


def p5_key(slot, obs):
    own = vec(obj(obs.get("self")).get("pos"), 3)
    points = []
    for field in ("mechs", "projectiles", "crates", "cubes", "pickups", "drops"):
        for entry in seq(obs.get(field)):
            point = vec(obj(entry).get("pos"), 3)
            if point is not None:
                points.append(tuple(round(axis) for axis in point))
    start = tuple(round(2 * axis) for axis in own) if own is not None else None
    return json.dumps((int(slot), start, sorted(points)), separators=(",", ":")).encode("ascii")


def p5_relay_key(route):
    extra_env = route[2] if len(route) == 3 else {}
    preset = extra_env if isinstance(extra_env, str) else None
    if preset is not None:
        extra_env = {}
    kind = route[0]
    salt = route[1] if kind == 4 else None
    return kind, salt, tuple(sorted((name, str(value)) for name, value in extra_env.items())), preset


class PracticeRouter:
    def __init__(self):
        keys = dict.fromkeys(p5_relay_key(route) for route in P5_TABLE.values()
                             if route[0] in PracticeRelay.KINDS)
        self.relays = {(kind, salt, extra_env, preset): PracticeRelay(salt, extra_env, kind=kind, preset=preset)
                       for kind, salt, extra_env, preset in keys}

    def start(self, hello):
        if len(self.relays) == 1:
            next(iter(self.relays.values())).start(hello)
        elif self.relays:
            with ThreadPoolExecutor(max_workers=len(self.relays)) as pool:
                for _ in pool.map(lambda relay: relay.start(hello), self.relays.values()):
                    pass

    def select(self, bot, obs):
        route = bot.select_p5(obs, self.relays)
        kind = route[0] if route is not None else None
        selected = self.relays.get(p5_relay_key(route)) if kind in PracticeRelay.KINDS else None
        self.ordered_decisions = kind == 2 or (kind == 3 and not bot.practice3.timed)
        for relay in self.relays.values():
            if relay is not selected:
                relay.stop()
        return kind == 2, selected

    def stop(self):
        for relay in self.relays.values():
            relay.stop()

    def close(self):
        self.stop()
        for relay in self.relays.values():
            relay.close()


class Royale:
    def __init__(self, hello):
        duel_bot.SEED_SALT = 6
        self.practice = duel_bot.DuelBot(hello)
        self.practice.guarded = GUARDED_OPENER
        self.ffa = Selective(hello)
        self.detector = Detector(hello)
        self.mode = FORCE_MODE or ("undecided" if ffa_enabled(F10_OPENER) else "practice")
        self.practice_evidence = PracticeEvidence(hello) if self.mode == "undecided" else None
        self.first_ffa = None
        self.practice2 = None
        self.practice3 = None
        self.practice_fallbacks = 0
        self.p5_options = None
        self.p5_loaded = None
        self.p5_relay_backup = None
        self.zone_pending = USE_Z and FORCE_MODE is None
        self.zone_pinned = False
        self.zone_fallback_logged = False
        if self.zone_pending:
            zone = obj(obj(hello.get("config")).get("zone"))
            phases = seq(zone.get("phases"))
            if phases:
                self.choose_zone_mode(obj(phases[0]).get("hold_s"), "hello", 0)
        if self.mode != "free-for-all":
            if P_DRIVER == 5:
                self.p5_loaded = set()
                routes = dict.fromkeys(route for route in P5_TABLE.values() if route[0] in (2, 3))
                self.p5_options = {route: self.new_driver(route[0], hello, *route[1:])
                                   for route in routes}
                if any(route[0] in PracticeRelay.KINDS for route in P5_TABLE.values()):
                    self.p5_relay_backup = self.new_driver(3, hello, SEED, timed=True)
            elif P_DRIVER == 2:
                self.practice2 = self.new_driver(2, hello, SEED)
            elif P_DRIVER == 3 or P_DRIVER in PracticeRelay.KINDS:
                self.practice3 = self.new_driver(3, hello, SEED, timed=P_DRIVER in PracticeRelay.KINDS)

    @staticmethod
    def new_driver(kind, hello, seed, preset=None, *, timed=False):
        try:
            if kind == 2:
                from practice2 import Practice
            else:
                from practice3 import Practice
        except ImportError:
            if P_DRIVER != 5:
                mf.log(f"driver {kind} unavailable")
            return None
        return Practice(hello, seed) if kind == 2 else Practice(hello, seed, preset, timed=timed)

    def select_p5(self, obs, relays=None):
        key = p5_key(self.detector.slot, obs)
        route = P5_TABLE.get(zlib.crc32(key) % P5_GROUPS, (1, SEED))
        options, self.p5_options = self.p5_options, None
        relay_backup, self.p5_relay_backup = self.p5_relay_backup, None

        def loaded(candidate):
            kind = candidate[0]
            if kind in PracticeRelay.KINDS:
                relay = relays.get(p5_relay_key(candidate)) if relays is not None else None
                return relay is not None and relay.connected
            return kind in self.p5_loaded and (kind == 1 or options.get(candidate) is not None)

        if not loaded(route):
            if route[0] in PracticeRelay.KINDS and relay_backup is not None and relay_backup.world is not None:
                fallback = (3, SEED)
                self.practice3 = relay_backup
            else:
                candidates = (*P5_TABLE.values(), (1, SEED))
                fallback = next((candidate for candidate in candidates if loaded(candidate)), None)
            destination = f"driver {fallback[0]} ({fallback[1]})" if fallback else "map-free steering"
            mf.log(f"Practice driver {route[0]} ({route[1]}) unavailable, using {destination}.")
            route = fallback
        if route is None:
            return None
        if route[0] == 2:
            self.practice2 = options.get(route)
        elif route[0] in PracticeRelay.KINDS:
            self.practice3 = relay_backup
        elif route[0] == 3 and self.practice3 is None:
            self.practice3 = options.get(route)
        return route

    def __getattr__(self, name):
        if name in ("practice", "practice2", "practice3", "ffa", "detector", "mode", "first_ffa"):
            raise AttributeError(name)
        if self.mode != "practice":
            return getattr(self.ffa, name)
        return getattr(self.practice2 or self.practice3 or self.practice, name)

    def load_map(self):
        if self.p5_options is not None:
            
            kinds = dict.fromkeys(route[0] for route in P5_TABLE.values())
            has_relay = any(kind in kinds for kind in PracticeRelay.KINDS)
            for kind in PracticeRelay.KINDS:
                kinds.pop(kind, None)
            kinds[1] = None
            if has_relay:
                kinds[3] = None
            for kind in kinds:
                try:
                    if kind == 1:
                        self.practice.load_map()
                        self.ffa.arena = self.practice.arena
                    elif not self.load_p5_maps(kind):
                        continue
                except Exception:
                    continue
                self.p5_loaded.add(kind)
            return True

        if self.practice2 is not None:
            self.practice2.load_map()
        self.practice.load_map()
        self.ffa.arena = self.practice.arena
        if self.practice3 is not None:
            try:
                self.load_practice3_map(self.practice3)
            except Exception as error:
                mf.log(f"practice3 map: {type(error).__name__}")
        return True

    def load_p5_maps(self, kind):
        drivers = [driver for route, driver in self.p5_options.items()
                   if route[0] == kind and driver is not None]
        if kind == 3 and self.p5_relay_backup is not None:
            drivers.append(self.p5_relay_backup)
        if not drivers:
            return False
        first, *others = drivers
        if kind == 2:
            first.load_map()
            for driver in others:
                driver.arena = first.arena
            return first.arena is not None
        self.load_practice3_map(first)
        for driver in others:
            driver.world = first.world
        return first.world is not None

    def load_practice3_map(self, driver):
        from pathlib import Path

        directory = self.practice.map_dir
        if isinstance(directory, str) and directory and len(directory) < 2048:
            root = Path(directory) / "v2"
            data = json.loads(eb.read_map_file(root / "world.json"))
            driver.load_map(data, eb.read_map_file(root / "terrain.i16"))
        else:
            driver.load_map()

    def choose_zone_mode(self, value, source, now):
        start = number(value, None)
        if start is None or start < 0:
            return False
        self.zone_pending = False
        free_for_all = start >= Z_SPLIT_S
        self.mode = "free-for-all" if free_for_all else "practice"
        self.zone_pinned = free_for_all or Z_ONLY
        if free_for_all:
            self.detector.ffa = True
            self.first_ffa = round(now, 1)
            self.p5_options = None
            self.p5_relay_backup = None
        mf.log(f"Z {source} shrink_start={start}s mode={self.mode}")
        return True

    def read_zone_schedule(self, obs):
        if not self.zone_pending:
            return False
        start = obj(obs.get("zone")).get("shrink_start")
        return self.choose_zone_mode(start, "obs", number(obs.get("t"), 0))

    def track_tick(self, obs):
        now = number(obs.get("t"), 0)
        if self.zone_pending:
            self.read_zone_schedule(obs)
        if FORCE_MODE is None and not self.zone_pinned:
            try:
                if T_FFA is not None and self.mode == "practice" and now >= T_FFA:
                    self.detector.ffa = True
                if self.detector.update(obs, now):
                    want = "free-for-all"
                elif self.mode == "undecided":
                    want = self.mode
                    if self.practice_evidence.update(obs, now, self.detector.score, self.ffa.arena):
                        want = "practice"
                    elif now >= F10_T0_S:
                        want = "free-for-all" if F10_T0_MODE == "free-for-all" else "practice"
                        self.detector.ffa = want == "free-for-all"
                else:
                    want = "practice"
            except (ArithmeticError, LookupError, TypeError, ValueError, AttributeError):
                want = self.mode
            if want != self.mode:
                self.mode = want
                if want == "free-for-all" and self.first_ffa is None:
                    self.first_ffa = round(now, 1)
                mf.log(f"mode {want}")
        if self.zone_pending and not self.zone_fallback_logged:
            self.zone_fallback_logged = True
            mf.log(f"Z obs shrink_start=unavailable mode={self.mode} (legacy rules)")
        if self.mode == "practice":
            self.ffa.record(obs, vec(obj(obs.get("self")).get("pos"), 3), now)
        elif self.mode == "undecided":
            self.practice.remember(obs, now)
        return now

    def act(self, obs, now=None):
        obs = obj(obs)
        if self.p5_options is not None:
            if not self.read_zone_schedule(obs) or self.mode == "practice":
                self.select_p5(obs)
        if now is None:
            now = self.track_tick(obs)
        if self.mode != "practice":
            self.ffa.opener_undecided = self.mode == "undecided"
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
                if driver is self.practice2 or not driver.timed:
                    return mf._fallback(obs, obs.get("tick"))
                if self.p5_loaded is not None and 1 not in self.p5_loaded:
                    return None
                try:
                    return self.practice.act(obs)
                except Exception:
                    return {"aim": driver.last_aim}
        if self.p5_loaded is not None and 1 not in self.p5_loaded:
            return None
        return self.practice.act(obs)


def main():
    zone_schedule = USE_Z and FORCE_MODE is None
    if P_DRIVER in PracticeRelay.KINDS and FORCE_MODE != "free-for-all":
        relay = PracticeRelay(kind=P_DRIVER, preset={6: P6_PRESET, 7: P7_PRESET}.get(P_DRIVER))
        try:
            mf.run(Royale, pause_show=PAUSE_SHOW, raw_wire=relay, zone_schedule=zone_schedule)
        finally:
            relay.close()
    elif P_DRIVER == 5 and FORCE_MODE != "free-for-all":
        router = PracticeRouter()
        complete_table = len(P5_TABLE) == P5_GROUPS
        practice_wire = complete_table and all(route[0] == 2 for route in P5_TABLE.values())
        ordered_decisions = complete_table and all(route[0] in (2, 3) for route in P5_TABLE.values())
        try:
            mf.run(Royale, pause_show=PAUSE_SHOW, practice_wire=practice_wire,
                   practice_router=router, zone_schedule=zone_schedule,
                   ordered_decisions=ordered_decisions)
        finally:
            router.close()
    else:
        mf.run(Royale, pause_show=PAUSE_SHOW, practice_wire=P_DRIVER == 2 and FORCE_MODE != "free-for-all",
               zone_schedule=zone_schedule,
               ordered_decisions=P_DRIVER in (2, 3) and FORCE_MODE != "free-for-all")


if __name__ == "__main__":
    main()
