"""Survival policy for the mechfight/1 starter entry point."""
from array import array
from dataclasses import dataclass
import heapq
import json
import math
import os
import stat
import time

import mechfight as mf


# Policy settings. Live physics and weapon values are read from hello and observations.
PLAN_BUDGET_S = 0.006
ROUTE_SLICE_S = 0.0015
ROUTE_NODES_PER_TICK = 280
ROUTE_TOTAL_NODES = 4500
ROUTE_WEIGHT = 1.19
ROUTE_REPLAN_M = 8.0
ROUTE_DIRECT_M = 28.0
ROUTE_CLEARANCE_M = 1.0
ROUTE_LOOKAHEAD_CELLS = 5
GRID_M = 3.0
RAY_STEP_M = 2.7
MAP_MAX_BYTES = 4 * 1024 * 1024
ZONE_LOOKAHEAD_S = 13.0
ZONE_MARGIN_M = 17.0
ZONE_TRAVEL_FACTOR = 1.65
ZONE_INTERIOR = 0.72
ZONE_MARGIN_FRACTION = 0.40
DEATH_CIRCLE_M = 7.0
COVER_NEAR_M = 16.0
COVER_RADII_M = (15, 30, 53)
COVER_REFRESH_S = 0.65
COVER_PREDICTION_S = 8.0
COVER_BREAK_M = 12.0
COVER_AWAY_M = 20.0
THREAT_RANGE_M = 155.0
EVADE_RANGE_M = 88.0
LOOT_THREAT_M = 117.0
LOOT_CONTEST_M = 42.0
LOOT_SAFE_S = 9.0
HEAL_FRACTION = 0.66
WEAK_FRACTION = 0.32
HIT_MEMORY_S = 3.2
SOUND_MEMORY_S = 1.3
CUBE_DETOUR_M = 38.0
CUBE_STAT_VALUE_M = 39.0
CUBE_UPGRADE_VALUE_M = 12.0
CUBE_UPGRADE_DISCOUNT = 0.22
WEAPON_DETOUR_M = 29.0
DROP_DETOUR_M = 48.0
CRATE_RANGE_M = 52.0
MORTAR_RANGE_M = 96.0
MORTAR_MIN_M = 17.0
STUCK_WINDOW_S = 0.8
STUCK_RETRY_S = 1.3
BOOST_RESERVE = 18.0
JET_RESERVE = 9.0
ROOF_APPROACH_M = 36.0
STEER_HORIZON_S = 0.58
CORE_HORIZON_S = 0.40
CORE_SLOW_M = 3.0
HOLD_M = 1.6
CORE_HOLD_M = 0.12
BOOST_THREAT_M = 56.0
SQUAD_EXPOSURE_PENALTY = 14.0
ARMING_YAW_ALLOW_RAD = 0.12
ARMING_PITCH_ALLOW_RAD = 0.10
RELOAD_FRACTION = 0.60
SCAN_RATE = 0.79
STEER_ANGLES = (0, 0.35, -0.35, 0.72, -0.72, 1.17, -1.17, 1.57, -1.57, 2.3, -2.3, math.pi)
COVER_ANGLES = tuple((math.cos(i * math.tau / 12), math.sin(i * math.tau / 12)) for i in range(12))
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))
WEAPON_RANK = {"gun": 0, "mortar": 1, "lightning": 2, "laser": 3}
UPGRADE_RANK = {
    "plating": 100, "nanites": 95, "armor": 87, "servos": 78, "reactor": 70,
    "jets": 67, "capacitor": 61, "sensors": 59, "gyros": 54, "laser_charge": 49,
    "gun_mag": 47, "gun_damage": 45, "gun_velocity": 43, "gun_rate": 41,
    "laser_damage": 39, "lightning_range": 38, "lightning_efficiency": 37,
}
DANGER_SOUNDS = ("gun", "mortar", "explosion", "laser", "laser_charge", "lightning", "jet", "boost", "step", "npc_gun")
ZERO = (0.0, 0.0, 0.0)


def obj(value):
    return value if isinstance(value, dict) else {}


def seq(value):
    return value if isinstance(value, (list, tuple)) else ()


def number(value, default=0.0):
    if type(value) in (int, float) and -1e9 <= value <= 1e9:
        return value
    return default


def vec(value, n):
    if isinstance(value, (list, tuple)) and len(value) >= n:
        values = tuple(number(value[i], None) for i in range(n))
        if None not in values:
            return values
    return None


def limit(value, lo, hi):
    return max(lo, min(hi, value))


def angle(value):
    return (value + math.pi) % math.tau - math.pi


