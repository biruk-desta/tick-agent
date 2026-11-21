

from array import array
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from struct import Struct
import sys

from example_bot import angle, bearing, distance, limit, number, obj, raised, read_map_file, seq, vec


ZERO = (0.0, 0.0)
ZERO3 = (0.0, 0.0, 0.0)
INF = math.inf
HEADINGS = tuple((math.cos(i * math.pi / 8), math.sin(i * math.pi / 8)) for i in range(16))
EXPOSURE_HEADINGS = tuple((math.cos(i * math.pi / 12), math.sin(i * math.pi / 12)) for i in range(24))
FIGHT_RING = tuple((direction, 6) for direction in HEADINGS)
SQUAD_STEPS = ((ZERO, 0),) + FIGHT_RING
OPEN_STEPS = SQUAD_STEPS + tuple((direction, 12) for direction in HEADINGS)
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
RANK = {"laser": 4, "lightning": 3, "mortar": 1}
OPEN_UPGRADES = ("Composite plating", "Reactive armor", "Tungsten rounds", "Repair nanites",
                 "Rotary feed", "Superconductor", "Tesla coil", "Focusing lens", "Leg servos",
                 "Fast capacitors")
SQUAD_UPGRADES = ("Composite plating", "Reactive armor", "Focusing lens", "Fast capacitors",
                  "Repair nanites", "Tungsten rounds", "Rotary feed", "Superconductor",
                  "Tesla coil", "Leg servos")
END_UPGRADES = ("Drum magazine", "Rail barrel", "Torso gyros", "Arc relay", "Reactor tune",
                "Capacitor bank", "Autoloader", "Cluster shells", "Long tube", "Sensor suite",
                "Efficient jets", "Phased beam")
FLOAT32 = Struct("=f")
RNG_LENGTH, RNG_TAP = 607, 273
WORD_MASK = (1 << 64) - 1
SIGNED_MASK = (1 << 63) - 1
MOVEMENT_RAYS = 360
ROUTE_SLICE = 640
ESCAPE_SLICE = 640
COVER_CELLS = 96
COVER_RAYS = 112
HOME_SAMPLES = 5
SHELL_STEPS = 400
FLAT_WORLD = {
    "terrain": {"minX": -513, "minY": -334, "nx": 1070, "ny": 724},
    "bounds": {"minX": -512, "maxX": 555, "minY": -333, "maxY": 388},
    "prisms": (),
}


def seed_words(seed, first_shift, second_shift):
    modulus = (1 << 31) - 1
    value = seed % modulus or 89482311
    words = []
    for i in range(-20, RNG_LENGTH):
        value = value * 48271 % modulus
        if i >= 0:
            high = value << first_shift
            value = value * 48271 % modulus
            middle = value << second_shift
            value = value * 48271 % modulus
            words.append(high ^ middle ^ value)
    return words


def multiply_rng_polynomials(lhs, rhs):





    width = 18
    left = int.from_bytes(b"".join(v.to_bytes(width, "little") for v in lhs), "little")
    right = int.from_bytes(b"".join(v.to_bytes(width, "little") for v in rhs), "little")
    packed = (left * right).to_bytes((2 * RNG_LENGTH - 1) * width, "little")
    coeffs = [int.from_bytes(packed[i:i + 8], "little") for i in range(0, len(packed), width)]
    for i in range(len(coeffs) - 1, RNG_LENGTH - 1, -1):
        coeffs[i - RNG_TAP] = (coeffs[i - RNG_TAP] + coeffs[i]) & WORD_MASK
        coeffs[i - RNG_LENGTH] = (coeffs[i - RNG_LENGTH] + coeffs[i]) & WORD_MASK
    return coeffs[:RNG_LENGTH]


@lru_cache(maxsize=1)
def rng_seed_mix():

    state = seed_words(1, 20, 10)
    first = []
    for i in range(RNG_LENGTH):
        feed, tap = (RNG_LENGTH - RNG_TAP - 1 - i) % RNG_LENGTH, (-1 - i) % RNG_LENGTH
        state[feed] = (state[feed] + state[tap]) & WORD_MASK
        first.append(state[feed])
    start = 7_800_000_000_000 - RNG_LENGTH
    power = [0, 1] + [0] * (RNG_LENGTH - 2)
    weights = [1] + [0] * (RNG_LENGTH - 1)
    exponent = start
    while exponent:
        if exponent & 1:
            weights = multiply_rng_polynomials(weights, power)
        power = multiply_rng_polynomials(power, power)
        exponent >>= 1
    for i in range(start, start + RNG_LENGTH):
        value = sum(a * b for a, b in zip(weights, first)) & WORD_MASK
        state[(RNG_LENGTH - RNG_TAP - 1 - i) % RNG_LENGTH] = value
        top = weights.pop()
        weights.insert(0, top)
        index = RNG_LENGTH - RNG_TAP
        weights[index] = (weights[index] + top) & WORD_MASK
    return tuple(state)


class RandomStream:


    def __init__(self, seed):
        seed = ((int(seed) + (1 << 63)) & WORD_MASK) - (1 << 63)
        self.state = [a ^ b for a, b in zip(seed_words(seed, 40, 20), rng_seed_mix())]
        self.feed, self.tap = RNG_LENGTH - RNG_TAP, 0

    def random(self):
        while True:
            self.feed = (self.feed - 1) % RNG_LENGTH
            self.tap = (self.tap - 1) % RNG_LENGTH
            value = (self.state[self.feed] + self.state[self.tap]) & WORD_MASK
            self.state[self.feed] = value
            fraction = (value & SIGNED_MASK) / (1 << 63)
            if fraction < 1:
                return fraction


def f32(value):
    return FLOAT32.unpack(FLOAT32.pack(value))[0]


def vector(value, size):
    return vec(value, size) or tuple(number(v) for v in (list(seq(value)) + [0] * size)[:size])


def heading(yaw):
    return math.cos(yaw), math.sin(yaw)


def unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    span = math.hypot(dx, dy)
    return (dx / span, dy / span) if span >= 1e-6 else ZERO


def offset(p, direction, span):
    return p[0] + direction[0] * span, p[1] + direction[1] * span


def aim_from(start, end):
    dx, dy, dz = end[0] - start[0], end[1] - start[1], end[2] - start[2]
    return math.atan2(dy, dx), math.atan2(dz, math.hypot(dx, dy))


class Prism:
    def __init__(self, raw):
        self.base, self.top = raw["base"], raw["top"]
        self.bridge = raw["kind"] == "bridge"
        rings = [list(zip(r[::2], r[1::2])) for r in (raw["ring"], *raw.get("holes", ()))]
        self.edges = [(ax, ay, bx - ax, by - ay)
                      for ring in rings for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1])]
        xs, ys = zip(*rings[0])
        self.bounds = min(xs), min(ys), max(xs), max(ys)

    def contains(self, x, y):
        left, bottom, right, top = self.bounds
        if not (left <= x <= right and bottom <= y <= top):
            return False
        inside = False
        for ax, ay, dx, dy in self.edges:
            if (ay > y) != (ay + dy > y) and x < ax + (y - ay) * dx / dy:
                inside = not inside
        return inside

    def near(self, x, y, radius):
        if self.contains(x, y):
            return True
        threshold = radius * radius
        for ax, ay, dx, dy in self.edges:
            px, py = x - ax, y - ay
            span = dx * dx + dy * dy
            t = limit((px * dx + py * dy) / span, 0, 1) if span else 0
            if (px - dx * t) ** 2 + (py - dy * t) ** 2 < threshold:
                return True
        return False

    def blocks(self, start, delta, bounds):
        x, y, z = start
        dx, dy, dz = delta
        x0, y0, low, x1, y1, high = bounds
        if low > self.top or high < self.base:
            return False
        left, bottom, right, top = self.bounds
        if x1 < left or x0 > right or y1 < bottom or y0 > top:
            return False
        if self.base <= z <= self.top and self.contains(x, y):
            return True
        if abs(dz) > 1e-9:
            face = self.base if dz > 0 else self.top
            t = (face - z) / dz
            if 0 <= t < 1 and self.contains(x + dx * t, y + dy * t):
                return True
        for ax, ay, ex, ey in self.edges:
            cross = dx * ey - dy * ex
            if abs(cross) < 1e-9:
                continue
            px, py = ax - x, ay - y
            t = (px * ey - py * ex) / cross
            if 0 <= t < 1 and self.base <= z + dz * t <= self.top:
                if 0 <= (px * dy - py * dx) / cross <= 1:
                    return True
        return False


