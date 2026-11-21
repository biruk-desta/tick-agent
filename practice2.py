"""Practice policy. It owns its tracking, navigation and random stream."""

from array import array
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from struct import Struct
import sys
from time import perf_counter

from example_bot import bearing, distance, limit, obj, raised, seq

try:
    import _practice_fast as fast
except ImportError:
    fast = None


ZERO = (0.0, 0.0)
ZERO3 = (0.0, 0.0, 0.0)
INF = math.inf
GUARD_SECONDS = 0.010
NATIVE_ROUTE_SECONDS = 0.008
PYTHON_ROUTE_SECONDS = 0.0037
HEADINGS = tuple((math.cos(i * math.pi / 8), math.sin(i * math.pi / 8)) for i in range(16))
EXPOSURE_HEADINGS = tuple((math.cos(i * math.pi / 12), math.sin(i * math.pi / 12)) for i in range(24))
FIGHT_RING = tuple((direction, 6) for direction in HEADINGS)
PEEK_HEADINGS = HEADINGS[::2]
SQUAD_STEPS = ((ZERO, 0),) + FIGHT_RING
OPEN_STEPS = SQUAD_STEPS + tuple((direction, 12) for direction in HEADINGS)
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
RANK = {"laser": 4, "lightning": 3, "mortar": 1}
OPEN_UPGRADES = ("plating", "armor", "gun_damage", "nanites", "gun_rate", "lightning_efficiency",
                 "lightning_range", "laser_damage", "servos", "laser_charge")
SQUAD_UPGRADES = ("plating", "armor", "laser_damage", "laser_charge", "nanites", "gun_damage",
                  "gun_rate", "lightning_efficiency", "lightning_range", "servos")
END_UPGRADES = ("gun_mag", "gun_velocity", "gyros", "lightning_chain", "reactor", "capacitor",
                "mortar_reload", "mortar_splash", "mortar_velocity", "sensors", "jets", "laser_pierce")
UPGRADE_RANKS = tuple({ident: i for i, ident in enumerate(start + END_UPGRADES)}
                      for start in (OPEN_UPGRADES, SQUAD_UPGRADES))
FLOAT32 = Struct("=f")
RNG_LENGTH, RNG_TAP = 607, 273
WORD_MASK = (1 << 64) - 1
SIGNED_MASK = (1 << 63) - 1
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
    """Convolve modulo 2**64 and x**607 - x**334 - 1.

    A convolution coefficient fits in 144 bits, so packed integer multiplication
    computes all coefficients without carry between them.
    """
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
    """Generate the Go math/rand seed mix with a recurrence jump."""
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
    """The seeded Go math/rand stream, implemented using Python integers."""

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


CM_TO_M = f32(0.01)
ORTH_RISE, DIAG_RISE = f32(2.2), f32(3.1)
EDGE_COST = tuple(tuple(f32(step * f32(1 + f32(f32(0.15) * max(0, 4 - clearance))))
                        for clearance in range(21)) for step in (2, f32(2 * f32(1.4142))))
LANDING_DISTANCES = array("d", (math.hypot(2 * x, 2 * y) for y in range(21) for x in range(21)))


def map_order(table):
    """Approximate Go's unspecified map traversal by ascending numeric wire ID."""
    return (table[ident] for ident in sorted(table))


def number(value, default=0.0):
    return default if value is None else value


def ratio(numerator, denominator):
    if denominator:
        return numerator / denominator
    if not numerator:
        return math.nan
    return math.copysign(INF, numerator) * math.copysign(1, denominator)


def angle(value):
    wrapped = math.fmod(value, math.tau)
    if wrapped > math.pi:
        return wrapped - math.tau
    if wrapped < -math.pi:
        return wrapped + math.tau
    return wrapped