def bearing(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def raised(pos, height):
    return pos[0], pos[1], pos[2] + height


def read_map_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAP_MAX_BYTES:
            raise ValueError("Invalid map file")
        return stream.read(MAP_MAX_BYTES + 1)


class Arena:
    """A raster of terrain and vertical solid intervals, plus ground clearance for routing."""

    def __init__(self, directory, height, step_up, slope):
        world = json.loads(read_map_file(os.path.join(directory, "v2/world.json")))
        raw = read_map_file(os.path.join(directory, "v2/terrain.i16"))
        terrain = world["terrain"]
        nx, ny = terrain["nx"], terrain["ny"]
        if nx < 2 or ny < 2 or len(raw) != nx * ny * 2:
            raise ValueError("Invalid terrain grid")
        heights = array("h", raw)
        if os.sys.byteorder != "little":
            heights.byteswap()
        bounds = world["bounds"]
        self.x0, self.y0 = bounds["minX"], bounds["minY"]
        self.right, self.top = bounds["maxX"], bounds["maxY"]
        self.w = w = math.ceil((self.right - self.x0) / GRID_M)
        self.h = h = math.ceil((self.top - self.y0) / GRID_M)
        if not (2 <= w <= 900 and 2 <= h <= 900 and terrain["step"] > 0):
            raise ValueError("Invalid arena bounds")
        self.height, self.step_up, self.slope = height, step_up, slope
        self.slabs = {}
        for prism in world["prisms"]:
            self.rasterize(prism)

        def indices(start, count, origin, size):
            for i in range(count):
                grid = limit((start + (i + 0.5) * GRID_M - origin) / terrain["step"], 0, size - 1)
                index = min(int(grid), size - 2)
                yield index, grid - index

        xs = tuple(indices(self.x0, w, terrain["minX"], nx))
        self.ground = ground = array("f")
        for j, fy in indices(self.y0, h, terrain["minY"], ny):
            lo, hi = j * nx, (j + 1) * nx
            ground.extend(0.01 * ((1 - fy) * (heights[lo + i] * (1 - fx) + heights[lo + i + 1] * fx)
                                  + fy * (heights[hi + i] * (1 - fx) + heights[hi + i + 1] * fx))
                          for i, fx in xs)

        self.floor = floor = ground[:]
        self.roof = roof = ground[:]
        self.clearance = clearance = array("f", [1e6]) * (w * h)
        for idx, spans in self.slabs.items():
            spans.sort()
            level = floor[idx]
            roof[idx] = max(level, max(top for _, top in spans))
            for base, top in spans:
                if top <= level:
                    continue
                if top <= level + step_up:
                    level = top
                elif base < level + height:
                    clearance[idx] = 0
                    break
            floor[idx] = level

        # Distance transform in grid units. Edges are kept out of pathfinding separately.
        diag = math.sqrt(2)
        for y in range(1, h - 1):
            for i in range(y * w + 1, (y + 1) * w - 1):
                if abs(floor[i] - floor[i - 1]) > slope * GRID_M or abs(floor[i] - floor[i - w]) > slope * GRID_M:
                    clearance[i] = 0
        for y in range(h):
            for x in range(w):
                i = y * w + x
                value = clearance[i]
                if x:
                    value = min(value, clearance[i - 1] + 1)
                if y:
                    value = min(value, clearance[i - w] + 1,
                                clearance[i - w - 1] + diag if x else value,
                                clearance[i - w + 1] + diag if x + 1 < w else value)
                clearance[i] = value
        for y in range(h - 1, -1, -1):
            for x in range(w - 1, -1, -1):
                i = y * w + x
                value = clearance[i]
                if x + 1 < w:
                    value = min(value, clearance[i + 1] + 1)
                if y + 1 < h:
                    value = min(value, clearance[i + w] + 1,
                                clearance[i + w - 1] + diag if x else value,
                                clearance[i + w + 1] + diag if x + 1 < w else value)
                clearance[i] = value

    def rasterize(self, prism):
        rings = []
        for ring in (prism["ring"], *prism.get("holes", ())):
            points = list(zip(ring[::2], ring[1::2]))
            if len(points) >= 3:
                rings.append(points)
        if not rings:
            return
        span = prism["base"], prism["top"]
        edges = [(a, b) for ring in rings for a, b in zip(ring, ring[1:] + ring[:1])]
        first = max(0, math.floor((min(y for _, y in rings[0]) - self.y0) / GRID_M))
        last = min(self.h, math.ceil((max(y for _, y in rings[0]) - self.y0) / GRID_M))
        for j in range(first, last):
            y = self.y0 + (j + 0.5) * GRID_M
            crossings = sorted(ax + (y - ay) * (bx - ax) / (by - ay)
                               for (ax, ay), (bx, by) in edges if (ay > y) != (by > y))
            for a, b in zip(crossings[::2], crossings[1::2]):
                left = max(0, math.ceil((a - self.x0) / GRID_M - 0.5))
                right = min(self.w, math.ceil((b - self.x0) / GRID_M - 0.5))
                for i in range(j * self.w + left, j * self.w + right):
                    self.slabs.setdefault(i, []).append(span)

    def cell(self, x, y):
        i = math.floor((x - self.x0) / GRID_M)
        j = math.floor((y - self.y0) / GRID_M)
        return j * self.w + i if 0 <= i < self.w and 0 <= j < self.h else None

    def point(self, idx):
        j, i = divmod(idx, self.w)
        return self.x0 + (i + 0.5) * GRID_M, self.y0 + (j + 0.5) * GRID_M

    def inset(self, pos, radius):
        return (limit(pos[0], self.x0 + radius, self.right - radius),
                limit(pos[1], self.y0 + radius, self.top - radius))

    def near_cover(self, pos):
        idx = self.cell(*pos[:2])
        return self.clearance[idx] * GRID_M if idx is not None else 1e6

    def ground_ok(self, idx, radius):
        return idx is not None and self.clearance[idx] * GRID_M >= radius + ROUTE_CLEARANCE_M

    def nearest_open(self, pos, radius, acceptable=None, rings=6):
        x, y = self.inset(pos, radius + 0.6)
        idx = self.cell(x, y)
        if idx is None:
            return None
        j, i = divmod(idx, self.w)
        best, best_distance = None, math.inf
        for dy in range(-rings, rings + 1):
            for dx in range(-rings, rings + 1):
                if not (0 <= i + dx < self.w and 0 <= j + dy < self.h):
                    continue
                cell = idx + dy * self.w + dx
                if not self.ground_ok(cell, radius):
                    continue
                p = self.point(cell)
                d = distance(p, pos)
                if d < best_distance and self.inset(p, radius) == p and (acceptable is None or acceptable(p)):
                    best, best_distance = cell, d
        return best

    def solid(self, point):
        x, y, z = point
        idx = self.cell(x, y)
        if idx is None or z < self.ground[idx] - 0.25:
            return True
        return any(base + 0.1 < z < top - 0.1 for base, top in self.slabs.get(idx, ()))

    def clear_ray(self, start, end):
        dx, dy, dz = (b - a for a, b in zip(start, end))
        steps = max(1, min(112, math.ceil(math.hypot(dx, dy, dz) / RAY_STEP_M)))
        x, y, z = start
        return all(not self.solid((x + dx * i / steps, y + dy * i / steps, z + dz * i / steps))
                   for i in range(1, steps))

    def obstacle(self, pos, radius, height, forgive_clearance=0.0):
        x, y, z = pos
        if self.inset(pos, radius) != (x, y):
            return True
        idx = self.cell(x, y)
        if idx is None or self.ground[idx] > z + self.step_up + 0.5:
            return True
        if abs(z - self.floor[idx]) < self.step_up + 1.0 and not self.ground_ok(idx, radius - forgive_clearance):
            return True
        for dx, dy in ((0, 0), (radius, 0), (-radius, 0), (0, radius), (0, -radius)):
            side = self.cell(x + dx, y + dy)
            if any(top > z + self.step_up + 0.25 and base < z + height - 0.15
                   for base, top in self.slabs.get(side, ())):
                return True
        return False

    def corridor(self, pos, goal, radius, height):
        length = distance(pos, goal)
        steps = max(1, min(10, math.ceil(length / GRID_M)))
        x, y, z = pos
        dx, dy = (goal[0] - x) / steps, (goal[1] - y) / steps
        for i in range(1, steps + 1):
            px, py = x + i * dx, y + i * dy
            idx = self.cell(px, py)
            if self.obstacle((px, py, z), radius, height, 0.55):
                return False
            if idx is not None and abs(self.floor[idx] - z) <= self.step_up + 0.5:
                z = self.floor[idx]
        return True


class RouteSearch:
    def __init__(self, arena, start, end, radius):
        self.arena, self.start, self.end, self.radius = arena, start, end, radius
        self.destination = arena.point(end)
        self.queue = [(0, 0, start)]
        self.parent = {start: None}
        self.cost = {start: 0}
        self.total = 0
        self.done = False

    def advance(self, until):
        arena, w, h = self.arena, self.arena.w, self.arena.h
        for _ in range(ROUTE_NODES_PER_TICK):
            if self.total >= ROUTE_TOTAL_NODES or not self.queue:
                self.done = True
                return ()
            if time.perf_counter() >= until:
                break
            self.total += 1
            _, negative, current = heapq.heappop(self.queue)
            g = -negative
            if g > self.cost[current]:
                continue
            if current == self.end:
                path = []
                while current != self.start:
                    path.append(arena.point(current))
                    current = self.parent[current]
                self.done = True
                return tuple(reversed(path))
            y, x = divmod(current, w)
            for dx, dy in NEIGHBORS:
                if not (1 <= x + dx < w - 1 and 1 <= y + dy < h - 1):
                    continue
                n = current + dy * w + dx
                if not arena.ground_ok(n, self.radius):
                    continue
                if dx and dy and (not arena.ground_ok(current + dx, self.radius)
                                  or not arena.ground_ok(current + dy * w, self.radius)):
                    continue
                step_cost = (1.414 if dx and dy else 1.0) + 0.22 / arena.clearance[n]
                cost = g + step_cost
                if cost < self.cost.get(n, math.inf):
                    self.cost[n] = cost
                    self.parent[n] = current
                    heuristic = ROUTE_WEIGHT * distance(arena.point(n), self.destination) / GRID_M
                    heapq.heappush(self.queue, (cost + heuristic, -cost, n))
        return ()


@dataclass(slots=True)
class Zone:
    center: tuple
    radius: float
    next_center: tuple
    next_radius: float
    start: float
    end: float
    now: float
    dps: float = 0.0

    def circle_in(self, seconds):
        remaining = self.end - max(self.now, self.start)
        if remaining <= 0:
            return self.center, self.radius
        fraction = limit((self.now + seconds - max(self.now, self.start)) / remaining, 0, 1)
        center = tuple(a + fraction * (b - a) for a, b in zip(self.center, self.next_center))
        return center, self.radius + fraction * (self.next_radius - self.radius)

    def gap(self, point, seconds=0.0):
        center, radius = self.circle_in(seconds)
        return radius - distance(point, center)

    def margin(self, radius):
        return min(ZONE_MARGIN_M, radius * ZONE_MARGIN_FRACTION)

    def anchor(self, pos, speed):
        center = self.next_center
        radial = distance(pos, center)
        inside = self.next_radius * ZONE_INTERIOR if self.next_radius > DEATH_CIRCLE_M else 0.0
        travel = max(0, radial - inside)
        early = travel / speed * ZONE_TRAVEL_FACTOR + ZONE_LOOKAHEAD_S
        future_center, future_radius = self.circle_in(ZONE_LOOKAHEAD_S)
        urgent = (self.gap(pos) < self.margin(self.radius)
                  or future_radius - distance(pos, future_center) < self.margin(future_radius)
                  or (travel > 3 and self.end - self.now < early))
        if self.radius <= DEATH_CIRCLE_M:
            return self.center, True
        if urgent and radial > inside and radial > 0:
            return tuple(c + (p - c) * inside / radial for p, c in zip(pos, center)), True
        if urgent:
            return center, True
        return pos[:2], False


@dataclass(slots=True)
class Contact:
    id: float
    kind: str
    pos: tuple
    vel: tuple
    aim: tuple | None
    hp: float
    max_hp: float
    scale: float
    dist: float
    face_error: float
    clear: bool
    attacker: bool
    charging: bool
    armed: tuple


class Bot:
    def __init__(self, hello):
        config = obj(hello.get("config"))
        self.mech = obj(config.get("mech"))
        self.weapon_config = obj(config.get("weapons"))
        self.cubes = obj(config.get("cubes"))
        self.upgrade_thresholds = tuple(
            value for raw in seq(self.cubes.get("upgrade_thresholds", (1, 3, 6, 10, 15, 21, 28, 36, 45)))
            if (value := number(raw, 0)) > 0
        )
        self.npc = obj(config.get("npc"))
        self.crates = obj(config.get("crates"))
        self.loot = obj(config.get("loot"))
        match = obj(config.get("match"))
        self.physics_dt = 1 / limit(number(match.get("tick_hz"), 20), 1, 1000)
        self.dt = self.physics_dt * limit(number(match.get("decide_every"), 2), 1, 20)
        self.match_end = max(0, number(match.get("duration_s"), 480))
        self.slot = number(hello.get("slot"), 0)
        self.arena = None
        self.map_dir = obj(hello.get("map")).get("dir")
        self.hits = {}
        self.drop_progress = {}
        self.last_damage = self.last_sound = -math.inf
        self.last_repair_reset = -math.inf
        self.damage_bearing = self.sound_bearing = None
        self.shelter = self.shelter_origin = None
        self.shelter_time = -math.inf
        self.search = self.route_goal = None
        self.path, self.path_index = (), 0
        self.motion_origin = None
        self.motion_time = self.stuck_until = -math.inf
        self.scout_yaw = self.slot * 1.7
        self.last_fire_target = None

    def load_map(self):
        directory = self.map_dir
        if isinstance(directory, str) and directory and len(directory) < 2048:
            slope = math.tan(math.radians(limit(self.phys("max_slope_deg", 50), 1, 80)))
            self.arena = Arena(directory, self.phys("height", 9), self.phys("step_up", 1.2), slope)
        return True

    def remember(self, obs, now):
        self.hits = {source: t for source, t in self.hits.items() if now - t < HIT_MEMORY_S}
        for event in seq(obs.get("events"))[:40]:
            event = obj(event)
            kind = event.get("type")
            if kind in ("hit", "damaged"):
                self.last_repair_reset = now
            if kind != "damaged" or event.get("weapon") == "zone":
                continue
            self.last_damage = now
            direction = number(event.get("bearing"), None)
            if direction is not None:
                self.damage_bearing = angle(direction)
            source = number(event.get("by"), None)
            if source is not None and len(self.hits) < 48:
                self.hits[source] = now
        for sound in seq(obs.get("sounds"))[:40]:
            sound = obj(sound)
            if sound.get("dist") == "near" and sound.get("kind") in DANGER_SOUNDS:
                direction = number(sound.get("bearing"), None)
                heard = now - max(0, number(sound.get("age")))
                if direction is not None and heard > self.last_sound:
                    self.last_sound, self.sound_bearing = heard, angle(direction)

    def contacts(self, obs, pos, eye):
        candidates = []
        for entry in seq(obs.get("mechs"))[:48]:
            entry = obj(entry)
            target, ident = vec(entry.get("pos"), 3), number(entry.get("id"), None)
            kind = entry.get("kind")
            if target is None or ident is None or kind not in ("mech", "npc") or ident == self.slot:
                continue
            d = distance(pos, target)
            attacker = ident in self.hits
            if d <= 210 or attacker and d <= 285:
                candidates.append((d + (24 if kind == "npc" else 0) - (100 if attacker else 0), d, entry, target, ident, attacker))
        candidates.sort(key=lambda item: item[0])
        contacts = []
        for _, d, entry, target, ident, attacker in candidates[:8]:
            kind = entry["kind"]
            aim = vec(entry.get("aim"), 2)
            facing = abs(angle(bearing(target, pos) - aim[0])) if aim else 0.0
            scale = 1 + limit(number(entry.get("cubes")), 0, 100) * number(self.cubes.get("size_per_cube"), 0.05)
            hp = number(entry.get("hp"), math.inf)
            max_hp = max(1, number(entry.get("max_hp"), 1400))
            offset = (self.phys("height", 9) * scale if kind == "mech" else number(self.npc.get("height"), 3.5)) * 0.58
            clear = self.arena is None or self.arena.clear_ray(raised(pos, eye), raised(target, offset))
            contacts.append(Contact(ident, kind, target, vec(entry.get("vel"), 3) or ZERO, aim, hp, max_hp,
                                    scale, math.hypot(d, target[2] - pos[2]), facing, clear, attacker,
                                    entry.get("charging") is True, tuple(seq(entry.get("weapons"))[:2])))
        return contacts

    def phys(self, key, default, stats=None):
        return number(stats.get(key) if stats else None, number(self.mech.get(key), default))

    def supply_hint(self, obs, pos, contacts, now):
        previous, self.drop_progress = self.drop_progress, {}
        known = {c.id for c in contacts}
        own_id = number(obj(obs.get("self")).get("id"), self.slot)
        closest, hint = LOOT_THREAT_M, None
        for item in seq(obs.get("drops"))[:8]:
            item = obj(item)
            ident = number(item.get("id"), None)
            holder = number(item.get("holder"), None)
            progress = number(item.get("progress"), None)
            if ident is None or holder is None or holder == own_id or progress is None or progress < 0:
                continue
            if number(item.get("lands_in"), math.inf) > 0:
                continue
            self.drop_progress[ident] = holder, progress, now
            prior = previous.get(ident)
            if (holder in known or prior is None or holder != prior[0] or progress <= prior[1]
                    or not 0 < now - prior[2] <= max(0.35, self.dt * 2)):
                continue
            p = vec(item.get("pos"), 3)
            if p is not None and (d := distance(pos, p)) < closest:
                closest, hint = d, p
        return hint

    def nearby_shells(self, obs, pos, velocity, height):
        hazards = []
        gravity = number(obj(self.weapon_config.get("mortar")).get("gravity"), 22)
        px, py, pz = raised(pos, height * 0.54)
        for item in seq(obs.get("projectiles"))[:96]:
            item = obj(item)
            point, vel = vec(item.get("pos"), 3), vec(item.get("vel"), 3)
            if point is None or vel is None or distance(pos, point) > 125:
                continue
            x, y, z = point
            vx, vy, vz = vel
            rx, ry = vx - velocity[0], vy - velocity[1]
            speed2 = rx * rx + ry * ry
            mortar = item.get("kind") == "mortar"
            if mortar:
                floor = pz - height * 0.54
                relative_z = z - floor
                disc = vz * vz + 2 * gravity * relative_z
                t = (vz + math.sqrt(disc)) / gravity if disc >= 0 and gravity > 0 else -1
                reach = 15
            else:
                t = ((px - x) * rx + (py - y) * ry) / speed2 if speed2 > 1 else -1
                reach = 8
            if not 0.018 < t < (0.9 if mortar else 0.38):
                continue
            point_at_impact = x + vx * t, y + vy * t
            expected = px + velocity[0] * t, py + velocity[1] * t
            if distance(point_at_impact, expected) <= reach and (mortar or abs(z + vz * t - pz) < height * 0.65):
                hazards.append((point_at_impact, t, reach))
                if len(hazards) == 5:
                    break
        return hazards

    def shelter_point(self, pos, zone, contacts, direction, radius, height, now, until, terminal_burn):
        arena = self.arena
        if arena is None:
            return None
        if (self.shelter_origin and now - self.shelter_time < COVER_REFRESH_S
                and distance(pos, self.shelter_origin) < COVER_BREAK_M
                and (self.shelter is None or terminal_burn or zone.gap(self.shelter, 5) > 1)):
            return self.shelter
        self.shelter_origin, self.shelter_time = pos, now
        danger = [c for c in contacts if c.dist < THREAT_RANGE_M and c.kind == "mech"][:2]
        if not danger:
            danger = [c for c in contacts if c.attacker][:1]
        source = None if direction is None else (pos[0] + math.cos(direction) * 57,
                                                pos[1] + math.sin(direction) * 57, pos[2] + height * 0.64)
        best, best_score = None, -math.inf
        for d in (0, *COVER_RADII_M):
            for dx, dy in COVER_ANGLES if d else ((0, 0),):
                if time.perf_counter() >= until:
                    self.shelter = best
                    return best
                p = pos[0] + d * dx, pos[1] + d * dy
                cell = arena.cell(*p)
                if not arena.ground_ok(cell, radius) or arena.inset(p, radius) != p:
                    continue
                if not terminal_burn and zone.gap(p, COVER_PREDICTION_S) < min(5, zone.radius * 0.2):
                    continue
                near = arena.near_cover(p)
                if near > COVER_NEAR_M * 1.7:
                    continue
                base = pos[2] if d == 0 else arena.floor[cell]
                if d and abs(base - pos[2]) > 6:
                    continue
                endpoint = p[0], p[1], base + height * 0.6
                score = 14 - abs(near - (radius + 5)) - d * 0.22
                for c in danger:
                    origin = raised(c.pos, (7 * c.scale if c.kind == "mech" else 2.4))
                    blocked = not arena.clear_ray(origin, endpoint)
                    score += (20 if blocked else -24) + 0.28 * limit(distance(c.pos, p) - c.dist, -30, 30)
                    if distance(c.pos, p) < 29:
                        score -= 19
                if not danger and source:
                    score += 13 if not arena.clear_ray(source, endpoint) else -5
                if score > best_score:
                    best, best_score = p, score
        self.shelter = best if best_score > -14 else None
        return self.shelter

    def loot_goal(self, obs, pos, zone, contacts, weapons, hp_fraction, cubes, safe, urgent, action):
        arena = self.arena
        options = []
        kinds = tuple(w.get("kind") for w in weapons)
        spare = next((i for i, w in enumerate(weapons) if not w), None)
        swap = next((i for i, w in enumerate(weapons) if w.get("kind") in ("mortar", "lightning")), None)
        detour = safe and not urgent
        rivals = [c.pos for c in contacts if c.kind == "mech"]
        pickup_radius = limit(number(self.loot.get("pickup_radius"), 4), 0.5, 15)
        take = None
        if spare is not None or (detour and swap is not None):
            for entry in seq(obs.get("pickups"))[:40]:
                entry = obj(entry)
                p, ident = vec(entry.get("pos"), 3), number(entry.get("id"), None)
                kind = entry.get("kind")
                rank = WEAPON_RANK.get(kind) if isinstance(kind, str) else None
                if p is None or abs(pos[2] - p[2]) > 4 or ident is None or ident < 0 or rank is None or kind in kinds:
                    continue
                if spare is None and rank <= WEAPON_RANK[kinds[swap]]:
                    continue
                d = distance(pos, p)
                if d > (WEAPON_DETOUR_M if detour else pickup_radius):
                    continue
                if any(distance(rival, p) < LOOT_CONTEST_M for rival in rivals):
                    continue
                if d <= pickup_radius:
                    choice = (rank, -d, ident)
                    if take is None or choice > take:
                        take = choice
                elif zone.gap(p, LOOT_SAFE_S) > min(3, zone.radius * 0.12):
                    options.append((30 + rank * 4 - d, p))
        if take is not None:
            action["take"] = take[2]
            if spare is None:
                action["drop"] = swap
            options.clear()
        if not detour:
            return None

        cube_cap = number(self.cubes.get("stat_cap"), 10)
        upgrade_gap = min((threshold - cubes for threshold in self.upgrade_thresholds if threshold > cubes),
                          default=math.inf)
        stat_gain = limit(cube_cap - cubes, 0, 1)
        # Discount progress toward distant offers, including after the stat cap.
        upgrade_value = CUBE_UPGRADE_VALUE_M / (1 + CUBE_UPGRADE_DISCOUNT * max(0, upgrade_gap - 1))
        cube_value = CUBE_STAT_VALUE_M * stat_gain + upgrade_value
        cube_reach = limit(number(self.cubes.get("pickup_radius"), 3.5), 0.5, 15)
        own_id = number(obj(obs.get("self")).get("id"), self.slot)
        for key, bound, maximum in (("cubes", 56, CUBE_DETOUR_M), ("drops", 8, DROP_DETOUR_M)):
            for entry in seq(obs.get(key))[:bound]:
                entry = obj(entry)
                p = vec(entry.get("pos"), 3)
                if p is None or abs(pos[2] - p[2]) > 4 or zone.gap(p, LOOT_SAFE_S) <= min(3, zone.radius * 0.12):
                    continue
                d = distance(pos, p)
                if d > maximum or any(distance(rival, p) < LOOT_CONTEST_M for rival in rivals):
                    continue
                if key == "cubes":
                    score = cube_value - d
                    if score <= 0 or d < cube_reach * 0.7:
                        continue
                else:
                    holder = entry.get("holder")
                    if number(entry.get("lands_in"), math.inf) > 0 or (holder is not None and holder != own_id):
                        continue
                    capture = limit(number(entry.get("capture_s"), 4), 0, 10)
                    if zone.gap(p, capture + d / 8 + 4) < 4:
                        continue
                    score = 52 + (1 - hp_fraction) * 37 - d * 0.7
                    if holder == own_id:
                        score += 30
                options.append((score, p))
        if not options:
            return None
        options.sort(reverse=True)
        for _, p in options[:4]:
            if arena is None or arena.clear_ray(raised(pos, 2.5), raised(p, 1.05)):
                return p[:2]
        return None

    def route(self, pos, goal, zone, radius, height, stuck, until):
        arena = self.arena
        if arena is None or distance(pos, goal) < 0.5:
            return goal
        cell = arena.cell(*pos[:2])
        end_cell = arena.cell(*goal)
        if cell is None:
            return arena.inset(goal, radius + 0.4)
        close_at_end = zone.next_radius <= DEATH_CIRCLE_M and distance(goal, zone.next_center) < 1
        elevated = pos[2] > arena.floor[cell] + arena.step_up + 1.5
        if (close_at_end and distance(pos, goal) < ROOF_APPROACH_M and end_cell is not None
                and arena.roof[end_cell] > arena.floor[end_cell] + arena.step_up):
            # A roof inside the final circle is reachable by jet even when ground routing goes around it.
            return goal
        if (elevated or not stuck) and distance(pos, goal) < ROUTE_DIRECT_M and arena.corridor(pos, goal, radius, height):
            self.path, self.search, self.route_goal = (), None, None
            return goal
        if elevated:
            return arena.inset(goal, radius + 0.4)
        if self.route_goal is None or distance(goal, self.route_goal) > ROUTE_REPLAN_M:
            self.route_goal = self.search = None
            self.path, self.path_index = (), 0
        if self.route_goal is None and time.perf_counter() < until:
            start = arena.nearest_open(pos, radius, rings=3)
            target = arena.nearest_open(goal, radius, rings=9 if close_at_end else 6)
            if start is not None and target is not None and start != target:
                self.route_goal = goal
                self.search = RouteSearch(arena, start, target, radius)
        if self.search is not None:
            path = self.search.advance(min(until, time.perf_counter() + ROUTE_SLICE_S))
            if self.search.done:
                self.search = None
                self.path, self.path_index = path, 0
        if self.path:
            while self.path_index + 1 < len(self.path) and distance(pos, self.path[self.path_index]) < 2.7:
                self.path_index += 1
            for i in range(min(self.path_index + ROUTE_LOOKAHEAD_CELLS, len(self.path) - 1), self.path_index - 1, -1):
                if arena.corridor(pos, self.path[i], radius, height):
                    self.path_index = i
                    return self.path[i]
            if stuck:
                self.route_goal = None
            return self.path[self.path_index]
        return goal

    def movement(self, pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction, stats,
                 grounded, energy, now, until, in_zone, terminal_burn, drop_hint):
        arena = self.arena
        walk = limit(self.phys("walk_speed", 11.7, stats), 2, 60)
        boost = limit(self.phys("boost_speed", 19.5, stats), walk, 90)
        radius = limit(self.phys("radius", 2.5, stats), 0.5, 25)
        height = limit(self.phys("height", 9, stats), 1, 80)
        goal_distance = distance(pos, waypoint)
        if self.motion_origin is None or now - self.motion_time >= STUCK_WINDOW_S:
            if self.motion_origin is not None and distance(pos, self.motion_origin) < 1.0 and goal_distance > 6:
                self.stuck_until = now + STUCK_RETRY_S
            self.motion_origin, self.motion_time = pos, now
        stuck = now < self.stuck_until
        core = zone.radius <= DEATH_CIRCLE_M and not terminal_burn
        clearance = zone.gap(pos)
        sprint = energy > (JET_RESERVE if clearance < 0 else BOOST_RESERVE) and (
            (urgent and goal_distance > 12 and (clearance < 8 or zone.gap(pos, 4) < 3))
            or (evade and not core and (hazards or any(c.clear and c.dist < BOOST_THREAT_M for c in threats))))
        pace = boost if sprint and grounded else walk
        if core and in_zone and goal_distance < CORE_HOLD_M:
            return {"move": [0.0, 0.0]}
        if not core and (in_zone or terminal_burn) and goal_distance < HOLD_M and not evade and not hazards:
            return {"move": [0.0, 0.0]}
        course = bearing(pos, waypoint)
        if goal_distance < HOLD_M and evade and threats and not core:
            course = bearing(threats[0].pos, pos)
        dx, dy = math.cos(course), math.sin(course)
        goal_scale = limit(goal_distance / (pace * 0.40), 0, 1)
        if core:
            if not in_zone and goal_distance < CORE_HOLD_M:
                goal_scale = limit(goal_distance / (pace * self.dt), 0, 0.8)
            else:
                goal_scale = limit(goal_distance / CORE_SLOW_M, 0.03, 0.8)
        scale = 1.0 if (evade or hazards) and not core else goal_scale
        horizon = CORE_HORIZON_S if core else STEER_HORIZON_S
        best_score, move = -math.inf, (dx * scale, dy * scale)
        clear_forward = True
        if arena is not None:
            probe = pos[0] + dx * (radius + 3), pos[1] + dy * (radius + 3), pos[2]
            clear_forward = not arena.obstacle(probe, radius, height, 0.9)
        steering_threats = threats[:3]
        concealed_muzzle = None
        if (SQUAD_EXPOSURE_PENALTY > 0 and arena is not None and evade and in_zone and not urgent and not hazards
                and zone.gap(pos, 4) > pace * horizon + 2):
            squad = [c for c in steering_threats if c.kind == "mech"]
            if len(squad) >= 2:
                for c in squad:
                    if not c.clear:
                        muzzle = raised(c.pos, 7 * c.scale)
                        if not arena.clear_ray(muzzle, raised(pos, height * 0.65)):
                            concealed_muzzle = muzzle
                            break
        evaluation_angles = (0, 0.40, -0.40, 0.92, -0.92) if core and clear_forward else STEER_ANGLES
        for offset in evaluation_angles:
            if time.perf_counter() >= until:
                break
            mx, my = math.cos(course + offset) * scale, math.sin(course + offset) * scale
            x, y, z = pos
            # The first probe includes inertial drift as the new velocity takes effect.
            turn = min(0.14 if grounded else 0.26, horizon * 0.5)
            px, py = x + (vel[0] * turn + mx * pace * (horizon - turn)), y + (vel[1] * turn + my * pace * (horizon - turn))
            endpoint = px, py, z
            wall = False
            if arena is not None:
                wall = not arena.corridor(pos, endpoint, radius, height)
            progress = goal_distance - distance(endpoint, waypoint)
            score = progress * (3.1 if urgent else 1.35)
            if not terminal_burn:
                gap = zone.gap(endpoint, 0.8)
                score -= max(0, min(9, zone.radius * 0.25) - gap) * (4.2 if core else 2.6)
            score -= abs(offset) * 0.38
            if wall:
                score -= 76
            if arena is not None and not core and not wall:
                score += max(0, 12 - abs(arena.near_cover(endpoint) - (radius + 6))) * 0.23
                if drop_hint is not None and progress > 0:
                    if not arena.clear_ray(raised(drop_hint, 7), raised(endpoint, height * 0.65)):
                        score += 2
                # Keep a wall between us and a second mech while disengaging.
                if concealed_muzzle is not None and arena.clear_ray(concealed_muzzle, raised(endpoint, height * 0.65)):
                    score -= SQUAD_EXPOSURE_PENALTY
            for c in steering_threats:
                delta = distance(endpoint, c.pos) - distance(pos, c.pos)
                score += delta * (0.8 if c.dist < 36 else 0.45)
                if c.clear and arena is not None and not wall:
                    if not arena.clear_ray(raised(c.pos, 7 * c.scale if c.kind == "mech" else 2.2), raised(endpoint, height * 0.65)):
                        score += 17 if not urgent else 8
            for impact, seconds, reach in hazards:
                future = x + mx * pace * seconds, y + my * pace * seconds
                score -= max(0, reach - distance(future, impact)) * (2.1 if not core else 1.0)
            if direction is not None and not threats and evade:
                score -= (mx * math.cos(direction) + my * math.sin(direction)) * 1.5
            if score > best_score:
                best_score, move = score, (mx, my)
        jet = False
        jump = False
        terminal_roof = False
        if arena is not None and urgent and zone.next_radius <= DEATH_CIRCLE_M and goal_distance < ROOF_APPROACH_M:
            cell = arena.cell(*waypoint)
            terminal_roof = (distance(waypoint, zone.next_center) < 2 and cell is not None
                             and arena.roof[cell] > pos[2] + arena.step_up)
        if arena is not None and not clear_forward and urgent and (stuck or core or terminal_roof) and energy > JET_RESERVE:
            overhead = arena.solid(raised(pos, height + 1.0))
            if not overhead:
                # A short approach when facing a wall buys altitude while preserving jet fuel.
                move = dx * 0.52, dy * 0.52
                jump, jet = grounded, not grounded
        if not grounded:
            cell = arena.cell(*pos[:2]) if arena is not None else None
            if cell is not None and vel[2] < -3 and pos[2] - arena.roof[cell] > 4 and urgent and energy > 30:
                jet = True
        return {"move": list(move), "boost": (sprint and grounded and not jump) or jet, "jump": jump}

    def target(self, obs, pos, contacts, fraction, zone, must_move, safe, terminal_burn, repairing, incoming):
        targets = []
        alive = number(obs.get("alive"), 16)
        duel = alive == 2
        quiet = (not must_move and not incoming and zone.now - self.last_damage >= HIT_MEMORY_S
                 and (duel or zone.now - self.last_sound >= SOUND_MEMORY_S))
        nearby_rivals = {c.id for c in contacts if c.kind == "mech" and c.clear and c.dist < LOOT_THREAT_M}
        front_half_arc = math.radians(limit(self.phys("front_arc_deg", 180), 0, 360)) / 2
        for c in contacts:
            if not c.clear or c.hp <= 0:
                continue
            weak = c.hp < min(c.max_hp * WEAK_FRACTION, 430)
            rear = c.aim is not None and c.face_error > front_half_arc
            if c.kind == "npc":
                allowed = c.attacker and c.dist < 58 and (not must_move or c.dist < 27)
                allowed |= safe and not repairing and c.dist < 62 and (weak or (fraction > 0.88 and c.dist > 35))
                merit = 26 + 35 * c.attacker + 22 * weak
            else:
                active = c.face_error < 0.45 and c.dist < (105 if c.charging else 46)
                finishing = (fraction > HEAL_FRACTION and not must_move and weak and c.dist < (112 if rear else 68)
                             and (not repairing or c.hp <= 115))
                busy = rear and c.charging and c.dist < 64 and fraction > 0.84 and not must_move and not repairing
                endgame = (duel and terminal_burn) or (alive <= 3 and zone.radius < 31 and c.dist < 36)
                opportunity = (quiet and nearby_rivals.issubset((c.id,))
                               and (duel or (rear and c.dist < 112))
                               and (not repairing or (duel and rear)))
                allowed = c.attacker or active or finishing or busy or endgame or opportunity
                if fraction < HEAL_FRACTION and not (c.attacker or active or endgame or opportunity and duel or c.hp < 115):
                    allowed = False
                merit = 48 + 55 * c.attacker + 40 * active + 25 * weak + 14 * rear + 19 * endgame
            if allowed:
                targets.append((merit - c.dist * 0.26 + 8 * (c.id == self.last_fire_target), c))
        if safe and not must_move and not repairing and fraction > HEAL_FRACTION:
            for item in seq(obs.get("crates"))[:36]:
                item = obj(item)
                p, ident = vec(item.get("pos"), 3), number(item.get("id"), None)
                if p is None or ident is None or abs(p[2] - pos[2]) > 6 or zone.gap(p, 10) < 4:
                    continue
                d = distance(pos, p)
                if d > CRATE_RANGE_M:
                    continue
                hp = number(item.get("hp"), 300)
                targets.append((24 + (300 - hp) * 0.06 - d * 0.27 + 8 * (ident == self.last_fire_target),
                                Contact(ident, "crate", p, ZERO, None, hp, 300, 1, d, 0, True, False, False, ())))
        return sorted(targets, key=lambda choice: choice[0], reverse=True)[:4]

    def aim_for(self, weapon, target, base, muzzle, pitch_bounds):
        kind = weapon["kind"]
        stats = obj(weapon.get("stats"))
        defaults = obj(self.weapon_config.get(kind))
        def setting(key, fallback):
            return number(stats.get(key), number(defaults.get(key), fallback))

        if target.kind == "mech":
            radius, height = self.phys("radius", 2.5) * target.scale, self.phys("height", 9) * target.scale
        else:
            body = self.npc if target.kind == "npc" else self.crates
            radius = number(body.get("radius"), 1.8)
            height = number(body.get("height"), 3.5 if target.kind == "npc" else 2.4)
        origin = raised(base, muzzle if kind != "mortar" else max(muzzle + 0.5, muzzle * 9.5 / 7.0))
        aim_center = raised(target.pos, height * 0.53)
        lead = 0.0
        d = math.dist(origin, aim_center)
        if kind == "gun":
            reach, speed = setting("range", 230), setting("speed", 252)
            if d > reach or speed <= 1:
                return None
            for _ in range(3):
                lead = self.physics_dt + max(0, d - 3.0) / speed
                point = tuple(a + v * lead for a, v in zip(aim_center, target.vel))
                d = math.dist(origin, point)
        elif kind == "mortar":
            gravity, speed = setting("gravity", 22), setting("speed", 72)
            if not MORTAR_MIN_M <= target.dist <= MORTAR_RANGE_M or speed <= 1:
                return None
            lead = d / speed
            for _ in range(5):
                point = tuple(a + v * (lead + self.physics_dt) for a, v in zip(aim_center, target.vel))
                point = raised(point, gravity * lead * lead * 0.5)
                lead = max(0.01, (math.dist(origin, point) - 3) / speed)
        elif kind == "laser":
            if d > setting("range", 280):
                return None
            point = tuple(a + v * self.physics_dt for a, v in zip(aim_center, target.vel))
        else:
            if d > setting("range", 45) * 0.97:
                return None
            point = aim_center

        dx, dy, dz = (a - b for a, b in zip(point, origin))
        horizontal = math.hypot(dx, dy)
        yaw, pitch = math.atan2(dy, dx), math.atan2(dz, horizontal)
        if not pitch_bounds[0] <= pitch <= pitch_bounds[1] and kind != "lightning":
            return None
        if self.arena is not None:
            if kind == "mortar":
                previous = origin
                for i in range(1, 9):
                    f = i / 8
                    following = origin[0] + dx * f, origin[1] + dy * f, origin[2] + dz * f - gravity * (lead * f) ** 2 / 2
                    if not self.arena.clear_ray(previous, following) or self.arena.solid(following):
                        return None
                    previous = following
            elif not self.arena.clear_ray(origin, point):
                return None
        tolerance = (math.radians(setting("cone_deg", 30)) * 0.38 if kind == "lightning"
                     else math.atan2(max(0.65, radius * (1.4 if kind == "mortar" else 0.82)), max(1.0, horizontal)))
        vertical = math.atan2(max(0.70, height * 0.37), max(1.0, horizontal))
        return yaw, limit(pitch, *pitch_bounds), tolerance, vertical

    def combat(self, obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy, fraction, zone,
               action, until, terminal_burn, repairing, incoming):
        muzzle = self.phys("muzzle_height", 7, stats)
        pitch_bounds = self.phys("min_pitch", -0.7, stats), self.phys("max_pitch", 1.3, stats)
        firing = [False, False]
        action["fire"] = firing
        selected = None
        best = -math.inf
        evacuating = (not terminal_burn and
                      (must_move or action.get("boost") or (evade and fraction < HEAL_FRACTION)
                       or (zone.radius <= DEATH_CIRCLE_M and math.hypot(*action["move"]) > 0.35)))
        targets = self.target(obs, pos, contacts, fraction, zone, must_move, safe, terminal_burn, repairing, incoming)
        for merit, target in targets:
            for i, weapon in enumerate(weapons):
                if time.perf_counter() >= until:
                    break
                kind = weapon.get("kind")
                if kind not in ("gun", "mortar", "laser", "lightning"):
                    continue
                if kind == "gun" and (number(weapon.get("reload")) > 0 or number(weapon.get("ammo"), 1) <= 0):
                    continue
                if kind == "lightning" and energy < BOOST_RESERVE + (8 if must_move else 0):
                    continue
                charge = number(weapon.get("charge"))
                if kind == "laser" and evacuating and charge <= 0:
                    continue
                if kind == "mortar" and target.kind == "crate":
                    continue
                plan = self.aim_for(weapon, target, pos, muzzle, pitch_bounds)
                if plan is None:
                    continue
                cooldown = number(weapon.get("cooldown"))
                yaw_diff = abs(angle(plan[0] - actual[0]))
                priority = {"gun": 10, "laser": 24, "lightning": 25, "mortar": 24}[kind]
                if kind == "lightning" and "laser" in target.armed:
                    priority += 15
                if kind == "laser" and "mortar" in target.armed:
                    priority += 15
                if kind == "mortar":
                    priority -= min(25, target.dist / 80 * math.hypot(*target.vel[:2]) * 1.6)
                priority += 85 if charge > 0 else 0
                score = merit + priority - min(1.2, cooldown) * 39 - yaw_diff * 4
                if score > best:
                    selected = (target, i, plan, charge, cooldown)
                    best = score
            if selected and selected[0] is target:
                break

        if selected is not None:
            target, index, plan, charge, cooldown = selected
            yaw, pitch, tolerance, vertical = plan
            weapon = weapons[index]
            kind = weapon["kind"]
            yaw_error, pitch_error = abs(angle(yaw - actual[0])), abs(pitch - actual[1])
            # Keep a narrow gate until the actual torso is almost aligned. Rotation on this
            # simulation step is limited, so a distant shot cannot rely on the commanded angle.
            yaw_allow = min(ARMING_YAW_ALLOW_RAD, self.phys("turn_rate", 4, stats) * self.physics_dt * 0.52)
            pitch_allow = min(ARMING_PITCH_ALLOW_RAD, self.phys("pitch_rate", 3, stats) * self.physics_dt * 0.52)
            aligned = yaw_error <= tolerance + yaw_allow and (kind == "lightning" or pitch_error <= vertical + pitch_allow)
            action["aim"] = [yaw, pitch]
            self.last_fire_target = target.id
            if kind == "laser":
                defaults = obj(self.weapon_config.get("laser"))
                charged = number(obj(weapon.get("stats")).get("charge"), number(defaults.get("charge"), 0.75))
                if charge > 0:
                    firing[index] = not (evacuating or (aligned and charge >= charged - self.physics_dt))
                elif cooldown <= self.physics_dt and aligned:
                    firing[index] = True
            elif cooldown <= self.dt + 0.025:
                firing[index] = aligned
            for i, other in enumerate(weapons):
                if i == index or other.get("kind") != "gun" or number(other.get("reload")) > 0 or number(other.get("ammo"), 1) <= 0:
                    continue
                if time.perf_counter() >= until or number(other.get("cooldown")) > self.dt + 0.025:
                    continue
                second = self.aim_for(other, target, pos, muzzle, pitch_bounds)
                if second:
                    gun_yaw, gun_pitch, gun_width, gun_height = second
                    firing[i] = (abs(angle(gun_yaw - actual[0])) <= gun_width and abs(gun_pitch - actual[1]) <= gun_height
                                 and abs(angle(gun_yaw - yaw)) <= gun_width and abs(gun_pitch - pitch) <= gun_height)
        else:
            self.last_fire_target = None
        for i, weapon in enumerate(weapons):
            if weapon.get("kind") == "gun" and not firing[i] and number(weapon.get("reload")) <= 0:
                ammo = number(weapon.get("ammo"), math.inf)
                mag = number(obj(weapon.get("stats")).get("mag"), 12)
                if ammo <= 0 or (safe and selected is None and ammo <= mag * RELOAD_FRACTION):
                    action["reload"] = True

    def act(self, obs):
        begin = time.perf_counter()
        until = begin + PLAN_BUDGET_S
        obs = obj(obs)
        me = obj(obs.get("self"))
        zone_obs = obj(obs.get("zone"))
        action = {}
        pos = vec(me.get("pos"), 3)
        offer = seq(obj(obs.get("offer")).get("choices"))[:3]
        if offer:
            def upgrade(i):
                ident = obj(offer[i]).get("id")
                priority = UPGRADE_RANK.get(ident, 0) if isinstance(ident, str) else 0
                if ident == "nanites" and number(zone_obs.get("radius"), math.inf) < 45:
                    priority -= 28
                return priority
            action["pick"] = max(range(len(offer)), key=upgrade)
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
                # Even straight-line travel to the current edge is too slow in this case.
                # A collapsed center at the reported position can still be unsafe due to rounding.
                pace = limit(self.phys("boost_speed", 19.5, stats), walk, 90)
                survival = min(hp / zone.dps, max(0, self.match_end - now))
                terminal_burn = (-gap > pace * survival
                                 or (zone.radius == 0 and distance(pos, center) < 1e-6))
            if terminal_burn:
                goal, urgent = pos[:2], False
            elif not urgent:
                goal, urgent = center, True
        self.remember(obs, now)
        repair_wait = max(0, self.phys("regen_delay", 5, stats) - (now - self.last_repair_reset))
        repairing = (in_zone and fraction < 1 and self.phys("regen_per_s", 45, stats) > 0
                     and now + repair_wait < self.match_end)
        contacts = self.contacts(obs, pos, eye)
        drop_hint = self.supply_hint(obs, pos, contacts, now) if self.arena is not None else None
        threats = [c for c in contacts if (c.kind == "mech" and c.dist < THREAT_RANGE_M) or c.attacker]
        hostile = any(c.clear and (c.attacker or (c.dist < EVADE_RANGE_M and c.kind == "mech")) for c in threats)
        just_hit = now - self.last_damage < HIT_MEMORY_S
        heard = now - self.last_sound < SOUND_MEMORY_S
        direction = self.damage_bearing if just_hit else self.sound_bearing if heard else None
        hazards = self.nearby_shells(obs, pos, velocity, height)
        evade = hostile or just_hit or bool(hazards)
        safe = not (terminal_burn or evade or heard
                    or any(c.kind == "mech" and c.clear and c.dist < LOOT_THREAT_M for c in contacts))
        items = seq(me.get("weapons"))
        weapons = [obj(items[i]) if i < len(items) else {} for i in range(2)]
        moving_to_evade = evade

        if self.arena is not None:
            goal = self.arena.inset(goal, radius + 0.4)
        pickup = self.loot_goal(obs, pos, zone, contacts, weapons, fraction, cubes, safe, urgent, action)
        if not in_zone or not safe or threats or pickup is not None or (urgent and gap < walk):
            drop_hint = None
        if not urgent:
            if pickup is not None:
                goal = pickup
            elif time.perf_counter() < until:
                cover = self.shelter_point(pos, zone, contacts, direction, radius, height, now,
                                           min(until, begin + 0.0029), terminal_burn)
                if cover is not None:
                    goal = cover
                    if distance(pos, cover) < HOLD_M and not hostile and not hazards:
                        moving_to_evade = False
                elif evade:
                    away = bearing(threats[0].pos, pos) if threats else angle((direction if direction is not None else actual[0]) + math.pi)
                    p = pos[0] + COVER_AWAY_M * math.cos(away), pos[1] + COVER_AWAY_M * math.sin(away)
                    if terminal_burn or zone.gap(p, 4) > 2:
                        goal = p
                elif not terminal_burn and (self.arena is None or self.arena.near_cover(pos) > COVER_NEAR_M * 1.7):
                    p = zone.next_center
                    if distance(pos, p) < 12:
                        p = (pos[0] + 22 * math.cos(self.scout_yaw), pos[1] + 22 * math.sin(self.scout_yaw))
                    if zone.gap(p, 5) > 4:
                        goal = p

        waypoint = self.route(pos, goal, zone, radius, height, now < self.stuck_until,
                              min(until, time.perf_counter() + ROUTE_SLICE_S))
        action.update(self.movement(pos, velocity, waypoint, zone, urgent, moving_to_evade, threats, hazards, direction,
                                    stats, grounded, energy, now, min(until, time.perf_counter() + 0.0020),
                                    in_zone, terminal_burn, drop_hint))
        if threats and (evade or threats[0].clear):
            direction = bearing(pos, threats[0].pos)
        if direction is None:
            if distance(pos, waypoint) > 2:
                direction = bearing(pos, waypoint)
            else:
                direction = angle(self.scout_yaw + now * SCAN_RATE)
        action["aim"] = [direction, 0.0]
        if time.perf_counter() < until:
            # Small-circle steering still centers the mech when holding is safe.
            must_move = urgent and (not in_zone or size > DEATH_CIRCLE_M or zone.gap(pos, STEER_HORIZON_S) < 0)
            self.combat(obs, pos, weapons, actual, stats, contacts, safe, must_move, evade, energy, fraction, zone,
                        action, until, terminal_burn, repairing, bool(hazards))
        return action


if __name__ == "__main__":
    mf.run(Bot)