class PracticeMap:


    def __init__(self, directory=None, *, world=None, heights=None):
        if world is None:
            try:
                root = Path(directory or "/arena") / "v2"
                world = json.loads(read_map_file(root / "world.json"))
                raw = read_map_file(root / "terrain.i16")
                samples = array("h", raw)
                if sys.byteorder != "little":
                    samples.byteswap()
                terrain = world["terrain"]
                if (terrain["step"] != 1 or not 2 <= terrain["nx"] <= 2048
                        or not 2 <= terrain["ny"] <= 2048
                        or len(samples) != terrain["nx"] * terrain["ny"]):
                    raise ValueError("Invalid terrain grid")
                heights = array("f", (h * 0.01 for h in samples))
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                world = FLAT_WORLD
        terrain, bounds = world["terrain"], world["bounds"]
        self.x0, self.y0 = terrain["minX"], terrain["minY"]
        self.nx, self.ny = nx, ny = terrain["nx"], terrain["ny"]
        self.left, self.right, self.bottom, self.top = (bounds[k] for k in ("minX", "maxX", "minY", "maxY"))
        self.heights = heights if heights is not None else array("f", [0]) * (nx * ny)
        self.terrain_top = max(self.heights)
        self.terrain_bottom = min(self.heights)
        self.prisms = [Prism(raw) for raw in world["prisms"] if len(raw["ring"]) >= 6]
        self.bx, self.by = self.left - 16, self.bottom - 16
        self.buckets = {}
        for prism in self.prisms:
            x0, y0, x1, y1 = prism.bounds
            for j in range(math.floor((y0 - self.by) / 16), math.floor((y1 - self.by) / 16) + 1):
                for i in range(math.floor((x0 - self.bx) / 16), math.floor((x1 - self.bx) / 16) + 1):
                    self.buckets.setdefault((i, j), []).append(prism)
        self.solid_top = max((p.top for p in self.prisms), default=-INF)
        self.block_width = (nx + 7) // 8
        block_rows = (ny + 7) // 8
        if self.terrain_top == self.terrain_bottom:
            self.block_max = [self.terrain_top] * (self.block_width * block_rows)
        else:
            maxima = [max(max(self.heights[row * nx + col:row * nx + min(col + 8, nx)])
                          for row in range(y, min(y + 8, ny)))
                      for y in range(0, ny, 8) for col in range(0, nx, 8)]
            width = self.block_width
            self.block_max = [max(maxima[row * width + col2] for row in range(j, min(j + 2, block_rows))
                                  for col2 in range(i, min(i + 2, width)))
                              for j in range(block_rows) for i in range(width)]
        self.build_raster()
        self.build_grid()

    def inside(self, x, y):
        return self.left < x < self.right and self.bottom < y < self.top

    def bare(self, x, y):
        if self.terrain_top == self.terrain_bottom:
            return self.terrain_top
        u = limit(x - self.x0, 0, self.nx - 1.000001)
        v = limit(y - self.y0, 0, self.ny - 1.000001)
        i, j = int(u), int(v)
        fx, fy = u - i, v - j
        idx = j * self.nx + i
        g = self.heights
        a = g[idx] + fx * (g[idx + 1] - g[idx])
        idx += self.nx
        b = g[idx] + fx * (g[idx + 1] - g[idx])
        return a + fy * (b - a)

    def local_prisms(self, x, y):
        return self.buckets.get((math.floor((x - self.bx) / 16), math.floor((y - self.by) / 16)), ())

    def surface(self, x, y, decks=True):
        ground = self.bare(x, y)
        candidates = [p for p in self.local_prisms(x, y) if p.top > ground and p.contains(x, y)]
        return self.stack(ground, candidates, decks)

    @staticmethod
    def stack(ground, candidates, decks=True):
        surface = ground
        for _ in range(8):
            previous = surface
            for p in candidates:
                if p.top > surface and (p.base <= surface + 1.5 or decks and p.bridge and p.top < ground + 6.5):
                    surface = p.top
            if surface == previous:
                break
        return surface

    def solid(self, point):
        x, y, z = point
        return z < self.bare(x, y) or any(p.base < z < p.top and p.contains(x, y)
                                          for p in self.local_prisms(x, y))

    def clear_ray(self, start, end):
        x, y, z = start
        ex, ey, ez = end
        dx, dy, dz = ex - x, ey - y, ez - z
        low, high = min(z, ez), max(z, ez)
        check_terrain = low < self.terrain_top
        if check_terrain and (z < self.bare(x, y) or ez < self.bare(ex, ey)):
            return False
        if self.buckets and low <= self.solid_top:
            bx, by = self.bx, self.by
            i, j = math.floor((x - bx) / 16), math.floor((y - by) / 16)
            si, sj = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
            tx = (bx + (i + (si > 0)) * 16 - x) / dx if dx else INF
            ty = (by + (j + (sj > 0)) * 16 - y) / dy if dy else INF
            dtx, dty = abs(16 / dx) if dx else INF, abs(16 / dy) if dy else INF
            seen = set()
            delta = dx, dy, dz
            bounds = min(x, ex), min(y, ey), low, max(x, ex), max(y, ey), high
            for _ in range(4096):
                for p in self.buckets.get((i, j), ()):
                    if p not in seen:
                        if p.blocks(start, delta, bounds):
                            return False
                        seen.add(p)
                if tx >= 1 and ty >= 1:
                    break
                if tx < ty:
                    i, tx = i + si, tx + dtx
                else:
                    j, ty = j + sj, ty + dty
        span = math.hypot(dx, dy)
        return not check_terrain or span <= 1e-9 or self.terrain_clear(start, (dx, dy, dz), 0.5 / span)

    def terrain_clear(self, start, delta, step):
        x, y, z = start
        dx, dy, dz = delta
        x0, y0 = self.x0, self.y0
        nx, ny = self.nx, self.ny
        width, blocks = self.block_width, self.block_max
        t = 0.0
        at_z = z
        for _ in range(100001):
            u, v = x + dx * t - x0, y + dy * t - y0
            i = (0 if u < 0 else nx - 1 if u >= nx else int(u)) // 8
            j = (0 if v < 0 else ny - 1 if v >= ny else int(v)) // 8
            peak = blocks[j * width + i]
            if at_z > peak:
                tx = (8 * (i + (dx > 0)) + x0 - x) / dx if dx else INF
                ty = (8 * (j + (dy > 0)) + y0 - y) / dy if dy else INF
                edge = min(1, min(tx if tx > t else INF, ty if ty > t else INF) + 1e-6)
                if z + dz * edge > peak:

                    t, at_z = edge, z + dz * edge
                    if t >= 1:
                        return True
                    continue
            elif at_z < self.bare(x + dx * t, y + dy * t):
                return False
            t += step
            if t >= 1:
                return True
            at_z = z + dz * t
        return True

    def build_raster(self):
        nx, ny = self.nx, self.ny
        self.raster_top = tops = self.heights[:]
        self.raster_obstacle = obstacles = bytearray(nx * ny)
        self.raster_slabs = slabs = {}
        spans = {}
        for p in self.prisms:
            _, low, _, high = p.bounds
            for j in range(max(0, math.floor(low - self.y0)), min(ny, math.ceil(high - self.y0) + 1)):
                y = self.y0 + j + 0.0001
                crossings = sorted(ax + (y - ay) * dx / dy
                                   for ax, ay, dx, dy in p.edges if (ay > y) != (ay + dy > y))
                for left, right in zip(crossings[::2], crossings[1::2]):
                    start = j * nx + max(0, math.ceil(left - self.x0))
                    end = j * nx + min(nx, math.floor(right - self.x0) + 1)
                    for cell in range(start, end):
                        spans.setdefault(cell, []).append(p)
        for cell, items in spans.items():
            ground = level = tops[cell]
            for p in sorted(items, key=lambda p: p.base):
                if p.top <= level:
                    continue
                if p.base <= level + 1.5:
                    level = p.top
                else:
                    slabs.setdefault(cell, []).append((p.base, p.top))
                    if p.base < level + 10.5 and not (p.bridge and p.top < ground + 6.5):
                        obstacles[cell] = 1
            tops[cell] = level
            if level > ground + 1.2:
                obstacles[cell] = 1
        self.raster_ceiling = max(max(tops), self.solid_top)

    def raster_cell(self, x, y):
        return (int(limit(math.floor(y - self.y0 + 0.5), 0, self.ny - 1)) * self.nx
                + int(limit(math.floor(x - self.x0 + 0.5), 0, self.nx - 1)))

    def above_obstacle(self, pos):
        x, y, z = pos
        return bool(self.raster_obstacle[self.raster_cell(x, y)]) and z > self.bare(x, y) + 3

    def build_grid(self):
        self.w, self.h = w, h = (self.nx + 1) // 2, (self.ny + 1) // 2
        self.offsets = tuple(dy * w + dx for dx, dy in NEIGHBORS)
        self.nav_height = surfaces = array("f", (self.heights[j * self.nx + i]
                                                   for j in range(0, self.ny, 2)
                                                   for i in range(0, self.nx, 2)))
        self.free = free = bytearray(w * h)
        first_x = max(0, math.ceil((self.left + 2.6 - self.x0) / 2))
        last_x = min(w - 1, math.floor((self.right - 2.6 - self.x0) / 2))
        first_y = max(0, math.ceil((self.bottom + 2.6 - self.y0) / 2))
        last_y = min(h - 1, math.floor((self.top - 2.6 - self.y0) / 2))
        if first_x <= last_x:
            fill = b"\1" * (last_x - first_x + 1)
            for j in range(first_y, last_y + 1):
                free[j * w + first_x:j * w + last_x + 1] = fill
        nearby = {}
        for p in self.prisms:
            left, bottom, right, top = p.bounds
            for j in range(max(0, math.ceil((bottom - 2.6 - self.y0) / 2)),
                           min(h, math.floor((top + 2.6 - self.y0) / 2) + 1)):
                for i in range(max(0, math.ceil((left - 2.6 - self.x0) / 2)),
                               min(w, math.floor((right + 2.6 - self.x0) / 2) + 1)):
                    nearby.setdefault(j * w + i, []).append(p)
        for cell, candidates in nearby.items():
            y, x = divmod(cell, w)
            x, y = self.x0 + x * 2, self.y0 + y * 2
            ground = surfaces[cell]
            containing = [p for p in candidates if p.top > ground and p.contains(x, y)]
            surface = self.stack(ground, containing)
            surfaces[cell] = surface
            if (surface > ground + 1.5 and any(p.top == surface and not p.bridge for p in containing)
                    or any(p.top > surface + 1.2 and p.base < surface + 9 and p.near(x, y, 2.6)
                           for p in candidates)):
                free[cell] = 0
        self.steps = steps = bytearray(w * h)
        mutual = bytearray(w * h)
        for cell in range(w + 1, w * (h - 1) - 1):
            if not free[cell]:
                continue
            level = surfaces[cell]
            mask = 0
            for i, delta in enumerate(self.offsets[:4]):
                nxt = cell + delta
                if free[nxt] and surfaces[nxt] <= level + 2.2:
                    mask |= 1 << i
                    if level <= surfaces[nxt] + 2.2:
                        mutual[cell] |= 1 << i
            for i, (dx, dy) in enumerate(NEIGHBORS[4:], 4):
                nxt = cell + self.offsets[i]
                if free[nxt] and free[cell + dx] and free[cell + dy * w] and surfaces[nxt] <= level + 3.1:
                    mask |= 1 << i
            steps[cell] = mask
        self.clearance = clearance = bytearray(20 if passed else 0 for passed in free)
        for cell, value in enumerate(clearance):
            if value:
                clearance[cell] = min(value, clearance[cell - 1] + 2, clearance[cell - w] + 2)
        for cell in range(w * h - 1, -1, -1):
            if clearance[cell]:
                clearance[cell] = min(clearance[cell], clearance[cell + 1] + 2, clearance[cell + w] + 2)
        seen = bytearray(w * h)
        main = []
        adjacent = tuple(tuple(delta for i, delta in enumerate(self.offsets[:4]) if mask & (1 << i))
                         for mask in range(16))
        for start, passed in enumerate(free):
            if not passed or seen[start]:
                continue
            comp = [start]
            seen[start] = 1
            for cell in comp:
                for delta in adjacent[mutual[cell]]:
                    nxt = cell + delta
                    if not seen[nxt]:
                        seen[nxt] = 1
                        comp.append(nxt)
            if len(comp) > len(main):
                main = comp
        self.main = bytearray(w * h)
        for cell in main:
            self.main[cell] = 1
        self.landing_cell = self.build_landings() if len(main) < sum(free) else None
        self.step_offsets = tuple(tuple((delta, i >= 4) for i, delta in enumerate(self.offsets)
                                        if mask & (1 << i)) for mask in range(256))

    def build_landings(self):

        w, h = self.w, self.h
        landings = array("i", [-1]) * (w * h)
        frontier = []
        for cell, passed in enumerate(self.main):
            if not passed:
                continue
            landings[cell] = cell
            if any(not self.main[cell + delta] for delta in self.offsets):
                frontier.append(cell)
        for _ in range(20):
            following = []
            for cell in frontier:
                y, x = divmod(cell, w)
                for dx, dy in NEIGHBORS:
                    if 0 <= x + dx < w and 0 <= y + dy < h:
                        nxt = cell + dx + dy * w
                        if landings[nxt] < 0:
                            landings[nxt] = landings[cell]
                            following.append(nxt)
            frontier = following
        return landings

    def cell(self, x, y):
        return (int(limit(math.floor((y - self.y0) / 2 + 0.5), 0, self.h - 1)) * self.w
                + int(limit(math.floor((x - self.x0) / 2 + 0.5), 0, self.w - 1)))

    def point(self, cell):
        y, x = divmod(cell, self.w)
        return self.x0 + 2 * x, self.y0 + 2 * y

    def snap(self, pos):
        cell = self.cell(*pos[:2])
        if self.free[cell]:
            return cell
        y, x = divmod(cell, self.w)
        for ring in range(1, 21):
            best, best_score = None, INF
            for j in range(max(0, y - ring), min(self.h, y + ring + 1)):
                if abs(j - y) == ring:
                    columns = range(max(0, x - ring), min(self.w, x + ring + 1))
                else:
                    columns = (i for i in (x - ring, x + ring) if 0 <= i < self.w)
                for i in columns:
                    nxt = j * self.w + i
                    score = (i - x) ** 2 + (j - y) ** 2
                    if self.free[nxt] and score < best_score:
                        best, best_score = nxt, score
            if best is not None:
                return best
        return None

    def walkable(self, start, end):
        x, y = start[:2]
        dx, dy = end[0] - x, end[1] - y
        count = int(math.hypot(dx, dy)) + 1
        previous = self.cell(x, y)
        heights, free, cell = self.nav_height, self.free, self.cell
        dx, dy = dx / count, dy / count
        for s in range(1, count + 1):
            nxt = cell(x + dx * s, y + dy * s)
            if nxt != previous:
                if not free[nxt] or heights[nxt] > heights[previous] + 3.1:
                    return False
                previous = nxt
        return True

    def exposure(self, point, ceiling=INF):

        x, y = point
        left, right, bottom, top = self.left, self.right, self.bottom, self.top
        z = self.surface(x, y) + 7
        tops, slabs = self.raster_top, self.raster_slabs
        total = 0.0
        for dx, dy in EXPOSURE_HEADINGS:
            x_edge = ((right if dx > 0 else left) - x) / dx if dx else INF
            y_edge = ((top if dy > 0 else bottom) - y) / dy if dy else INF
            edge = max(1, min(80, math.floor(min(x_edge, y_edge) / 2.5) + 1))
            hit = edge
            if z <= self.raster_ceiling:
                sx, sy = dx * 2.5, dy * 2.5
                for i in range(1, edge):
                    idx = self.raster_cell(x + sx * i, y + sy * i)
                    if z < tops[idx] - 0.05 or any(a < z < b for a, b in slabs.get(idx, ())):
                        hit = i
                        break
            total += hit * 2.5
            if total >= ceiling * 4800:
                return INF
        return total / 4800


