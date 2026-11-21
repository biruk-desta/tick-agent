"""Static map queries for Mechfight; stdlib only, no game-engine claims.

Prism ray and swept-cylinder tests include polygon holes and vertical slabs.
Terrain ray/movement tests sample at <=0.75m; small terrain features between
samples can differ from server collision. ``available`` is false on map failure;
clearance tests then return False and height queries raise RuntimeError.
"""
from __future__ import annotations

import array
import hashlib
import json
import math
import os
import sys

_EPS = 1e-7


def _inside(x, y, ring):
    """Even/odd polygon membership; boundary handled separately by edges."""
    inside = False
    j = len(ring) - 2
    for i in range(0, len(ring), 2):
        xi, yi, xj, yj = ring[i], ring[i + 1], ring[j], ring[j + 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _point_segment_sq(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length)) if length else 0.0
    return (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


def _segments_sq(ax, ay, bx, by, cx, cy, dx, dy):
    ux, uy, vx, vy = bx - ax, by - ay, dx - cx, dy - cy
    cross = _cross(ux, uy, vx, vy)
    if abs(cross) > _EPS:
        t = _cross(cx - ax, cy - ay, vx, vy) / cross
        u = _cross(cx - ax, cy - ay, ux, uy) / cross
        if -_EPS <= t <= 1 + _EPS and -_EPS <= u <= 1 + _EPS:
            return 0.0
    return min(_point_segment_sq(ax, ay, cx, cy, dx, dy),
               _point_segment_sq(bx, by, cx, cy, dx, dy),
               _point_segment_sq(cx, cy, ax, ay, bx, by),
               _point_segment_sq(dx, dy, ax, ay, bx, by))


class Arena:
    """Load only authoritative prisms and terrain from hello.map.dir.

    ``bounds`` has minX/maxX/minY/maxY, ``available`` and ``error`` report load
    status. Trees are intentionally absent: these queries concern movement and
    shots, not canopy vision. No filesystem writes occur.
    """
    cell_size = 24.0

    def __init__(self, map_dir):
        self.available = False
        self.error = None
        self.bounds = {}
        self.prisms = []
        self._grid = {}
        try:
            with open(os.path.join(map_dir, 'v2', 'world.json'), 'rb') as f:
                world_bytes = f.read()
            self.world_sha256 = hashlib.sha256(world_bytes).hexdigest()
            world = json.loads(world_bytes)
            self.bounds = world['bounds']
            self.terrain = world['terrain']
            self._nx, self._ny = int(self.terrain['nx']), int(self.terrain['ny'])
            self._minx, self._miny = self.terrain['minX'], self.terrain['minY']
            self._step = self.terrain['step']
            self._scale = self.terrain.get('scale', 0.01)
            self._heights = array.array('h')
            with open(os.path.join(map_dir, 'v2', self.terrain['file']), 'rb') as f:
                terrain_bytes = f.read()
            self.terrain_sha256 = hashlib.sha256(terrain_bytes).hexdigest()
            self._heights.frombytes(terrain_bytes)
            with open(__file__, 'rb') as f:
                self.geometry_sha256 = hashlib.sha256(f.read()).hexdigest()
            if sys.byteorder != 'little':
                self._heights.byteswap()
            if len(self._heights) != self._nx * self._ny:
                raise ValueError('terrain byte count does not match grid')
            for raw in world['prisms']:
                ring = raw['ring']
                if len(ring) < 6 or len(ring) % 2:
                    raise ValueError('invalid prism ring')
                holes = raw.get('holes', [])
                edges = []
                for poly in [ring] + holes:
                    for i in range(0, len(poly), 2):
                        j = (i + 2) % len(poly)
                        edges.append((poly[i], poly[i + 1], poly[j], poly[j + 1]))
                box = (min(ring[::2]), min(ring[1::2]), max(ring[::2]), max(ring[1::2]))
                p = {'ring': ring, 'holes': holes, 'edges': edges, 'box': box,
                     'base': raw['base'], 'top': raw['top'], 'kind': raw['kind']}
                idx = len(self.prisms)
                self.prisms.append(p)
                for gx in range(math.floor(box[0] / self.cell_size), math.floor(box[2] / self.cell_size) + 1):
                    for gy in range(math.floor(box[1] / self.cell_size), math.floor(box[3] / self.cell_size) + 1):
                        self._grid.setdefault((gx, gy), []).append(idx)
            self.available = True
        except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
            self.error = f'{type(exc).__name__}: {exc}'

    def terrain_height(self, x, y):
        """Bilinear terrain height, clamped to the map's vertex grid."""
        if not self.available:
            raise RuntimeError(f'arena unavailable: {self.error}')
        u = max(0.0, min(self._nx - 1.0, (x - self._minx) / self._step))
        v = max(0.0, min(self._ny - 1.0, (y - self._miny) / self._step))
        i, j = min(self._nx - 2, int(u)), min(self._ny - 2, int(v))
        fu, fv = u - i, v - j
        k = j * self._nx + i
        h = self._heights
        low = h[k] * (1 - fu) + h[k + 1] * fu
        high = h[k + self._nx] * (1 - fu) + h[k + self._nx + 1] * fu
        return (low * (1 - fv) + high * fv) * self._scale

    def _candidates(self, ax, ay, bx, by, radius=0.0):
        x0, x1 = math.floor((min(ax, bx) - radius) / self.cell_size), math.floor((max(ax, bx) + radius) / self.cell_size)
        y0, y1 = math.floor((min(ay, by) - radius) / self.cell_size), math.floor((max(ay, by) + radius) / self.cell_size)
        found = set()
        for gx in range(x0, x1 + 1):
            for gy in range(y0, y1 + 1):
                found.update(self._grid.get((gx, gy), ()))
        return found

    @staticmethod
    def _solid_xy(p, x, y):
        return _inside(x, y, p['ring']) and not any(_inside(x, y, hole) for hole in p['holes'])

    @staticmethod
    def _slab(a_z, b_z, low, high):
        """Parameter interval where linear z lies strictly inside a slab."""
        low, high = low + _EPS, high - _EPS
        dz = b_z - a_z
        if abs(dz) < _EPS:
            return (0.0, 1.0) if low <= a_z <= high else None
        t0, t1 = (low - a_z) / dz, (high - a_z) / dz
        lo, hi = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
        return (lo, hi) if lo <= hi else None

    def _prism_segment(self, p, a, b, radius, height):
        interval = self._slab(a[2], b[2], p['base'] - height, p['top'])
        if interval is None:
            return False
        t0, t1 = interval
        ax, ay = a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0
        bx, by = a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1
        x0, y0, x1, y1 = p['box']
        if max(ax, bx) + radius < x0 or min(ax, bx) - radius > x1 or max(ay, by) + radius < y0 or min(ay, by) - radius > y1:
            return False
        if self._solid_xy(p, ax, ay) or self._solid_xy(p, bx, by):
            return True
        r2 = radius * radius + _EPS
        for cx, cy, dx, dy in p['edges']:
            if max(ax, bx) + radius < min(cx, dx) or min(ax, bx) - radius > max(cx, dx) or max(ay, by) + radius < min(cy, dy) or min(ay, by) - radius > max(cy, dy):
                continue
            if _segments_sq(ax, ay, bx, by, cx, cy, dx, dy) <= r2:
                return True
        return False

    def point_clear(self, pos, radius, height):
        """Cylinder clearance; touching a prism side is conservatively blocked."""
        if not self.available or not self.in_bounds(pos[0], pos[1], radius):
            return False
        if pos[2] < self.terrain_height(pos[0], pos[1]) - 0.05:
            return False
        return not any(self._prism_segment(self.prisms[i], pos, pos, radius, height)
                       for i in self._candidates(pos[0], pos[1], pos[0], pos[1], radius))

    def in_bounds(self, x, y, radius=0.0):
        return self.available and (self.bounds['minX'] + radius <= x <= self.bounds['maxX'] - radius
                                   and self.bounds['minY'] + radius <= y <= self.bounds['maxY'] - radius)

    def surface_height(self, x, y, reference_z=None, step_up=1.2, height=9.0):
        """Highest center-support surface reachable from reference_z by one step.

        Without a reference only terrain is returned. This is a support query,
        not a claim that the cylinder can reach the surface or fit an overhang.
        """
        floor = self.terrain_height(x, y)
        if reference_z is None:
            return floor
        for i in self._candidates(x, y, x, y):
            p = self.prisms[i]
            if floor < p['top'] <= reference_z + step_up + _EPS and self._solid_xy(p, x, y):
                floor = p['top']
        return floor

    def line_clear(self, a, b):
        """Straight zero-radius shot ray against prisms/terrain (not trees)."""
        if not self.available:
            return False
        if not self.in_bounds(a[0], a[1]) or not self.in_bounds(b[0], b[1]):
            return False
        for i in self._candidates(a[0], a[1], b[0], b[1]):
            if self._prism_segment(self.prisms[i], a, b, 0.0, 0.0):
                return False
        n = max(1, math.ceil(math.dist(a[:2], b[:2]) / 0.75))
        for k in range(n + 1):
            t = k / n
            x, y, z = (a[j] + (b[j] - a[j]) * t for j in range(3))
            if z < self.terrain_height(x, y) - 0.01:
                return False
        return True

    def escape_clear(self, a, b, radius, height, step_up, max_slope_deg, grounded=True):
        """Permit only outward repair of a shallow observed side overlap.

        A legal server position may disagree slightly with this conservative
        cylinder model. Rejecting every sweep at that start would immobilize
        the mech. Reject new solids and solid-center crossings; require sampled
        componentwise clearance progress and exact sweeps after separation.
        This is bounded recovery, not a reduced collision radius.
        """
        if not self.available or not 1e-6 < math.dist(a[:2],b[:2]) <= min(5.,max(1.,radius*2)):
            return False
        blockers={i for i in self._candidates(*a[:2],*a[:2],radius)
                  if self._prism_segment(self.prisms[i],a,a,radius,height)}
        if not blockers or len(blockers)>4 or sum(len(self.prisms[i]['edges']) for i in blockers)>256:
            return False
        def clearance(p,point):
            if self._slab(point[2],point[2],p['base']-height,p['top']) is None:
                return radius
            if self._solid_xy(p,*point[:2]):
                return -1.
            return math.sqrt(min(_point_segment_sq(*point[:2],*edge) for edge in p['edges']))
        initial={i:clearance(self.prisms[i],a) for i in blockers}
        if any(distance < radius-min(.5,radius*.25) for distance in initial.values()):
            return False
        if not self.move_clear(a,b,radius,height,step_up,max_slope_deg,grounded,_ignore=blockers):
            return False
        count=max(1,math.ceil(math.dist(a[:2],b[:2])/.25))
        follow_ground=grounded and abs(a[2]-self.terrain_height(*a[:2]))<.15 and abs(b[2]-self.terrain_height(*b[:2]))<.15
        previous=a;distances=initial.copy();cleared=set()
        for k in range(1,count+1):
            point=tuple(a[j]+(b[j]-a[j])*k/count for j in range(3))
            if follow_ground:
                point=(point[0],point[1],self.terrain_height(*point[:2]))
            for i in blockers:
                prism=self.prisms[i]
                # Once separation is observed, restore the exact full-radius
                # sweep for this blocker. Samples alone can miss a narrow
                # protrusion that reenters the cylinder between two points.
                if i in cleared and self._prism_segment(prism,previous,point,radius,height):
                    return False
                # Exact center-ray rejection prevents crossing a thin solid
                # between the clearance samples, including polygon holes.
                if self._prism_segment(prism,previous,point,0.,height):
                    return False
                distance=clearance(prism,point)
                if distance+1e-6 < min(radius,distances[i]):
                    return False
                distances[i]=distance
                if distance>radius+1e-6:
                    cleared.add(i)
            previous=point
        return all(distances[i]>initial[i]+1e-4 for i in blockers)

    def move_clear(self, a, b, radius, height, step_up, max_slope_deg, grounded=True, _ignore=()):
        """Conservative straight swept-cylinder feet motion.

        Passed z values describe intended feet motion; use surface_height for
        support endpoints. Air motion ignores ground slope but cannot penetrate
        terrain. Ground paths sample support, step-up and slope. Roof departures
        may be allowed (falling), while impossible upward steps are rejected.
        Does not reproduce server wall sliding, eave pushes or mech collisions.
        """
        if not self.available or not self.in_bounds(a[0], a[1], radius) or not self.in_bounds(b[0], b[1], radius):
            return False
        candidates = self._candidates(a[0], a[1], b[0], b[1], radius)
        candidates.difference_update(_ignore)
        horizontal = math.dist(a[:2], b[:2])
        n = max(1, math.ceil(horizontal / 0.75))
        limit = math.tan(math.radians(max_slope_deg))
        ground_a, ground_b = self.terrain_height(a[0], a[1]), self.terrain_height(b[0], b[1])
        if grounded and abs(a[2] - ground_a) < .15 and abs(b[2] - ground_b) < .15:
            # Ground locomotion follows the surface. A chord between endpoint
            # heights can pass through a gentle hill and falsely disconnect a
            # perfectly walkable road in the navigation graph.
            previous = (a[0], a[1], ground_a)
            for k in range(1, n + 1):
                t = k / n
                x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                current = (x, y, self.terrain_height(x, y))
                if current[2] - previous[2] > limit * (horizontal / n) + .05:
                    return False
                if any(self._prism_segment(self.prisms[i], previous, current, radius, height) for i in candidates):
                    return False
                previous = current
            return True
        for i in candidates:
            if self._prism_segment(self.prisms[i], a, b, radius, height):
                return False
        previous_ground = self.terrain_height(a[0], a[1])
        previous_feet = a[2]
        for k in range(n + 1):
            t = k / n
            x, y, z = (a[j] + (b[j] - a[j]) * t for j in range(3))
            ground = self.terrain_height(x, y)
            if z < ground - 0.08:
                return False
            if grounded and k:
                # Directional uphill terrain slope; elevated roof motion is
                # unaffected by terrain far below the body.
                if z <= ground + step_up and previous_feet <= previous_ground + step_up:
                    if ground - previous_ground > limit * (horizontal / n) + 0.05:
                        return False
                if z - previous_feet > max(step_up, limit * (horizontal / n)) + 0.05:
                    return False
            previous_ground, previous_feet = ground, z
        return True