def vector(value, size):
    values = seq(value)
    if size == 3 and len(values) >= 3:
        return number(values[0]), number(values[1]), number(values[2])
    if size == 2 and len(values) >= 2:
        return number(values[0]), number(values[1])
    return tuple(number(values[i]) if i < len(values) else 0.0 for i in range(size))


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

    def blocks(self, start, delta, ray_bounds):
        x, y, z = start
        dx, dy, dz = delta
        left, bottom, right, top = self.bounds
        x0, y0, z0, x1, y1, z1 = ray_bounds
        if z0 > self.top or z1 < self.base or x0 > right or x1 < left or y0 > top or y1 < bottom:
            return False
        enter, exit = 0.0, 1.0
        for origin, span, low, high in ((x, dx, left, right), (y, dy, bottom, top),
                                        (z, dz, self.base, self.top)):
            if abs(span) < 1e-9:
                if not low <= origin <= high:
                    return False
                continue
            a, b = (low - origin) / span, (high - origin) / span
            if a > b:
                a, b = b, a
            enter, exit = max(enter, a), min(exit, b)
            if enter > exit:
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
    """Exact shot geometry, plus the two rasters used by the practice policy."""

    def __init__(self, directory=None, *, world=None, heights=None):
        if world is None:
            try:
                root = Path(directory or "/arena") / "v2"
                world = json.loads((root / "world.json").read_bytes())
                raw = (root / "terrain.i16").read_bytes()
                terrain = world["terrain"]
                count = terrain["nx"] * terrain["ny"]
                if terrain["nx"] < 2 or terrain["ny"] < 2 or len(raw) < 2 * count:
                    raise ValueError("Invalid terrain grid")
                samples = array("h", raw[:2 * count])
                if sys.byteorder != "little":
                    samples.byteswap()
                heights = array("f", (h * CM_TO_M for h in samples))
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
        self.bucket_w = math.ceil((self.right - self.left) / 16) + 3
        self.bucket_h = math.ceil((self.top - self.bottom) / 16) + 3
        self.buckets = {}
        for prism in self.prisms:
            x0, y0, x1, y1 = prism.bounds
            for j in range(max(0, math.floor((y0 - self.by) / 16)),
                           min(self.bucket_h, math.floor((y1 - self.by) / 16) + 1)):
                for i in range(max(0, math.floor((x0 - self.bx) / 16)),
                               min(self.bucket_w, math.floor((x1 - self.bx) / 16) + 1)):
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
        self.ray_cache = {}
        self.routes = {}
        self.snaps = {}
        bounded = all(-1e8 < value < 1e8 for value in
                      (self.x0, self.y0, self.bx, self.by, self.right, self.top))
        self.native = self.load_native() if fast is not None and bounded else None
        # On integer grids the landing offsets are exact multiples of 2 m.
        self.native_escape = self.native is not None and all(
            value == int(value) for value in (self.x0, self.y0))

    def load_native(self):
        prisms, edges = array("d"), array("d")
        edge_starts, bucket_starts, bucket_prisms = array("i", [0]), array("i", [0]), array("i")
        prism_ids = {}
        for index, prism in enumerate(self.prisms):
            prism_ids[prism] = index
            prisms.extend((prism.base, prism.top, *prism.bounds))
            for edge in prism.edges:
                edges.extend(edge)
            edge_starts.append(len(edges) // 4)
        for j in range(self.bucket_h):
            for i in range(self.bucket_w):
                bucket_prisms.extend(prism_ids[p] for p in self.buckets.get((i, j), ()))
                bucket_starts.append(len(bucket_prisms))
        heuristics = array("f", (value for row in self.heuristic_rows for value in row))
        costs = array("f", EDGE_COST[0] + EDGE_COST[1])
        return fast.load_arena(
            (self.steps, self.clearance, heuristics, costs, self.heights, array("d", self.block_max),
             prisms, edges, edge_starts, bucket_starts, bucket_prisms,
             self.landing_cell if self.landing_cell is not None else array("i"), LANDING_DISTANCES),
            (self.w, self.nx, self.ny, self.block_width, self.bucket_w, self.bucket_h),
            (self.x0, self.y0, self.bx, self.by, self.terrain_top, self.terrain_bottom,
             self.solid_top if self.buckets else -INF),
        )

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
        a = (1 - fx) * g[idx] + fx * g[idx + 1]
        idx += self.nx
        b = (1 - fx) * g[idx] + fx * g[idx + 1]
        return (1 - fy) * a + fy * b

    def local_prisms(self, x, y):
        return self.buckets.get((math.floor((x - self.bx) / 16), math.floor((y - self.by) / 16)), ())

    def surface(self, x, y, decks=True):
        ground = self.bare(x, y)
        candidates = [p for p in self.local_prisms(x, y) if p.top > ground and p.contains(x, y)]
        return self.stack(ground, candidates, decks)[0]

    @staticmethod
    def stack(ground, candidates, decks=True):
        surface = ground
        raised_by = None
        for _ in range(8):
            previous = surface
            for p in candidates:
                if p.top > surface and (p.base <= surface + 1.5 or decks and p.bridge and p.top < ground + 6.5):
                    surface = p.top
                    raised_by = p
            if surface == previous:
                break
        return surface, raised_by

    def solid(self, point):
        x, y, z = point
        return z < self.bare(x, y) or any(p.base < z < p.top and p.contains(x, y)
                                          for p in self.local_prisms(x, y))

    def clear_ray(self, start, end):
        # The segment is directed: the endpoint and stepping rules differ
        # from their reverse. Coordinates are exact and terrain is immutable.
        key = tuple(start), tuple(end)
        cached = self.ray_cache.get(key)
        if cached is not None:
            return cached
        result = None
        if self.native is not None:
            step = 0.0
            if min(start[2], end[2]) <= self.terrain_top and self.terrain_top != self.terrain_bottom:
                span = math.hypot(end[0] - start[0], end[1] - start[1])
                if span > 1e-9:
                    step = 0.5 / span
            result = fast.clear_ray(self.native, key[0], key[1], step)
        if result is None:
            result = self.clear_ray_python(start, end)
        if len(self.ray_cache) < 4096:
            self.ray_cache[key] = result
        return result

    def clear_ray_python(self, start, end):
        x, y, z = start
        ex, ey, ez = end
        dx, dy, dz = ex - x, ey - y, ez - z
        low = min(z, ez)
        check_terrain = low <= self.terrain_top
        if check_terrain and z < self.bare(x, y):
            return False
        if self.buckets and low <= self.solid_top:
            bx, by = self.bx, self.by
            i, j = math.floor((x - bx) / 16), math.floor((y - by) / 16)
            ei, ej = math.floor((ex - bx) / 16), math.floor((ey - by) / 16)
            si = (1 if dx > 0 else -1) if abs(dx) > 1e-9 else 0
            sj = (1 if dy > 0 else -1) if abs(dy) > 1e-9 else 0
            tx = (bx + (i + (si > 0)) * 16 - x) / dx if si else INF
            ty = (by + (j + (sj > 0)) * 16 - y) / dy if sj else INF
            dtx, dty = abs(16 / dx) if si else INF, abs(16 / dy) if sj else INF
            seen = set()
            delta = dx, dy, dz
            ray_bounds = (min(x, ex), min(y, ey), low, max(x, ex), max(y, ey), max(z, ez))
            for _ in range(4096):
                for p in self.buckets.get((i, j), ()):
                    if p not in seen:
                        if p.blocks(start, delta, ray_bounds):
                            return False
                        seen.add(p)
                if (i == ei or not si) and (j == ej or not sj):
                    break
                if si and i != ei and (tx < ty or j == ej or not sj):
                    i, tx = i + si, tx + dtx
                else:
                    j, ty = j + sj, ty + dty
        if not check_terrain:
            return True
        span = math.hypot(dx, dy)
        if span <= 1e-9 or self.terrain_top == self.terrain_bottom:
            return ez >= self.bare(ex, ey)
        return self.terrain_clear(start, (dx, dy, dz), 0.5 / span, end)

    def terrain_clear(self, start, delta, step, end):
        x, y, z = start
        dx, dy, dz = delta
        x0, y0 = self.x0, self.y0
        nx, ny = self.nx, self.ny
        width, blocks = self.block_width, self.block_max
        t = 0.0
        for _ in range(100001):
            u, v = x + dx * t - x0, y + dy * t - y0
            if 0 <= u < nx and 0 <= v < ny:
                i, j = int(u) // 8, int(v) // 8
                peak = blocks[j * width + i]
                if z + dz * t > peak:
                    tx = (8 * (i + (dx > 0)) + x0 - x) / dx if dx else INF
                    ty = (8 * (j + (dy > 0)) + y0 - y) / dy if dy else INF
                    edge = min(1.0, min(tx, ty) + 1e-6)
                    if edge > t and z + dz * edge > peak:
                        t = edge
                        if t >= 1:
                            return True
                        continue
            t += step
            if t >= 1:
                ex, ey, ez = end
                return ez >= self.bare(ex, ey)
            if z + dz * t < self.bare(x + dx * t, y + dy * t):
                return False
        return True

    def build_raster(self):
        nx, ny = self.nx, self.ny
        self.raster_top = tops = self.heights[:]
        self.raster_obstacle = obstacles = bytearray(nx * ny)
        self.raster_slabs = slabs = {}
        spans = {}
        for p in self.prisms:
            _, low, _, high = p.bounds
            for j in range(max(0, math.ceil(low - self.y0)), min(ny, math.floor(high - self.y0) + 1)):
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
                    slabs.setdefault(cell, []).append((f32(p.base), f32(p.top)))
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
            surface, raised_by = self.stack(ground, containing)
            surfaces[cell] = surface
            if (surface > ground + 1.5 and not raised_by.bridge
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
                if free[nxt] and f32(surfaces[nxt] - level) <= ORTH_RISE:
                    mask |= 1 << i
                    if f32(level - surfaces[nxt]) <= ORTH_RISE:
                        mutual[cell] |= 1 << i
            for i, (dx, dy) in enumerate(NEIGHBORS[4:], 4):
                nxt = cell + self.offsets[i]
                if free[nxt] and free[cell + dx] and free[cell + dy * w] and f32(surfaces[nxt] - level) <= DIAG_RISE:
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
        self.heuristic_rows = tuple(tuple(f32((max(dx, dy) + 0.4142 * min(dx, dy)) * 2 * 1.15)
                                          for dx in range(w)) for dy in range(h))

    def build_landings(self):
        """Grow the main component in grid order, including through solids."""
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
        if cell not in self.snaps:
            if len(self.snaps) >= 1024:
                del self.snaps[next(iter(self.snaps))]
            self.snaps[cell] = self.snap_blocked(cell)
        return self.snaps[cell]

    def snap_blocked(self, cell):
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
                if not free[nxt] or f32(heights[nxt] - heights[previous]) > DIAG_RISE:
                    return False
                previous = nxt
        return True

    def exposure(self, point, ceiling=INF, terms=()):
        """Accumulate raster exposure, stopping when it cannot win a score comparison."""
        x, y = point
        left, right, bottom, top = self.left, self.right, self.bottom, self.top
        z = self.surface(x, y) + 7
        tops, slabs = self.raster_top, self.raster_slabs
        total = 0.0
        for dx, dy in EXPOSURE_HEADINGS:
            hit = 200
            if z > self.raster_ceiling and left < x < right and bottom < y < top:
                x_edge = ((right if dx > 0 else left) - x) / dx if dx else INF
                y_edge = ((top if dy > 0 else bottom) - y) / dy if dy else INF
                edge = max(1, min(80, math.floor(min(x_edge, y_edge) / 2.5)))
                # Check the real sample on either side of the analytic crossing.
                for i in range(max(1, edge - 1), min(80, edge + 2)):
                    span = 2.5 * i
                    if not (left < x + dx * span < right and bottom < y + dy * span < top):
                        hit = span
                        break
            else:
                raster_cell = self.raster_cell
                for i in range(1, 80):
                    span = 2.5 * i
                    px, py = x + dx * span, y + dy * span
                    if not (left < px < right and bottom < py < top):
                        hit = span
                        break
                    idx = raster_cell(px, py)
                    intervals = slabs.get(idx)
                    if z < tops[idx] - 0.05 or intervals and any(a < z < b for a, b in intervals):
                        hit = span
                        break
            total += hit
            if ceiling < INF:
                bound = 120 * (total / 4800)
                for term in terms:
                    bound += term
                if bound >= ceiling:
                    return INF
        return total / 4800


class Route:
    """Weighted A* with the practice policy's strict heap ordering."""

    def __init__(self, arena, start, goal):
        self.arena, self.start, self.goal = arena, start, goal
        self.result = None
        if arena.native is None:
            self.slices = self.search_python()
            self.native = None
        else:
            sy, sx = divmod(start, arena.w)
            gy, gx = divmod(goal, arena.w)
            heuristic = arena.heuristic_rows[abs(sy - gy)][abs(sx - gx)]
            self.native = fast.start_route(start, goal, arena.w, len(arena.steps), heuristic)

    def advance(self, deadline=INF):
        while self.result is None and perf_counter() < deadline:
            cells = (fast.advance_route(self.arena.native, self.native)
                     if self.native is not None else next(self.slices))
            if cells is not None:
                self.result = tuple(map(self.arena.point, cells))
        return self.result is not None

    def search_python(self):
        arena, goal, start = self.arena, self.goal, self.start
        steps, offsets, clearance = arena.steps, arena.step_offsets, arena.clearance
        width = arena.w
        gy, gx = divmod(goal, width)
        xdelta = tuple(abs(x - gx) for x in range(width))
        heuristics = tuple(arena.heuristic_rows[abs(y - gy)] for y in range(arena.h))
        y, x = divmod(start, width)
        best, best_h = start, heuristics[y][xdelta[x]]
        heap = [(best_h, start, best_h)]
        costs = {start: 0.0}
        parent = {start: None}
        closed = bytearray(len(steps))
        pack, unpack = FLOAT32.pack, FLOAT32.unpack
        pops = 0
        while heap and pops < 22000:
            if pops and pops % 128 == 0:
                yield None
            _, cell, heur = heap[0]
            last = heap.pop()
            count = len(heap)
            if count:
                idx, child = 0, 1
                while child < count:
                    node = heap[child]
                    right = child + 1
                    if right < count and heap[right][0] < node[0]:
                        child, node = right, heap[right]
                    if last[0] <= node[0]:
                        break
                    heap[idx] = node
                    idx, child = child, child * 2 + 1
                heap[idx] = last
            pops += 1
            if closed[cell]:
                continue
            if cell == goal:
                best = cell
                break
            closed[cell] = 1
            if heur < best_h:
                best, best_h = cell, heur
            base = costs[cell]
            for delta, diagonal in offsets[steps[cell]]:
                nxt = cell + delta
                if closed[nxt]:
                    continue
                unrounded = base + EDGE_COST[diagonal][clearance[nxt]]
                old_cost = costs.get(nxt, INF)
                # A strictly cheaper rounded cost requires a smaller exact sum.
                if unrounded >= old_cost:
                    continue
                cost = unpack(pack(unrounded))[0]
                if cost < old_cost:
                    costs[nxt] = cost
                    parent[nxt] = cell
                    y, x = divmod(nxt, width)
                    heur = heuristics[y][xdelta[x]]
                    key = unpack(pack(cost + heur))[0]
                    idx = len(heap)
                    node = key, nxt, heur
                    heap.append(node)
                    while idx:
                        ancestor = (idx - 1) // 2
                        previous = heap[ancestor]
                        if key >= previous[0]:
                            break
                        heap[idx] = previous
                        idx = ancestor
                    heap[idx] = node
        path, cell = [], best
        while cell is not None:
            path.append(cell)
            cell = parent[cell]
        yield path[::-1]

    def path(self):
        return self.result


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

    def stat(self, key):
        return number(self.stats.get(key))


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
    def __init__(self, hello):
        self.slot = hello.get("slot") or 0
        self.rng = RandomStream(hello.get("seed") or self.slot + 1)
        config = obj(hello.get("config"))
        self.mech = obj(config.get("mech"))
        self.npc = obj(config.get("npc"))
        self.crate_config = obj(config.get("crates"))
        self.cube_config = obj(config.get("cubes"))
        self.loot_config = obj(config.get("loot"))
        self.weapon_config = obj(config.get("weapons"))
        self.map_dir = obj(hello.get("map")).get("dir")
        self.arena = None
        self.enemies, self.drones = {}, {}
        self.items = {key: {} for key in ("pickups", "cubes", "crates")}
        self.zone = Zone()
        self.kills = self.deficit_ticks = 0
        self.start_alive = None
        self.disqualified = self.squad = self.retreat = False
        self.incoming = self.last_threat = -100.0
        self.incoming_bearing = self.drone_bearing = 0.0
        self.drone_hit = self.losing = 0.0
        self.selected, self.selected_at = 0, 0.0
        self.last_fire_target = None
        self.last_aim = ZERO
        self.loot_id, self.loot_since, self.blacklist = -1, 0.0, {}
        self.home = None
        self.home_at = -INF
        self.cover_goal, self.cover_at = None, -INF
        self.strafe_side, self.strafe_until = 1, 0.0
        self.stuck_since = self.unstuck_until = 0.0
        self.unstuck = ZERO
        self.route_goal = None
        self.route_at = -INF
        self.path, self.waypoint = (), 0
        self.pending_route, self.pending_goal = None, None
        self.route_slices = 0
        self.deadline = self.route_deadline = INF
        self.guard_fired = False
        self.guard_firings = 0
        self.escape_plan = None
        self.escape_at = -INF
        self.escape_jumping = False
        self.mode = "start"

    def load_map(self):
        directory = self.map_dir
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
        self.cube_cap = number(self.cube_config.get("stat_cap"))
        self.alive = number(obs.get("alive"))
        stats = obj(me.get("stats"))
        if not number(stats.get("radius")):
            stats = self.mech
        self.radius = number(stats.get("radius"))
        self.height = number(stats.get("height"))
        self.muzzle_height = number(stats.get("muzzle_height"))
        self.muzzle = raised(self.pos, self.muzzle_height)
        self.eye = raised(self.pos, number(stats.get("eye_height")))
        self.walk_speed = number(stats.get("walk_speed"))
        self.yaw_slew = 0.05 * number(stats.get("turn_rate"))
        self.pitch_slew = 0.05 * number(stats.get("pitch_rate"))
        self.min_pitch = number(stats.get("min_pitch"))
        self.max_pitch = number(stats.get("max_pitch"))
        self.raw_slots = seq(me.get("weapons"))
        self.slots = [self.weapon(raw) for raw in self.raw_slots]
        self.primary, self.secondary = (self.slots + [None, None])[:2]
        self.gun, self.laser, self.lightning = (next((w for w in self.slots if w and w.kind == kind), None)
                                               for kind in ("gun", "laser", "lightning"))
        self.zone.update(obj(obs.get("zone")), self.now)
        self.zone_goal = self.zone.goal(self.pos)
        self.zone_span = distance(self.pos, self.zone_goal)
        self.zone_arrival = self.now + ratio(1.45 * self.zone_span, self.walk_speed) + 4
        self.zone_deadline = self.zone.deadline(self.pos, 8)
        self.late = self.zone.next[2] <= 70 or self.alive <= 3
        self.projectiles = [(raw.get("kind"), vector(raw.get("pos"), 3), vector(raw.get("vel"), 3))
                            for item in seq(obs.get("projectiles")) if (raw := obj(item))]
        self.drops = [vector(raw.get("pos"), 3) for item in seq(obs.get("drops")) if (raw := obj(item))]
        self.raw_mechs = seq(obs.get("mechs"))
        if self.start_alive is None:
            self.start_alive = self.alive

    def weapon(self, raw):
        if raw is None:
            return None
        w = obj(raw)
        kind = w.get("kind") or ""
        stats = obj(w.get("stats"))
        return Weapon(kind, stats, number(w.get("ammo")), number(w.get("reload")),
                      number(w.get("charge")), number(w.get("cooldown")))

    def refresh(self, obs):
        now, own = self.now, self.pos
        arena = self.arena
        clear = arena.clear_ray
        for table in (self.enemies, self.drones):
            for track in table.values():
                track.engaged = False
                track.fresh = track.seen == now
                if table is self.enemies and not track.fresh:
                    track.clear = False
        base_radius = number(self.mech.get("radius"))
        base_height = number(self.mech.get("height"))
        base_eye = number(self.mech.get("eye_height"))
        npc_radius = number(self.npc.get("radius"))
        npc_height = number(self.npc.get("height"))
        size_per_cube = number(self.cube_config.get("size_per_cube"))
        for item in self.raw_mechs:
            raw = obj(item)
            kind = raw.get("kind") or ""
            ident = number(raw.get("id"))
            table = self.drones if kind == "npc" else self.enemies
            pos, vel, aim = vector(raw.get("pos"), 3), vector(raw.get("vel"), 3), vector(raw.get("aim"), 2)
            cubes = number(raw.get("cubes"))
            if kind != "npc":
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
        self.awareness = [e for e in map_order(self.enemies) if now - e.seen <= 2.5]
        self.threat_eyes = [(e.id, raised(e.pos, e.eye)) for e in self.awareness]
        for kind, table in self.items.items():
            for item in seq(obs.get(kind)):
                raw = obj(item)
                ident, pos = number(raw.get("id")), vector(raw.get("pos"), 3)
                table[ident] = Track(ident, raw.get("kind", kind), pos, now, hp=number(raw.get("hp")),
                                     dist=distance(own, pos))
            for ident, item in tuple(table.items()):
                if item.seen == now:
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
                if self.squad:
                    value -= 100 * (e.hp <= 0.3 * e.max_hp)
                    value -= 120 * (e.id == self.selected and self.now - self.selected_at < 2)
                value -= 40 * (hit_age < 4)
                value -= 15 * (e.closing > 3)
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
                losing |= hp < 0.35 and theirs > hp + 0.10
                if theirs < 0.25 and hp > 0.20 and nearby <= 2:
                    losing = False
            if losing:
                self.losing = now
            self.retreat = self.losing > 0 and now - self.losing < 1.5

    def pick(self, obs, action):
        choices = seq(obj(obs.get("offer")).get("choices"))
        if choices:
            rank = UPGRADE_RANKS[self.squad]
            action["pick"] = min(range(len(choices)), key=lambda i: rank.get(obj(choices[i]).get("id"), INF))

    def wants(self, kind):
        if kind == "gun":
            return bool(self.raw_slots) and self.raw_slots[0] is None
        if not isinstance(kind, str) or kind in ("mortar", "gun"):
            return False
        secondary = self.secondary
        return (all(w is None or w.kind != kind for w in self.slots)
                and RANK.get(kind, 0) > (RANK.get(secondary.kind, 0) if secondary else 0))

    def take(self, obs, action):
        reach = number(self.loot_config.get("pickup_radius")) - 0.3
        for item in seq(obs.get("pickups")):
            raw = obj(item)
            if not self.wants(raw.get("kind")):
                continue
            pos = vector(raw.get("pos"), 3)
            if distance(self.pos, pos) > reach or abs(self.pos[2] - pos[2]) > 3.6:
                continue
            secondary = self.secondary
            swapping = self.primary is not None and secondary is not None
            if swapping and secondary.kind == "laser" and secondary.charge > 0:
                break
            action["take"] = int(number(raw.get("id")))
            if swapping:
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
            for item in map_order(table):
                span = distance(self.pos, item.pos)
                if category == 0:
                    if not self.wants(item.kind):
                        continue
                    laser = self.squad and item.kind == "laser"
                    radius = 240 if laser else phase_radius
                    value = 150 if laser else 130 if len(self.raw_slots) > 1 and self.raw_slots[1] is None else 60
                elif category == 1:
                    radius, value = max(60, phase_radius * 0.7), cube_value
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
                if (zone.deadline(item.pos, 6) < now + ratio(1.4 * span, self.walk_speed) + 5
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

    def travel(self, goal):
        arena, pos = self.arena, self.pos
        span = distance(pos, goal)
        direct = unit(pos, goal)
        if span < 0.8:
            return ZERO
        if arena.above_obstacle(pos) or span < 45 and arena.walkable(pos, goal):
            return direct
        if (self.pending_route is not None or not self.path or self.now - self.route_at > 2.5
                or distance(self.route_goal, goal) > 5):
            start, end = arena.snap(pos), arena.snap(goal)
            search = self.pending_route
            if start is None or end is None:
                self.path, self.pending_route = (), None
                return direct
            if (search is not None and (end != search.goal or distance(self.pending_goal, goal) > 5
                                        or distance(pos, arena.point(search.start)) > 12)):
                search = self.pending_route = None
            key = start, end
            # A completed search is a function of the two snapped cells and
            # this immutable grid, including when it reaches the pop cap.
            path = arena.routes.get(key)
            if path is None and perf_counter() < self.route_deadline:
                if search is None:
                    search = self.pending_route = Route(arena, start, end)
                    self.pending_goal = goal
                if search.advance(self.route_deadline):
                    path = search.path()
                    if len(arena.routes) >= 128:
                        del arena.routes[next(iter(arena.routes))]
                    arena.routes[search.start, end] = path
            if path is not None:
                self.path, self.waypoint = path, 0
                self.route_goal, self.route_at = goal, self.now
                self.pending_route = None
            else:
                self.route_slices += 1
                self.guard()
        path = self.path
        if not path:
            return direct
        first = self.waypoint
        nearest = min(range(first, min(first + 10, len(path))), key=lambda i: distance(pos, path[i]))
        if distance(pos, path[nearest]) > 12:
            self.path = ()
            return direct
        self.waypoint = nearest
        last = len(path) - 1
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
        cell = fast.escape_cell(arena.native, start) if arena.native_escape else self.escape_cell(start)
        self.escape_at = self.now
        if cell < 0:
            return None
        launch, land = arena.point(cell), arena.point(arena.landing_cell[cell])
        if distance(launch, land) > 0.1:
            beyond = offset(land, unit(launch, land), 5)
            if arena.inside(*beyond) and arena.main[arena.cell(*beyond)]:
                land = beyond
        return launch, land

    def escape_cell(self, start):
        arena = self.arena
        queue, seen, best, score, visits = deque([(start, 0)]), {start}, -1, INF, 0
        while queue and visits < 60000:
            cell, n = queue.popleft()
            visits += 1
            if 2 * n >= score:
                break
            dest = arena.landing_cell[cell]
            if dest >= 0:
                launch, land = arena.point(cell), arena.point(dest)
                span = distance(launch, land)
                value = 2 * n + 4 * span
                if value < score:
                    best, score = cell, value
            for delta, _ in arena.step_offsets[arena.steps[cell]]:
                nxt = cell + delta
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, n + 1))
        return best

    def escape(self):
        arena, pos = self.arena, self.pos
        jump = False
        if self.grounded:
            self.escape_jumping = False
            start = arena.snap(pos)
            if start is not None and arena.main[start] or arena.above_obstacle(pos):
                self.escape_plan = None
                return None
            if self.escape_plan is None or self.now - self.escape_at > 6:
                self.escape_plan = self.new_escape(start)
            if self.escape_plan is None:
                return None
            launch, _ = self.escape_plan
            if distance(pos, launch) > 2.5:
                return self.travel(launch), False, False
            if self.energy < min(70, 0.7 * self.max_energy):
                return ZERO, False, False
            self.escape_jumping = jump = True
        if not self.escape_jumping or self.escape_plan is None:
            return None
        land = self.escape_plan[1]
        span = distance(pos, land)
        if span < 1.5:
            return ZERO, False, jump
        move = unit(pos, land)
        level = max(arena.surface(*offset(pos, move, n), decks=False) for n in range(int(min(30, span)) + 1))
        return move, pos[2] < level + 2.5 and self.energy > 1, jump

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
        clear = arena.clear_ray

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
                if checked >= 350:
                    break
                if self.guard():
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
        if not self.guard_fired:
            self.cover_goal, self.cover_at = best, self.now
        return self.cover_move(best)

    def cover_move(self, goal):
        return ZERO if distance(self.pos, goal) < 1.5 else self.travel(goal)

    def nearest_cube(self, radius, vertical=INF):
        return min((item for item in map_order(self.items["cubes"])
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
        laser_ready = (laser and laser.charge >= laser.stat("charge") - 0.3
                       and d <= laser.stat("range") - 5)
        if self.squad and (laser or lightning):
            return 1
        if (not self.squad and not laser_ready
                and any(e.fresh and e.charging and e.face_error < 0.3 for e in self.awareness)):
            return -1.6
        if (laser_ready or gun and gun.ammo > 0 and gun.reload <= 0.25 and d <= gun.stat("range") - 10
                or lightning and d <= lightning.stat("range") + 6
                and self.energy >= 3 * lightning.stat("energy")):
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
        clear = arena.clear_ray
        wanted = sight > 0
        best, best_score = ZERO, -INF
        directions = SQUAD_STEPS if self.squad else OPEN_STEPS
        threat_eyes = [eye for ident, eye in self.threat_eyes if ident != foe.id and distance(pos, eye) <= 182]
        for direction, span in directions:
            if span and self.guard():
                break
            dot = direction[0] * sx + direction[1] * sy
            point = offset(pos, direction, span)
            cell = arena.cell(*point)
            if span and (not arena.free[cell] or not arena.walkable(pos, point)):
                turn_next |= span == 6 and dot > 0.9
                continue
            base = -1.1 * abs(distance(point, foe.pos) - preferred) - 0.4 * span
            probe = span == 6 and not self.squad
            zone = self.zone.penalty(point)
            bonus = 1.5 * (cube.dist - distance(point, cube.pos)) if cube else 0
            clearance = 2.5 * max(0, 4 - arena.clearance[cell])
            strafe = (9 * dot if wanted else 0) if span else -8
            stand = 14 if not span and not wanted else 0
            # Each remaining threat can only lower the score. Use the same
            # arithmetic for bounds and final scores, in candidate order.
            upper = base + (45 * sight if wanted else 0) + (8 if probe else 0)
            if upper - zone + bonus - clearance + strafe + stand <= best_score:
                continue
            z = arena.surface(*point)
            sightline = clear((*point, z + self.muzzle_height), foe.midpoint)
            score = base + (45 * sight if sightline else 0)
            stand = 0 if sightline else stand
            extra = probe and sightline == wanted
            if score + (8 if extra else 0) - zone + bonus - clearance + strafe + stand <= best_score:
                continue
            if extra:
                for direction2 in PEEK_HEADINGS:
                    alternative = offset(point, direction2, 7)
                    if arena.free[arena.cell(*alternative)]:
                        elevation = arena.surface(*alternative) + self.muzzle_height
                        if clear((*alternative, elevation), foe.midpoint) != sightline:
                            score += 8
                            break
            body = (*point, z + 0.6 * self.height)
            for eye in threat_eyes:
                if distance(point, eye) <= 170 and clear(eye, body):
                    score -= 30
                    if score - zone + bonus - clearance + strafe + stand <= best_score:
                        break
            score = score - zone + bonus - clearance + strafe + stand
            if score > best_score:
                best, best_score = direction, score
        if turn_next:
            self.strafe_side *= -1
            self.strafe_until = self.now + 0.5
        return best

    def shell_dodge(self):
        arena, pos = self.arena, self.pos
        mortar = obj(self.weapon_config.get("mortar"))
        gravity = number(mortar.get("gravity"))
        gravity = gravity if gravity > 0 else 22
        reach = number(mortar.get("splash_radius")) + self.radius + 2
        for kind, origin, velocity in self.projectiles:
            if kind != "mortar":
                continue
            if arena.native is not None and gravity < 1e8 and all(-1e8 < v < 1e8 for v in (*origin, *velocity)):
                impact = fast.shell_impact(arena.native, origin, velocity, gravity)
            else:
                impact = self.shell_impact(origin, velocity, gravity)
            if impact is None:
                continue
            span = distance(pos, impact)
            if not span < reach:
                continue
            vx, vy, _ = velocity
            away = unit(ZERO, (-vy, vx)) if span < 0.5 else unit(impact, pos)
            for turn in (0, 0.7, -0.7, 1.4, -1.4):
                c, s = heading(turn)
                move = away[0] * c - away[1] * s, away[0] * s + away[1] * c
                if arena.walkable(pos, offset(pos, move, 6)):
                    return move
        return None

    def shell_impact(self, origin, velocity, gravity):
        x, y, z = origin
        vx, vy, vz = velocity
        dx, dy = vx * 0.05, vy * 0.05
        clock = 0.0
        # An impact at or beyond this clock never enters the dodge sweep.
        while clock < 2.5:
            x, y, z = x + dx, y + dy, z + vz * 0.05
            vz -= gravity * 0.05
            if self.arena.solid((x, y, z)):
                return x, y
            clock += 0.05
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
                sign = -1 if -vy * (dx + vx * future) + vx * (dy + vy * future) > 0 else 1
                x -= sign * vy / xy
                y += sign * vx / xy
        laser = False
        for raw in self.raw_mechs:
            foe = obj(raw)
            if foe.get("kind") == "mech" and foe.get("charging"):
                toward = bearing(vector(foe.get("pos"), 3), self.pos)
                if abs(angle(vector(foe.get("aim"), 2)[0] - toward)) > 0.15:
                    continue
                perpendicular = toward + self.strafe_side * math.pi / 2
                x += 1.5 * math.cos(perpendicular)
                y += 1.5 * math.sin(perpendicular)
                laser = True
        norm = math.hypot(x, y)
        if norm > 0.01:
            x, y = 0.4 * move[0] + 0.9 * x / norm, 0.4 * move[1] + 0.9 * y / norm
            cap = max(1, math.hypot(x, y))
            move = x / cap, y / cap
            boost |= laser and self.energy > 25
        return move, boost

    def home_point(self):
        now, zone, arena = self.now, self.zone.next, self.arena
        outside = self.home is None or distance(self.home, zone) > 0.8 * zone[2]
        if not outside and now - self.home_at <= 12:
            return self.home
        pressure = [(e.pos, 80) for e in map_order(self.enemies) if now - e.seen < 20]
        pressure.extend((point, 60) for point in self.drops)

        def score(point, limit=INF):
            crowd = 0.0
            for other, radius in pressure:
                crowd += max(0, 1 - distance(point, other) / radius)
            terms = (0.25 * distance(self.pos, point), 40 * crowd,
                     10 * distance(point, zone) / max(30, zone[2]))
            if sum(terms) >= limit:
                return INF
            value = 120 * arena.exposure(point, limit, terms)
            for term in terms:
                value += term
            return value

        winner, best = None, INF
        for _ in range(40):
            point = offset(zone, heading(math.tau * self.rng.random()), 0.7 * zone[2] * math.sqrt(self.rng.random()))
            if arena.inside(*point) and arena.main[arena.cell(*point)]:
                value = score(point, best)
                if value < best:
                    winner, best = point, value
        if winner is not None:
            if outside or score(self.home) > best + 15:
                self.home = winner
        self.home_at = now
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
                return "retreat", move, move != ZERO and self.energy > 10, False, None
            if self.guard_fired:
                return "retreat", ZERO, False, False, None
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
                     self.pos[2] + number(self.mech.get("eye_height")))
            if (move := self.cover([(None, sight), *self.threat_eyes])) is not None:
                return "hide", move, move != ZERO and self.energy > 30, False, None
            if self.guard_fired:
                return "hide", ZERO, False, False, None
        if (foe := shot or blocked) is not None:
            close = self.squad and foe.hp < 0.38 * foe.max_hp and self.hp_share > 0.42 and self.crowd <= 2
            sight = self.sight_preference(foe)
            move = self.fight(foe, self.preferred(foe, close), sight)
            if (self.squad and not self.guard_fired
                    and (cube := self.nearest_cube(70 if self.hp_share > 0.50 else 70 * 0.57))):
                move = self.travel(cube.pos)
            return "fight", move, bool(self.lightning and foe.dist > 50 and self.energy > 55 and sight > 0), False, None
        if self.zone_span > 2 and self.zone_arrival + 14 >= self.zone_deadline:
            return "advisory-zone", self.travel(self.zone_goal), False, False, None
        loot = self.select_loot()
        if loot:
            category, item, span = loot
            if (category == 2 and span < 50
                    and self.arena.clear_ray(self.muzzle, raised(item.pos, number(self.crate_config.get("height")) * 0.5))):
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
            speed = min(1, ratio(4.6, self.walk_speed)) if not self.danger and self.now - self.incoming > 6 else 1
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
            self.path = ()
            self.stuck_since = -1
            return True
        return jump

    def defensive_drone(self):
        now = self.now
        if self.drone_hit <= 0 or now - self.drone_hit >= 3:
            return None
        best, score = None, 0.7
        for drone in map_order(self.drones):
            if now - drone.seen > 0.5 or not drone.clear or drone.dist > 150:
                continue
            value = abs(angle(bearing(self.pos, drone.pos) - self.drone_bearing))
            if now - drone.hit < 3:
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
        speed = self.gun.stat("speed")
        speed = speed if speed > 0 else 252
        flight = 0
        for _ in range(4):
            travel = 0.075 + flight
            prediction = (point[0] + vx * travel, point[1] + vy * travel,
                          point[2] + (vz * travel * 0.5 if abs(vz) >= 0.5 else 0))
            dx, dy, dz = (prediction[i] - origin[i] for i in range(3))
            flight = max(0, math.sqrt(dx * dx + dy * dy + dz * dz) - 3) / speed
        return aim_from(origin, prediction)

    def mortar_aim(self, origin, point, velocity, weapon):
        speed, gravity = weapon.stat("speed"), weapon.stat("gravity")
        if speed <= 0 or gravity <= 0:
            return None
        x, y = origin[:2]
        z = self.pos[2] + self.height + 0.5
        height = point[2] - z
        flight = 0
        speed_sq = speed * speed
        for _ in range(3):
            travel = 0.075 + flight
            dx = point[0] + velocity[0] * travel - x
            dy = point[1] + velocity[1] * travel - y
            span = math.hypot(dx, dy)
            discriminant = speed_sq * speed_sq - gravity * (gravity * (span * span) + 2 * height * speed_sq)
            if span < 1 or discriminant < 0:
                return None
            pitch = math.atan((speed_sq - math.sqrt(discriminant)) / (gravity * span))
            horizontal = speed * math.cos(pitch)
            flight = span / horizontal
        if not self.min_pitch <= pitch <= self.max_pitch:
            return None
        yaw = math.atan2(dy, dx)
        vx, vy, vz = horizontal * dx / span, horizontal * dy / span, speed * math.sin(pitch)
        t = 0.1
        while t < 0.9 * flight:
            if self.arena.solid((x + vx * t, y + vy * t, z + vz * t - 0.5 * gravity * t * t)):
                return None
            t += 0.1
        return yaw, pitch

    def fire(self, action, move, shot, blocked, farm):
        defense = self.defensive_drone() if shot is None else None
        target = shot or defense or (farm if not self.retreat and self.hp_share >= 0.5 else None)
        self.last_fire_target = target.id if target else None
        triggers = [False, False]
        aim = self.scan(move) if target is None else None
        if target:
            origin = (self.muzzle[0] + self.vel[0] * 0.075, self.muzzle[1] + self.vel[1] * 0.075, self.muzzle[2])
            d = distance(self.pos, target.pos)
            if target is shot:
                point = target.midpoint
                if target.kind == "mech" and not self.arena.clear_ray(origin, point):
                    point = raised(target.pos, target.height * 0.85)
                radius, height = target.radius, target.height
            elif target.kind == "npc":
                point, radius, height = target.midpoint, target.radius, target.height
            else:
                radius = number(self.crate_config.get("radius"))
                height = number(self.crate_config.get("height"))
                point = raised(target.pos, height * 0.5)
            velocity = target.vel
            instant = aim_from(origin, (point[0] + 0.125 * velocity[0], point[1] + 0.125 * velocity[1], point[2]))
            instant_yaw = abs(angle(self.actual[0] - instant[0]))
            instant_pitch = abs(self.actual[1] - instant[1])
            yaw_tol = math.atan2(0.75 * radius, max(1, d))
            pitch_tol = math.atan2(0.4 * height, max(1, d))
            aligned = instant_yaw < 0.90 * yaw_tol and instant_pitch < pitch_tol
            gun = self.gun
            aim = gun_aim = self.gun_aim(origin, point, velocity) if gun else instant
            gun_in_range = gun is not None and d <= 0.96 * gun.stat("range")
        for i, weapon in enumerate(self.slots[:2]):
            if weapon is None:
                continue
            if weapon.kind == "gun":
                if target and gun_in_range and weapon.ammo > 0 and weapon.reload <= 0:
                    yaw, pitch = self.errors(gun_aim)
                    triggers[i] = yaw < yaw_tol and pitch < pitch_tol
            elif weapon.kind == "lightning" and target:
                triggers[i] = (d < weapon.stat("range") - 1.5
                               and instant_yaw < 0.5 * math.radians(weapon.stat("cone_deg")) - 0.05
                               and self.energy >= weapon.stat("energy"))
            elif weapon.kind == "laser":
                full = weapon.stat("charge")
                reach = weapon.stat("range")
                if shot and d <= 0.97 * reach:
                    charge = weapon.charge
                    if charge >= full - 0.051:
                        aim, triggers[i] = instant, not aligned
                    elif self.squad and aligned and charge >= weapon.stat("min_charge") and self.lethal(shot, weapon, full):
                        aim = instant
                    else:
                        triggers[i] = True
                        if charge > 0.45 * full:
                            aim = instant
                elif not shot and blocked:
                    triggers[i] = (weapon.cooldown <= 0.05 and blocked.dist < reach
                                   and weapon.charge < full + weapon.stat("hold_s") - 0.35)
            elif (weapon.kind == "mortar" and shot and 16 <= d <= 200 and weapon.cooldown <= 0.25):
                mortar = self.mortar_aim(origin, raised(point, -height * 0.5), velocity, weapon)
                if mortar is not None:
                    if not gun_in_range or gun.ammo == 0 or gun.reload > 0:
                        aim = mortar
                    yaw, pitch = self.errors(mortar)
                    triggers[i] = yaw < 0.04 and pitch < 0.03
        gun = self.gun
        if gun and shot is None and farm is None and defense is None and gun.reload <= 0:
            mag = gun.stat("mag")
            if gun.ammo < mag and (gun.ammo <= 0.6 * mag or self.now - self.last_threat > 3):
                action["reload"] = True
        action["fire"] = triggers
        if aim is not None and all(math.isfinite(v) for v in aim):
            self.last_aim = (aim[0], limit(aim[1], self.min_pitch, self.max_pitch))
            action["aim"] = self.last_aim

    def errors(self, aim):
        return (max(0, abs(angle(self.actual[0] - aim[0])) - self.yaw_slew),
                max(0, abs(self.actual[1] - aim[1]) - self.pitch_slew))

    def lethal(self, shot, laser, full):
        fraction = laser.stat("min_frac")
        damage = laser.stat("damage") * (fraction + (1 - fraction) * ratio(laser.charge, full))
        damage *= 1 + number(self.cube_config.get("damage_per_cube")) * min(self.cube_cap, self.cubes)
        if "mortar" in shot.weapons:
            damage *= 1 + laser.stat("cookoff")
        return 0.80 * damage >= shot.hp

    def guard(self):
        if not self.guard_fired and perf_counter() >= self.deadline:
            self.guard_fired = True
            self.guard_firings += 1
        return self.guard_fired

    def act(self, obs, observed=None):
        if self.arena is None:
            return {"aim": self.last_aim}
        started = perf_counter() if observed is None else observed
        self.deadline = started + GUARD_SECONDS
        route_budget = NATIVE_ROUTE_SECONDS if self.arena.native is not None else PYTHON_ROUTE_SECONDS
        self.route_deadline = started + route_budget
        self.guard_fired = False
        self.arena.ray_cache.clear()
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