class Route:


    def __init__(self, arena, start, goal):
        self.arena, self.goal = arena, goal
        self.gy, self.gx = divmod(goal, arena.w)
        self.cost = {start: 0.0}
        self.parent = {start: None}
        self.closed = set()
        self.best, self.best_h = start, self.heuristic(start)
        self.heap = [(self.best_h, start)]
        self.pops = 0

    def heuristic(self, cell):
        y, x = divmod(cell, self.arena.w)
        dx, dy = abs(x - self.gx), abs(y - self.gy)
        return f32(1.15 * 2 * (max(dx, dy) + 0.4142 * min(dx, dy)))

    def push(self, key, cell):
        heap = self.heap
        idx = len(heap)
        heap.append((key, cell))
        while idx:
            parent = (idx - 1) // 2
            if key >= heap[parent][0]:
                break
            heap[idx] = heap[parent]
            idx = parent
        heap[idx] = key, cell

    def pop(self):
        heap = self.heap
        _, cell = heap[0]
        last = heap.pop()
        if heap:
            idx = 0
            child = 1
            while child < len(heap):
                if child + 1 < len(heap) and heap[child + 1][0] < heap[child][0]:
                    child += 1
                if last[0] <= heap[child][0]:
                    break
                heap[idx] = heap[child]
                idx = child
                child = idx * 2 + 1
            heap[idx] = last
        return cell

    def advance(self):
        arena, closed, costs = self.arena, self.closed, self.cost
        steps, offsets, clearance = arena.steps, arena.step_offsets, arena.clearance
        stop = min(self.pops + ROUTE_SLICE, 22000)
        while self.heap and self.pops < stop:
            cell = self.pop()
            self.pops += 1
            if cell in closed:
                continue
            if cell == self.goal:
                self.best = cell
                return True
            closed.add(cell)
            heur = self.heuristic(cell)
            if heur < self.best_h:
                self.best, self.best_h = cell, heur
            base = costs[cell]
            for delta, diagonal in offsets[steps[cell]]:
                nxt = cell + delta
                if nxt in closed:
                    continue
                cost = f32(base + (2.8284 if diagonal else 2) * (1 + 0.15 * max(0, 4 - clearance[nxt])))
                if cost < costs.get(nxt, INF):
                    costs[nxt] = cost
                    self.parent[nxt] = cell
                    self.push(f32(cost + self.heuristic(nxt)), nxt)
        return not self.heap or self.pops == 22000

    def path(self):
        path, cell = [], self.best
        while cell is not None:
            path.append(self.arena.point(cell))
            cell = self.parent[cell]
        return path[::-1]


@dataclass(slots=True)
class Track:
    id: int
    kind: str
    pos: tuple
    seen: float
    hp: float = 0.0
    max_hp: float = 0.0
    vel: tuple = ZERO3
    aim: tuple = ZERO
    cubes: int = 0
    weapons: tuple = ()
    charging: bool = False
    hit: float = -100.0
    closing: float = 0.0
    dist: float = 0.0
    radius: float = 0.0
    height: float = 0.0
    eye: float = 0.0
    clear: bool = False
    engaged: bool = False
    fresh: bool = True
    face_error: float = 0.0
    midpoint: tuple = ZERO3


@dataclass(slots=True)
class Weapon:
    kind: str
    stats: dict
    ammo: float
    reload: float
    charge: float
    cooldown: float

    def stat(self, key, default=0):
        return number(self.stats.get(key), default)


class Zone:
    def __init__(self):
        self.start = -1
        self.hold = (0, 0, 0)

    def update(self, raw, now):
        current = (*vector(raw.get("center"), 2), number(raw.get("radius")))
        self.next = (*vector(raw.get("next_center"), 2), number(raw.get("next_radius")))
        start = number(raw.get("shrink_start"))
        self.end = number(raw.get("shrink_end"))
        if self.start != start or now <= start:
            self.hold = current
        self.start, self.now = start, now
        self.current = (current if now <= start or abs(current[0] - self.hold[0]) > 0.01
                        or abs(current[2] - self.hold[2]) > 0.01 else self.circle(now))
        times = (start + (self.end - start) * i / 24 for i in range(25))
        self.schedule = tuple((when, self.circle(when)) for when in times)
        self.weight = limit(1 - (start - now) / 25, 0.1, 1)

    def circle(self, when):
        if when <= self.start or self.end <= self.start:
            return self.hold
        part = limit((when - self.start) / (self.end - self.start), 0, 1)
        return tuple(a + (b - a) * part for a, b in zip(self.hold, self.next))

    def deadline(self, point, pad):
        if distance(point, self.next) <= self.next[2] - pad:
            return INF
        for when, circle in self.schedule:
            if distance(point, circle) > circle[2] - pad:
                return when
        return self.end

    def goal(self, pos):
        x, y, radius = self.next
        if radius <= 30:
            return x, y
        span = distance(pos, self.next)
        inner = max(0, radius - limit(0.3 * radius, 3, 30) - 5)
        if span <= inner or span < 1:
            return pos[:2]
        return x + (pos[0] - x) * inner / span, y + (pos[1] - y) * inner / span

    def penalty(self, point):
        current = distance(point, self.current) - self.current[2] + 5
        following = distance(point, self.next) - self.next[2] + 5
        return ((150 + 5 * current if current > 0 else 0)
                + ((25 + 0.8 * following) * self.weight if following > 0 else 0))


class Practice:
    def __init__(self, hello, seed):
        self.slot = number(hello.get("slot"), -1)
        self.rng = RandomStream(seed or self.slot + 1)
        config = obj(hello.get("config"))
        self.mech = obj(config.get("mech"))
        self.npc = obj(config.get("npc"))
        self.crate_config = obj(config.get("crates"))
        self.cube_config = obj(config.get("cubes"))
        self.loot_config = obj(config.get("loot"))
        self.weapon_config = obj(config.get("weapons"))
        self.upgrades = {upgrade["id"]: upgrade.get("name")
                         for raw in seq(config.get("upgrades"))
                         if isinstance((upgrade := obj(raw)).get("id"), str)}
        self.map_dir = obj(hello.get("map")).get("dir")
        self.arena = None
        self.enemies, self.drones = {}, {}
        self.items = {key: {} for key in ("pickups", "cubes", "crates")}
        self.zone = Zone()
        self.kills = self.deficit_ticks = 0
        self.start_alive = None
        self.disqualified = self.squad = self.retreat = False
        self.incoming = self.last_threat = self.selected_at = -100.0
        self.incoming_bearing = self.drone_bearing = 0.0
        self.drone_hit = self.losing = 0.0
        self.selected = self.last_fire_target = None
        self.last_aim = ZERO
        self.loot_id, self.loot_since, self.blacklist = -1, 0.0, {}
        self.home = self.home_search = None
        self.home_at = -INF
        self.cover_goal, self.cover_at = None, -INF
        self.strafe_side, self.strafe_until = 1, 0.0
        self.stuck_since = self.unstuck_until = 0.0
        self.unstuck = ZERO
        self.search = self.route_goal = None
        self.route_at = -INF
        self.path, self.waypoint = (), 0
        self.escape_plan = self.escape_search = None
        self.escape_at = -INF
        self.escape_jumping = False
        self.mode = "start"
        self.work_limits = 0

    def load_map(self):
        directory = self.map_dir if isinstance(self.map_dir, str) and len(self.map_dir) < 2048 else None
        try:
            self.arena = PracticeMap(directory)
        except (ValueError, TypeError, LookupError, ArithmeticError, AttributeError):
            self.arena = PracticeMap(world=FLAT_WORLD)

    def prepare(self, obs):
        me = obj(obs.get("self"))
        self.now = number(obs.get("t"))
        self.pos, self.vel = vector(me.get("pos"), 3), vector(me.get("vel"), 3)
        self.actual = vector(me.get("aim"), 2)
        self.hp, max_hp = number(me.get("hp")), number(me.get("max_hp"))
        self.hp_share = self.hp / max(1, max_hp)
        self.energy = number(me.get("energy"))
        self.max_energy = number(me.get("max_energy"))
        self.grounded = me.get("grounded") is True
        self.in_zone = me.get("in_zone") is True
        self.cubes = number(me.get("cubes"))
        self.cube_cap = number(self.cube_config.get("stat_cap"), 10)
        self.alive = number(obs.get("alive"))
        stats = obj(me.get("stats"))
        if not number(stats.get("radius")):
            stats = self.mech
        self.radius = number(stats.get("radius"), 2.5)
        self.height = number(stats.get("height"), 9)
        self.muzzle_height = number(stats.get("muzzle_height"), 7)
        self.muzzle = raised(self.pos, self.muzzle_height)
        self.eye = raised(self.pos, number(stats.get("eye_height"), 8))
        self.walk_speed = max(1e-6, number(stats.get("walk_speed"), 11.7))
        self.yaw_slew = 0.05 * number(stats.get("turn_rate"), 4)
        self.pitch_slew = 0.05 * number(stats.get("pitch_rate"), 3)
        self.min_pitch = number(stats.get("min_pitch"), -0.7)
        self.max_pitch = number(stats.get("max_pitch"), 1.3)
        self.raw_slots = seq(me.get("weapons"))
        self.slots = [self.weapon(raw) for raw in self.raw_slots[:2]]
        self.slots.extend([None] * (2 - len(self.slots)))
        self.gun, self.laser, self.lightning = (next((w for w in self.slots if w and w.kind == kind), None)
                                               for kind in ("gun", "laser", "lightning"))
        self.zone.update(obj(obs.get("zone")), self.now)
        self.zone_goal = self.zone.goal(self.pos)
        self.zone_span = distance(self.pos, self.zone_goal)
        self.zone_arrival = self.now + 1.45 * self.zone_span / self.walk_speed + 4
        self.zone_deadline = self.zone.deadline(self.pos, 8)
        self.late = self.zone.next[2] <= 70 or self.alive <= 3
        self.projectiles = [(raw.get("kind"), vector(raw.get("pos"), 3), vector(raw.get("vel"), 3))
                            for item in seq(obs.get("projectiles")) if (raw := obj(item))]
        self.drops = [vector(raw.get("pos"), 3) for item in seq(obs.get("drops")) if (raw := obj(item))]
        if self.start_alive is None:
            self.start_alive = self.alive

    def weapon(self, raw):
        w = obj(raw)
        kind = w.get("kind")
        if not isinstance(kind, str):
            return None
        stats = obj(w.get("stats")) or obj(self.weapon_config.get(kind))
        return Weapon(kind, stats, number(w.get("ammo")), number(w.get("reload")),
                      number(w.get("charge")), number(w.get("cooldown")))

    def refresh(self, obs):
        now, own = self.now, self.pos
        arena = self.arena
        clear = arena.clear_ray
        for table in (self.enemies, self.drones):
            for track in table.values():
                track.fresh = track.engaged = False
                if table is self.enemies:
                    track.clear = False
        base_radius = number(self.mech.get("radius"), 2.5)
        base_height = number(self.mech.get("height"), 9)
        base_eye = number(self.mech.get("eye_height"), 8)
        npc_radius = number(self.npc.get("radius"), 1.8)
        npc_height = number(self.npc.get("height"), 3.5)
        size_per_cube = number(self.cube_config.get("size_per_cube"), 0.05)
        for item in seq(obs.get("mechs")):
            raw = obj(item)
            kind = raw.get("kind")
            ident = number(raw.get("id"))
            if kind not in ("mech", "npc") or ident == self.slot:
                continue
            table = self.enemies if kind == "mech" else self.drones
            pos, vel, aim = vector(raw.get("pos"), 3), vector(raw.get("vel"), 3), vector(raw.get("aim"), 2)
            cubes = number(raw.get("cubes"))
            if kind == "mech":
                scale = 1 + size_per_cube * cubes
                radius, height, eye = base_radius * scale, base_height * scale, base_eye * scale
            else:
                radius, height, eye = npc_radius, npc_height, 0
            dx, dy = pos[0] - own[0], pos[1] - own[1]
            span = math.hypot(dx, dy)
            previous = table.get(ident)
            closing = (-(dx * (vel[0] - self.vel[0]) + dy * (vel[1] - self.vel[1])) / span
                       if span > 1 else previous.closing if previous else 0)
            midpoint = raised(pos, height * 0.5)
            visible = clear(self.muzzle, midpoint) or kind == "mech" and clear(self.muzzle, raised(pos, height * 0.85))
            table[ident] = Track(ident, kind, pos, now, number(raw.get("hp")), number(raw.get("max_hp")),
                                 vel, aim, cubes, tuple(seq(raw.get("weapons"))), raw.get("charging") is True,
                                 previous.hit if previous else -100, closing, span, radius, height, eye, visible,
                                 face_error=abs(angle(aim[0] - math.atan2(-dy, -dx))), midpoint=midpoint)
        for table, expiry in ((self.enemies, 20), (self.drones, 120)):
            for ident in [ident for ident, track in table.items() if now - track.seen > expiry]:
                del table[ident]
        for item in seq(obs.get("events")):
            event = obj(item)
            kind = event.get("type")
            if kind == "damaged":
                by = number(event.get("by"), None)
                yaw = number(event.get("bearing"), None)
                if by is not None:
                    self.incoming = now
                    if yaw is not None:
                        self.incoming_bearing = yaw
                    for table in (self.enemies, self.drones):
                        if by in table:
                            table[by].hit = now
                if event.get("weapon") == "npc" and yaw is not None:
                    self.drone_hit, self.drone_bearing = now, yaw
            elif kind == "kill":
                self.kills += 1
                self.enemies.pop(number(event.get("target")), None)
        if self.start_alive - self.alive - self.kills > 0:
            self.deficit_ticks += 1
            if self.deficit_ticks >= 5:
                self.disqualified = True
        else:
            self.deficit_ticks = 0
        self.squad = now > 20 and not self.disqualified
        self.awareness = [e for e in self.enemies.values() if now - e.seen <= 2.5]
        self.threat_eyes = [(e.id, raised(e.pos, e.eye)) for e in self.awareness]
        for kind, table in self.items.items():
            seen = set()
            for item in seq(obs.get(kind)):
                raw = obj(item)
                if not raw:
                    continue
                ident, pos = number(raw.get("id")), vector(raw.get("pos"), 3)
                seen.add(ident)
                table[ident] = Track(ident, raw.get("kind", kind), pos, now, hp=number(raw.get("hp")),
                                     dist=distance(own, pos))
            for ident, item in tuple(table.items()):
                if ident in seen:
                    continue
                item.dist = distance(own, item.pos)
                if now - item.seen > 0.35 and item.dist < 40 and clear(self.eye, raised(item.pos, 1.5)):
                    del table[ident]

    def targets(self):
        shot, blocked = None, None
        score_best, blocked_best = INF, 240 if self.squad else 215
        cap = blocked_best
        danger, crowd, nearby = False, 0, 0
        for e in self.awareness:
            hit_age = self.now - e.hit
            danger |= hit_age < 4
            if not e.fresh:
                continue
            d = e.dist
            nearby += d < 160
            aimed = e.face_error < 0.22
            if self.squad:
                e.engaged = (d < 60 or hit_age < 6 or self.late or e.closing > 3 and d < 180
                             or e.hp < 0.4 * e.max_hp and d < 160 or aimed and d < 190)
            else:
                e.engaged = (d < 60 or hit_age < 4 or aimed and e.charging and d < 120
                             or e.hp < 350 and d < 120 or self.alive <= 2)
            danger |= e.engaged
            crowd += e.engaged or e.clear and d < 150
            if not e.engaged:
                continue
            if e.clear and d <= cap:
                value = d + (0.2 if self.squad else 60 / 1400) * e.hp
                value -= 40 * (hit_age < 4) + 15 * (e.closing > 3)
                if self.squad:
                    value -= 100 * (e.hp <= 0.3 * e.max_hp)
                    value -= 120 * (e.id == self.selected and self.now - self.selected_at < 2)
                if value < score_best:
                    shot, score_best = e, value
            elif not e.clear and d < blocked_best:
                blocked, blocked_best = e, d
        if shot:
            self.selected, self.selected_at = shot.id, self.now
        if blocked and self.squad and blocked.hp >= 1.01 * blocked.max_hp:
            blocked = None
        self.danger, self.crowd = danger, crowd
        if danger or self.now - self.incoming < 3:
            self.last_threat = self.now
        self.update_retreat(shot, nearby)
        return shot, blocked

    def update_retreat(self, shot, nearby):
        hp, crowd, now = self.hp_share, self.crowd, self.now
        swamped = (crowd >= 3 or crowd == 2 and hp < 0.65
                   or shot and "laser" in shot.weapons and shot.dist > 55 and not self.laser and hp < 0.80)
        if not self.retreat and (swamped or hp < 0.38 and now - self.last_threat < 2):
            self.retreat, self.cover_at = True, -1
        elif self.retreat and not swamped and (hp > 0.80 or hp > 0.55 and now - self.last_threat > 7):
            self.retreat = False
        if self.squad:
            losing = nearby >= 2 and hp < 0.55 or nearby >= 3 and hp < 0.80
            if shot:
                theirs = shot.hp / max(1, shot.max_hp)
                losing |= hp < 0.35 and theirs - hp > 0.10
                if theirs < 0.25 and hp > 0.20 and nearby <= 2:
                    losing = False
            if losing:
                self.losing = now
            self.retreat = self.losing > 0 and now - self.losing < 1.5

    def pick(self, obs, action):
        choices = seq(obj(obs.get("offer")).get("choices"))[:3]
        if choices:
            ranking = (SQUAD_UPGRADES if self.squad else OPEN_UPGRADES) + END_UPGRADES
            rank = {name: i for i, name in enumerate(ranking)}
            names = (self.upgrades.get(ident) if isinstance(ident := obj(choice).get("id"), str) else None
                     for choice in choices)
            action["pick"] = min(enumerate(names), key=lambda pair: rank.get(pair[1], INF))[0]

    def wants(self, kind):
        if kind == "gun":
            return bool(self.raw_slots) and self.raw_slots[0] is None and not self.gun
        if not isinstance(kind, str) or kind in ("mortar", "gun"):
            return False
        secondary = self.slots[1]
        return (all(w is None or w.kind != kind for w in self.slots)
                and RANK.get(kind, 0) > (RANK.get(secondary.kind, 0) if secondary else 0))

    def take(self, obs, action):
        reach = number(self.loot_config.get("pickup_radius"), 4) - 0.3
        for item in seq(obs.get("pickups")):
            raw = obj(item)
            if not self.wants(raw.get("kind")):
                continue
            pos = vector(raw.get("pos"), 3)
            if distance(self.pos, pos) > reach or abs(self.pos[2] - pos[2]) > 3.6:
                continue
            secondary = self.slots[1]
            if secondary and secondary.kind == "laser" and secondary.charge > 0:
                break
            ident = number(raw.get("id"))
            if ident >= 0 and ident == int(ident):
                action["take"] = int(ident)
                if all(self.slots):
                    action["drop"] = 1
            break

    def select_loot(self):
        phase_radius = 150 if self.squad else 90
        farming = (not self.danger and self.hp_share > (0.50 if self.squad else 0.70)
                   and self.now < (1e9 if self.squad else 150))
        cube_value = 75 if self.cubes < self.cube_cap else 25
        arena, now, zone = self.arena, self.now, self.zone
        best, score = None, 0.0
        groups = (self.items["pickups"], self.items["cubes"], self.items["crates"], self.drones)
        for category, table in enumerate(groups):
            if category >= 2 and not farming:
                break
            for item in table.values():
                span = distance(self.pos, item.pos)
                if category == 0:
                    if not self.wants(item.kind):
                        continue
                    laser = self.squad and item.kind == "laser"
                    radius = 240 if laser else phase_radius
                    value = 150 if laser else 130 if len(self.raw_slots) > 1 and self.raw_slots[1] is None else 60
                elif category == 1:
                    radius, value = (105 if self.squad else 63), cube_value
                elif category == 2:
                    radius, value = phase_radius, 0.6 * cube_value
                else:
                    if self.cubes >= self.cube_cap or now - item.seen >= 12:
                        continue
                    radius, value = phase_radius, 85
                if span >= radius or span > 260 or self.blacklist.get(item.id, -INF) > now:
                    continue
                utility = value / (span + 18) * (1.35 if item.id == self.loot_id else 1)
                if utility <= score or distance(item.pos, zone.current) > zone.current[2] - 6:
                    continue
                if (zone.deadline(item.pos, 6) < now + 1.4 * span / self.walk_speed + 5
                        or item.pos[2] > arena.bare(*item.pos[:2]) + 3.2):
                    continue
                cell = arena.snap(item.pos)
                if cell is not None and arena.main[cell]:
                    best, score = (category, item, span), utility
        if best is None:
            self.loot_id = -1
        elif best[1].id != self.loot_id:
            self.loot_id, self.loot_since = best[1].id, now
        elif now - self.loot_since > 30:
            self.blacklist[self.loot_id] = now + 60
            self.loot_id = -1
            return None
        return best

    def reached_work_limit(self, rays, limit=MOVEMENT_RAYS):
        if self.work_rays + rays <= limit:
            return False
        self.work_limits += 1
        return True

    def movement_ray(self, start, end):
        self.work_rays += 1
        return self.arena.clear_ray(start, end)

    def travel(self, goal):
        arena, pos = self.arena, self.pos
        span = distance(pos, goal)
        direct = unit(pos, goal)
        if span < 0.8:
            return ZERO
        if arena.above_obstacle(pos) or span < 45 and arena.walkable(pos, goal):
            return direct
        if (self.route_goal is None or self.now - self.route_at > 2.5
                or distance(self.route_goal, goal) > 5):
            start, end = arena.snap(pos), arena.snap(goal)
            self.route_goal, self.route_at = goal, self.now
            self.path, self.waypoint = (), 0
            self.search = Route(arena, start, end) if start is not None and end is not None else None
        if self.search:
            if self.search.advance():
                self.path = self.search.path()
                self.search = None
                self.waypoint = 0
            else:
                self.work_limits += 1
                self.path = self.search.path()
                self.waypoint = 0
        path = self.path
        if not path:
            return direct
        first = self.waypoint
        nearest = min(range(first, min(first + 10, len(path))), key=lambda i: distance(pos, path[i]))
        if distance(pos, path[nearest]) > 12:
            self.path, self.search, self.route_goal = (), None, None
            return direct
        self.waypoint = nearest
        last = len(path) - 1
        if nearest == last and self.search is not None:
            return unit(pos, path[last]) if distance(pos, path[last]) >= 0.8 else direct
        for i in range(min(nearest + 14, last), nearest, -1):
            waypoint = path[i]
            if arena.walkable(pos, waypoint):
                if i == last and distance(waypoint, goal) < 4 and arena.walkable(pos, goal):
                    return direct
                return unit(pos, waypoint)
        return unit(pos, path[nearest + 1]) if nearest < last else direct

    def new_escape(self, start):
        arena = self.arena
        if start is None or arena.landing_cell is None:
            return None
        if self.escape_search is None or self.escape_search[0] != start:
            self.escape_search = start, deque([(start, 0)]), {start}, None, INF, 0
        _, queue, seen, pair, score, visits = self.escape_search
        stop = min(visits + ESCAPE_SLICE, 60000)
        while queue and visits < stop:
            cell, n = queue.popleft()
            visits += 1
            if 2 * n >= score:
                queue.clear()
                break
            dest = arena.landing_cell[cell]
            if dest >= 0:
                launch, land = arena.point(cell), arena.point(dest)
                span = distance(launch, land)
                value = 2 * n + 4 * span
                if value < score:
                    if span > 0.1:
                        beyond = offset(land, unit(launch, land), 5)
                        if arena.inside(*beyond) and arena.main[arena.cell(*beyond)]:
                            land = beyond
                    pair, score = (launch, land), value
            for delta, _ in arena.step_offsets[arena.steps[cell]]:
                nxt = cell + delta
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, n + 1))
        if queue and visits < 60000:
            self.work_limits += 1
            self.escape_search = start, queue, seen, pair, score, visits
            return pair
        self.escape_search = None
        self.escape_at = self.now
        return pair

    def escape(self):
        arena, pos = self.arena, self.pos
        if self.grounded:
            self.escape_jumping = False
            start = arena.snap(pos)
            if start is not None and arena.main[start] or arena.above_obstacle(pos):
                self.escape_plan, self.escape_search = None, None
                return None
            if (self.escape_plan is None or self.escape_search is not None
                    or self.now - self.escape_at > 6):
                self.escape_plan = self.new_escape(start)
            if self.escape_plan is None:
                return (ZERO, False, False) if self.escape_search is not None else None
            launch, _ = self.escape_plan
            if distance(pos, launch) > 2.5:
                return self.travel(launch), False, False
            self.escape_jumping = self.energy >= min(70, 0.7 * self.max_energy)
            return ZERO, False, self.escape_jumping
        if not self.escape_jumping or self.escape_plan is None:
            return None
        land = self.escape_plan[1]
        span = distance(pos, land)
        if span < 1.5:
            return ZERO, False, False
        move = unit(pos, land)
        level = max(arena.surface(*offset(pos, move, n), decks=False) for n in range(int(min(30, span)) + 1))
        return move, pos[2] < level + 2.5 and self.energy > 1, False

    def cover(self, threats):
        arena, pos = self.arena, self.pos
        threats = [(span, eye) for _, eye in threats if (span := distance(pos, eye)) < 230]
        if not threats:
            return None
        if self.cover_goal is not None and self.now - self.cover_at < 0.4:
            return self.cover_move(self.cover_goal)
        if len(threats) > 4:
            threats = sorted(threats, key=lambda row: row[0])[:4]
        eyes = [eye for _, eye in threats]
        clear = self.movement_ray
        cover_rays = min(MOVEMENT_RAYS - 24, self.work_rays + COVER_RAYS)

        def covered(point):
            x, y = point
            z = arena.surface(x, y)
            full, half = (x, y, z + self.height), (x, y, z + self.height * 0.5)
            return not any(clear(eye, full) or clear(eye, half) for eye in eyes)

        if self.zone.penalty(pos) == 0 and covered(pos[:2]):
            self.cover_goal, self.cover_at = pos[:2], self.now
            return ZERO
        start = arena.snap(pos)
        if start is None:
            return None
        queue, seen = deque([(start, 0)]), {start}
        best, score, checked = None, INF, 0
        while queue:
            cell, n = queue.popleft()
            if n > 50 or 2 * n > score + 30:
                break
            y, x = divmod(cell, arena.w)
            if n and (x + y) % 2 == 0:
                if checked >= COVER_CELLS:
                    self.work_limits += 1
                    break
                if self.reached_work_limit(2 * len(eyes), cover_rays):
                    break
                checked += 1
                point = arena.point(cell)
                close = min(80, min(distance(point, eye) for eye in eyes))
                value = 2 * n + self.zone.penalty(point) - 0.25 * close
                if value < score and covered(point):
                    best, score = point, value
            for delta, _ in arena.step_offsets[arena.steps[cell]]:
                nxt = cell + delta
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, n + 1))
        if best is None:
            return None
        self.cover_goal, self.cover_at = best, self.now
        return self.cover_move(best)

    def cover_move(self, goal):
        return ZERO if distance(self.pos, goal) < 1.5 else self.travel(goal)

    def nearest_cube(self, radius, vertical=INF):
        return min((item for item in self.items["cubes"].values()
                    if item.dist < radius and abs(item.pos[2] - self.pos[2]) < vertical),
                   key=lambda item: item.dist, default=None)

    def preferred(self, foe, finish=False):
        if foe.kind == "npc":
            return 58
        if finish:
            goal = 14
        elif self.lightning and self.energy > 12:
            goal = 28
        else:
            goal = 120 if self.squad and self.laser else 85
        if not self.lightning:
            if "lightning" in foe.weapons:
                goal = max(goal, 64)
            if "mortar" in foe.weapons:
                goal = max(goal, 80)
        return goal

    def sight_preference(self, foe):
        gun, laser, lightning = self.gun, self.laser, self.lightning
        d = foe.dist
        laser_ready = (laser and laser.charge >= laser.stat("charge", 0.75) - 0.3
                       and d <= laser.stat("range", 280) - 5)
        if self.squad and (laser or lightning):
            return 1
        if not self.squad and not laser_ready and foe.fresh and foe.charging and foe.face_error < 0.3:
            return -1.6
        if (laser_ready or gun and gun.ammo > 0 and gun.reload <= 0.25 and d <= gun.stat("range", 230) - 10
                or lightning and d <= lightning.stat("range", 45) + 6
                and self.energy >= 3 * lightning.stat("energy", 3)):
            return 1
        return -1

    def fight(self, foe, preferred, sight):
        arena, pos = self.arena, self.pos
        if self.now >= self.strafe_until:
            if self.rng.random() < 0.6:
                self.strafe_side *= -1
            self.strafe_until = self.now + 0.3 + 0.7 * self.rng.random()
        scale = self.strafe_side / (distance(pos, foe.pos) + 1e-9)
        sx, sy = (pos[1] - foe.pos[1]) * scale, (foe.pos[0] - pos[0]) * scale
        turn_next = False
        cube = self.nearest_cube(40, 4)
        clear = self.movement_ray
        wanted = sight > 0
        candidates = []
        directions = SQUAD_STEPS if self.squad else OPEN_STEPS
        for i, (direction, span) in enumerate(directions):
            dot = direction[0] * sx + direction[1] * sy
            point = offset(pos, direction, span)
            cell = arena.cell(*point)
            if span and (not arena.free[cell] or not arena.walkable(pos, point)):
                turn_next |= span == 6 and dot > 0.9
                continue
            score = -1.1 * abs(distance(point, foe.pos) - preferred) - 0.4 * span - self.zone.penalty(point)
            if cube:
                score += 1.5 * (cube.dist - distance(point, cube.pos))
            score -= 2.5 * max(0, 4 - arena.clearance[cell])
            score += (9 * dot if wanted else 0) if span else -8
            probe = span == 6 and not self.squad
            upper = score + (45 * sight if wanted else 0) + (8 if probe else 0)
            if not span and not wanted:
                upper += 14
            candidates.append((upper, i, score, direction, point, span, probe))
        candidates.sort(key=lambda c: -c[0])
        best, best_score, best_index = ZERO, -INF, INF
        threat_eyes = [eye for ident, eye in self.threat_eyes if ident != foe.id and distance(pos, eye) <= 182]

        def loses(score, i):
            return score < best_score or score == best_score and i >= best_index

        ray_reserve = 1 + len(threat_eyes)
        for upper, i, score, direction, point, span, probe in candidates:
            if loses(upper, i) or best_index < INF and self.reached_work_limit(ray_reserve + 8 * probe):
                break
            z = arena.surface(*point)
            sightline = clear((*point, z + self.muzzle_height), foe.midpoint)
            if sightline:
                score += 45 * sight
            elif not span and not wanted:
                score += 14
            extra = probe and sightline == wanted
            ceiling = 8 if extra else 0
            if loses(score + ceiling, i):
                continue
            body = (*point, z + 0.6 * self.height)
            for eye in threat_eyes:
                if distance(point, eye) <= 170 and clear(eye, body):
                    score -= 30
                    if loses(score + ceiling, i):
                        break
            if loses(score + ceiling, i):
                continue
            if extra:
                for direction2 in HEADINGS[::2]:
                    alternative = offset(point, direction2, 7)
                    if arena.free[arena.cell(*alternative)]:
                        elevation = arena.surface(*alternative) + self.muzzle_height
                        if clear((*alternative, elevation), foe.midpoint) != sightline:
                            score += 8
                            break
            if not loses(score, i):
                best, best_score, best_index = direction, score, i
        if turn_next:
            self.strafe_side *= -1
            self.strafe_until = self.now + 0.5
        return best

    def shell_dodge(self):
        arena, pos = self.arena, self.pos
        mortar = obj(self.weapon_config.get("mortar"))
        gravity = number(mortar.get("gravity"), 22)
        gravity = gravity if gravity > 0 else 22
        reach = number(mortar.get("splash_radius"), 7) + self.radius + 2
        remaining = SHELL_STEPS
        for kind, origin, velocity in self.projectiles:
            if kind != "mortar":
                continue
            x, y, z = origin
            vx, vy, vz = velocity
            dx, dy = vx * 0.05, vy * 0.05

            if distance(origin, pos) > 2.5 * math.hypot(vx, vy) + reach:
                continue
            for _ in range(min(50, remaining)):
                remaining -= 1
                x, y, z = x + dx, y + dy, z + vz * 0.05
                vz -= gravity * 0.05
                if not arena.solid((x, y, z)):
                    continue
                span = distance(pos, (x, y))
                if span < reach:
                    away = math.atan2(vx, -vy) if span < 0.5 else math.atan2(pos[1] - y, pos[0] - x)
                    for turn in (0, 0.7, -0.7, 1.4, -1.4):
                        move = heading(away + turn)
                        if arena.walkable(pos, offset(pos, move, 6)):
                            return move
                break
            if remaining == 0:
                self.work_limits += 1
                break
        return None

    def dodge(self, move, boost):
        bx, by, bz = raised(self.pos, self.height * 0.56)
        x, y = ZERO
        for kind, (px, py, pz), (vx, vy, vz) in self.projectiles:
            if kind == "mortar":
                continue
            speed_sq = vx * vx + vy * vy + vz * vz
            xy = math.hypot(vx, vy)
            if speed_sq < 1 or xy < 1:
                continue
            dx, dy, dz = px - bx, py - by, pz - bz
            future = -(dx * vx + dy * vy + dz * vz) / speed_sq
            if 0 < future <= 0.7 and math.hypot(dx + vx * future, dy + vy * future) < self.radius + 1.1:
                sign = -1 if -vy * dx + vx * dy > 0 else 1
                x -= sign * vy / xy
                y += sign * vx / xy
        laser = False
        for foe in self.awareness:
            if foe.fresh and foe.charging and foe.face_error <= 0.15:
                perpendicular = bearing(foe.pos, self.pos) + self.strafe_side * math.pi / 2
                x += 1.5 * math.cos(perpendicular)
                y += 1.5 * math.sin(perpendicular)
                laser = True
        norm = math.hypot(x, y)
        if norm > 0.01:
            x, y = 0.4 * move[0] + 0.9 * x / norm, 0.4 * move[1] + 0.9 * y / norm
            cap = max(1, math.hypot(x, y))
            move = x / cap, y / cap
        return move, boost or laser and self.energy > 25

    def home_point(self):
        now, zone, arena = self.now, self.zone.next, self.arena
        outside = self.home is None or distance(self.home, zone) > 0.8 * zone[2]
        if self.home_search is None and (outside or now - self.home_at > 12):
            sightings = [e.pos for e in self.enemies.values() if now - e.seen < 20]

            def base(point):
                crowd = sum(max(0, 1 - distance(point, other) / 80) for other in sightings)
                crowd += sum(max(0, 1 - distance(point, other) / 60) for other in self.drops)
                return (0.25 * distance(self.pos, point) + 40 * crowd
                        + 10 * distance(point, zone) / max(30, zone[2]))

            samples = []
            for i in range(40):
                point = offset(zone, heading(math.tau * self.rng.random()), 0.7 * zone[2] * math.sqrt(self.rng.random()))
                if arena.inside(*point) and arena.main[arena.cell(*point)]:
                    samples.append((base(point), i, point))
            samples.sort(reverse=True)
            incumbent = None if outside else (self.home, base(self.home))
            self.home_search = (zone, samples, None, INF, INF, incumbent)
            self.home_at = now
        if self.home_search is None:
            return self.home
        origin, samples, winner, score, index, incumbent = self.home_search
        if origin != zone:
            self.home_search = None
            return self.home
        for _ in range(HOME_SAMPLES):
            if not samples or samples[-1][0] > score:
                break
            value, i, point = samples.pop()
            value += 120 * arena.exposure(point, (score - value) / 120 if i >= index else INF)
            if value < score or value == score and i < index:
                winner, score, index = point, value, i
        if samples and samples[-1][0] <= score:
            self.work_limits += 1
            self.home_search = (origin, samples, winner, score, index, incumbent)
            return self.home if self.home is not None else winner
        if winner is not None:
            if incumbent is None:
                self.home = winner
            else:
                point, value = incumbent
                if value + 120 * arena.exposure(point) > score + 15:
                    self.home = winner
        self.home_search = None
        return self.home

    def movement(self, shot, blocked):
        plan = self.escape()
        if plan is not None:
            return "escape", *plan, None
        if self.now < self.unstuck_until:
            return "unstuck", self.unstuck, False, False, None
        if (dodge := self.shell_dodge()) is not None:
            return "shell", dodge, self.energy > 15, False, None
        if self.zone_span > 2 and (not self.in_zone or self.zone_arrival + 3 >= self.zone_deadline):
            return ("urgent-zone", self.travel(self.zone_goal),
                    self.energy > 5 and (not self.in_zone or self.zone_arrival >= self.zone_deadline), False, None)
        finish = shot and shot.dist < 120 and (shot.hp < 200 or shot.hp < self.hp * 0.5)
        if self.retreat and not finish and not self.late:
            if (move := self.cover(self.threat_eyes)) is not None:
                return "retreat", move, self.energy > 10, False, None
            if shot:
                move = self.fight(shot, self.preferred(shot), 1)
            else:
                move = self.travel(self.zone_goal)
                if move == ZERO and self.drone_hit > 0 and self.now - self.drone_hit < 3:
                    turn = math.pi / 2 if self.now % 3 <= 1.5 else -math.pi / 2
                    move = heading(self.drone_bearing + turn)
            return "retreat", move, False, False, None
        if not self.squad and not shot and not self.late and self.now - self.incoming < 2.5:
            sight = (*offset(self.pos, heading(self.incoming_bearing), 80),
                     self.pos[2] + number(self.mech.get("eye_height"), 8))
            if (move := self.cover([(None, sight), *self.threat_eyes])) is not None:
                return "hide", move, self.energy > 30, False, None
        if (foe := shot or blocked) is not None:
            close = self.squad and foe.hp < 0.38 * foe.max_hp and self.hp_share > 0.42 and self.crowd <= 2
            sight = self.sight_preference(foe)
            move = self.fight(foe, self.preferred(foe, close), sight)
            if self.squad and (cube := self.nearest_cube(70 if self.hp_share > 0.50 else 39.9)):
                move = self.travel(cube.pos)
            return "fight", move, bool(self.lightning and foe.dist > 50 and self.energy > 55 and sight > 0), False, None
        if self.zone_span > 2 and self.zone_arrival + 14 >= self.zone_deadline:
            return "advisory-zone", self.travel(self.zone_goal), False, False, None
        loot = self.select_loot()
        if loot:
            category, item, span = loot
            if (category == 2 and span < 50
                    and self.arena.clear_ray(self.muzzle, raised(item.pos, number(self.crate_config.get("height"), 2.4) * 0.5))):
                move = ((self.pos[0] - item.pos[0]) / max(0.1, span),
                        (self.pos[1] - item.pos[1]) / max(0.1, span)) if span < 12 else ZERO
                item.dist = span
                return "crate", move, False, False, item
            if category == 3 and self.now - item.seen < 1 and item.clear and item.dist < 75:
                return "drone", self.fight(item, 58, 1), False, False, item
            return "loot", self.travel(item.pos), False, False, None
        if self.zone_span > 3 and (self.squad or self.zone.next[2] <= 30):
            return "zone", self.travel(self.zone_goal), False, False, None
        if not self.squad and (home := self.home_point()) is not None and distance(self.pos, home) > 3:
            move = self.travel(home)
            speed = min(1, 4.6 / self.walk_speed) if not self.danger and self.now - self.incoming > 6 else 1
            return "home", (move[0] * speed, move[1] * speed), False, False, None
        return "idle", ZERO, False, False, None

    def stuck(self, move, jump, escaping):
        if escaping or move == ZERO or not self.grounded or math.hypot(*self.vel[:2]) >= 1.2:
            self.stuck_since = -1
        elif self.stuck_since < 0:
            self.stuck_since = self.now
        elif self.now - self.stuck_since > 0.7:
            self.unstuck = heading(math.tau * self.rng.random())
            self.unstuck_until = self.now + 0.5
            self.search, self.route_goal, self.path = None, None, ()
            self.stuck_since = -1
            return True
        return jump

    def defensive_drone(self):
        now = self.now
        if self.drone_hit <= 0 or now - self.drone_hit >= 3:
            return None
        best, score = None, 0.7
        for drone in self.drones.values():
            if now - drone.seen > 0.5 or not drone.clear or drone.dist > 150:
                continue
            value = abs(angle(bearing(self.pos, drone.pos) - self.drone_bearing))
            if value < 0.7 and now - drone.hit < 3:
                value = 0
            if value < score:
                best, score = drone, value
        return best

    def scan(self, move):
        close = min((e for e in self.awareness if e.engaged or self.now - e.hit < 6),
                    key=lambda e: e.dist, default=None)
        if close is not None:
            return bearing(self.pos, close.pos), 0
        if self.drone_hit > 0 and self.now - self.drone_hit < 2.5:
            return self.drone_bearing, 0
        if self.now - self.incoming < 2.5:
            return self.incoming_bearing, 0
        if move != ZERO:
            return math.atan2(move[1], move[0]) + 1.15 * math.sin(1.3 * self.now), 0
        return self.actual[0] + 0.35, 0

    def gun_aim(self, origin, point, velocity):
        vx, vy, vz = velocity
        vz = vz * 0.5 if abs(vz) >= 0.5 else 0
        speed = self.gun.stat("speed", 252)
        speed = speed if speed > 0 else 252
        flight = 0
        for _ in range(4):
            travel = 0.075 + flight
            prediction = point[0] + vx * travel, point[1] + vy * travel, point[2] + vz * travel
            flight = max(0, math.dist(origin, prediction) - 3) / speed
        return aim_from(origin, prediction)

    def mortar_aim(self, origin, point, velocity, weapon):
        speed, gravity = weapon.stat("speed"), weapon.stat("gravity")
        if speed <= 0 or gravity <= 0:
            return None
        x, y = origin[:2]
        z = self.pos[2] + self.height + 0.5
        height = point[2] - z
        flight = 0
        for _ in range(3):
            travel = 0.075 + flight
            dx = point[0] + velocity[0] * travel - x
            dy = point[1] + velocity[1] * travel - y
            span = math.hypot(dx, dy)
            discriminant = speed**4 - gravity * (gravity * span**2 + 2 * height * speed**2)
            if span < 1 or discriminant < 0:
                return None
            pitch = math.atan2(speed**2 - math.sqrt(discriminant), gravity * span)
            horizontal = speed * math.cos(pitch)
            flight = span / horizontal
        if not self.min_pitch <= pitch <= self.max_pitch:
            return None
        yaw = math.atan2(dy, dx)
        vx, vy, vz = horizontal * dx / span, horizontal * dy / span, speed * math.sin(pitch)
        for step in range(1, math.ceil(9 * flight)):
            t = step * 0.1
            if self.arena.solid((x + vx * t, y + vy * t, z + vz * t - 0.5 * gravity * t * t)):
                return None
        return yaw, pitch

    def fire(self, action, move, shot, blocked, farm):
        defense = self.defensive_drone() if shot is None else None
        target = shot or defense or (farm if not self.retreat and self.hp_share >= 0.5 else None)
        self.last_fire_target = target.id if target else None
        triggers = [False, False]
        aim = self.scan(move) if target is None else None
        can_gun = False
        if target:
            origin = (self.muzzle[0] + self.vel[0] * 0.075, self.muzzle[1] + self.vel[1] * 0.075, self.muzzle[2])
            d = target.dist
            if target.kind == "mech":
                point = target.midpoint
                if not self.arena.clear_ray(origin, point):
                    point = raised(target.pos, target.height * 0.85)
                radius, height = target.radius, target.height
            elif target.kind == "npc":
                point, radius, height = target.midpoint, target.radius, target.height
            else:
                radius = number(self.crate_config.get("radius"), 1.4)
                height = number(self.crate_config.get("height"), 2.4)
                point = raised(target.pos, height * 0.5)
            velocity = target.vel
            instant = aim_from(origin, (point[0] + 0.125 * velocity[0], point[1] + 0.125 * velocity[1], point[2]))
            instant_yaw = abs(angle(self.actual[0] - instant[0]))
            instant_pitch = abs(self.actual[1] - instant[1])
            yaw_tol = math.atan(0.75 * radius / max(1, d))
            pitch_tol = math.atan(0.4 * height / max(1, d))
            aligned = instant_yaw < 0.90 * yaw_tol and instant_pitch < pitch_tol
            gun = self.gun
            aim = gun_aim = self.gun_aim(origin, point, velocity) if gun else instant
            can_gun = gun and gun.ammo > 0 and gun.reload <= 0 and d <= 0.96 * gun.stat("range", 230)
        for i, weapon in enumerate(self.slots):
            if weapon is None:
                continue
            if weapon.kind == "gun":
                if can_gun:
                    yaw, pitch = self.errors(gun_aim)
                    triggers[i] = yaw < yaw_tol and pitch < pitch_tol
                if shot is None and farm is None and defense is None and weapon.reload <= 0:
                    mag = weapon.stat("mag", 12)
                    if weapon.ammo < mag and (weapon.ammo <= 0.6 * mag or self.now - self.last_threat > 3):
                        action["reload"] = True
            elif weapon.kind == "lightning" and target:
                triggers[i] = (d < weapon.stat("range", 45) - 1.5
                               and instant_yaw < 0.5 * math.radians(weapon.stat("cone_deg", 30)) - 0.05
                               and self.energy >= weapon.stat("energy", 3))
            elif weapon.kind == "laser":
                full = weapon.stat("charge", 0.75)
                reach = weapon.stat("range", 280)
                if shot and d <= 0.97 * reach:
                    charge = weapon.charge
                    if charge >= full - 0.051:
                        aim, triggers[i] = instant, not aligned
                    elif self.squad and aligned and charge >= weapon.stat("min_charge", 0.15) and self.lethal(shot, weapon, full):
                        aim = instant
                    else:
                        triggers[i] = True
                        if charge > 0.45 * full:
                            aim = instant
                elif not shot and blocked:
                    triggers[i] = (weapon.cooldown <= 0.05 and blocked.dist < reach
                                   and weapon.charge < full + weapon.stat("hold_s", 2) - 0.35)
            elif (weapon.kind == "mortar" and shot and 16 <= d <= 200 and weapon.cooldown <= 0.25):
                mortar = self.mortar_aim(origin, raised(point, -height * 0.5), velocity, weapon)
                if mortar is not None:
                    if not can_gun:
                        aim = mortar
                    yaw, pitch = self.errors(mortar)
                    triggers[i] = yaw < 0.04 and pitch < 0.03
        action["fire"] = triggers
        if aim is not None and all(math.isfinite(v) for v in aim):
            self.last_aim = (aim[0], limit(aim[1], self.min_pitch, self.max_pitch))
            action["aim"] = self.last_aim

    def errors(self, aim):
        return (max(0, abs(angle(self.actual[0] - aim[0])) - self.yaw_slew),
                max(0, abs(self.actual[1] - aim[1]) - self.pitch_slew))

    def lethal(self, shot, laser, full):
        fraction = laser.stat("min_frac", 0.35)
        damage = laser.stat("damage", 315) * (fraction + (1 - fraction) * laser.charge / max(1e-6, full))
        damage *= 1 + number(self.cube_config.get("damage_per_cube"), 0.04) * min(self.cube_cap, self.cubes)
        if "mortar" in shot.weapons:
            damage *= 1 + laser.stat("cookoff", 0.6)
        return 0.80 * damage >= shot.hp

    def act(self, obs):
        if self.arena is None:
            return {"aim": self.last_aim}
        self.work_rays = 0
        self.prepare(obs)
        self.refresh(obs)
        shot, blocked = self.targets()
        action = {}
        self.pick(obs, action)
        self.mode, move, boost, jump, farm = self.movement(shot, blocked)
        if self.mode not in ("escape", "unstuck"):
            move, boost = self.dodge(move, boost)
        if not all(math.isfinite(v) for v in move):
            move = ZERO
        jump = self.stuck(move, jump, self.mode == "escape")
        action.update(move=move, boost=bool(boost and move != ZERO), jump=jump)
        self.fire(action, move, shot, blocked, farm)
        self.take(obs, action)
        return action
