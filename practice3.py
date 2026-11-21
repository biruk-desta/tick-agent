
from array import array
from collections import deque
import heapq
import math
import random
import struct
import sys
import time


class World:
    






    ns = 2.0
    _dirs = ((1, 0), (-1, 0), (0, 1), (0, -1),
             (1, 1), (1, -1), (-1, 1), (-1, -1))

    def __init__(self, data=None, terrain_bytes=None):
        if data is None:
            data = {"terrain": {"minX": -513., "minY": -334., "nx": 1070,
                                "ny": 724, "step": 1},
                    "bounds": {"minX": -512., "maxX": 555.,
                               "minY": -333., "maxY": 388.}, "prisms": []}
            heights = array("f", [0.]) * (1070 * 724)
        else:
            t = data["terrain"]
            nx, ny = t["nx"], t["ny"]
            if not (2 <= nx <= 2048 and 2 <= ny <= 2048 and t["step"] == 1):
                raise ValueError("practice3 requires a 1 m terrain grid")
            if len(terrain_bytes) != nx * ny * 2:
                raise ValueError("invalid terrain length")
            packed = array("h", terrain_bytes)
            if sys.byteorder != "little":
                packed.byteswap()
            centimetre = self._single(.01)
            heights = array("f", (v * centimetre for v in packed))
        t, b = data["terrain"], data["bounds"]
        self.x0, self.y0 = t["minX"], t["minY"]
        self.nx, self.ny = int(t["nx"]), int(t["ny"])
        self.bx0, self.bx1 = b["minX"], b["maxX"]
        self.by0, self.by1 = b["minY"], b["maxY"]
        self.ground = heights
        self.gx0, self.gy0 = self.bx0 - 16, self.by0 - 16
        self.gnx = math.ceil((self.bx1 - self.bx0) / 16) + 3
        self.gny = math.ceil((self.by1 - self.by0) / 16) + 3
        self.bins = [[] for _ in range(self.gnx * self.gny)]
        self.prisms = []
        for source in data.get("prisms", ()):
            edges, xx, yy = [], [], []
            for ring in [source["ring"]] + source.get("holes", []):
                points = list(zip(ring[::2], ring[1::2]))
                xx.extend(p[0] for p in points)
                yy.extend(p[1] for p in points)
                for a, z in zip(points, points[1:] + points[:1]):
                    dx, dy = z[0] - a[0], z[1] - a[1]
                    edges.append((a[0], a[1], z[0], z[1], dx, dy, dx*dx+dy*dy))
            if not edges:
                continue
            p = (source["base"], source["top"], min(xx), min(yy),
                 max(xx), max(yy), source["kind"], tuple(edges))
            ident = len(self.prisms)
            self.prisms.append(p)
            for c in self._box_cells(p[2], p[3], p[4], p[5]):
                self.bins[c].append(ident)
        self.deadline = math.inf
        self._rise_limits = self._single(2.2), self._single(3.1)
        self._path_job = self._escape_job = None
        self.path_pending = self.escape_pending = False
        self._build_blocks()
        self._build_raster()
        self._build_nav()

    def begin_tick(self, deadline):
        self.deadline = deadline

    def reset_path(self):
        self._path_job, self.path_pending = None, False

    def reset_escape(self):
        self._escape_job, self.escape_pending = None, False

    def _geo_cell(self, x, y):
        i, j = math.floor((x-self.gx0)/16), math.floor((y-self.gy0)/16)
        return j*self.gnx+i if 0 <= i < self.gnx and 0 <= j < self.gny else -1

    def _box_cells(self, x0, y0, x1, y1):
        a, b = max(0, math.floor((x0-self.gx0)/16)), min(self.gnx-1, math.floor((x1-self.gx0)/16))
        c, d = max(0, math.floor((y0-self.gy0)/16)), min(self.gny-1, math.floor((y1-self.gy0)/16))
        for j in range(c, d+1):
            yield from range(j*self.gnx+a, j*self.gnx+b+1)

    @staticmethod
    def _single(value):
        return struct.unpack("f", struct.pack("f", value))[0]

    @staticmethod
    def _inside(edges, x, y):
        result = False
        for ax, ay, bx, by, dx, dy, _ in edges:
            if (ay > y) != (by > y) and x < ax + dx*(y-ay)/dy:
                result = not result
        return result

    def ground_at(self, x, y):
        x = max(0., min(self.nx-1.000001, x-self.x0))
        y = max(0., min(self.ny-1.000001, y-self.y0))
        i, j = int(x), int(y)
        u, v, k = x-i, y-j, j*self.nx+i
        a, n = self.ground, self.nx
        return ((1-u)*a[k] + u*a[k+1])*(1-v) + ((1-u)*a[k+n] + u*a[k+n+1])*v

    def in_bounds(self, x, y):
        return self.bx0 < x < self.bx1 and self.by0 < y < self.by1

    def _stack(self, x, y, deck=True, ground=None):
        g = self.ground_at(x, y) if ground is None else ground
        z, ident = g, -1
        c = self._geo_cell(x, y)
        if c < 0:
            return z, ident
        for _ in range(8):
            before = z
            for k in self.bins[c]:
                p = self.prisms[k]
                if p[1] <= z or x < p[2] or x > p[4] or y < p[3] or y > p[5]:
                    continue
                if (p[0] <= z+1.5 or deck and p[6] == "bridge" and p[1]-g < 6.5) and self._inside(p[7], x, y):
                    z, ident = p[1], k
            if z == before:
                break
        return z, ident

    def walk_at(self, x, y):
        return self._stack(x, y)[0]

    def top_at(self, x, y):
        return self._stack(x, y, False)[0]

    def solid(self, x, y, z):
        if z < self.ground_at(x, y):
            return True
        c = self._geo_cell(x, y)
        if c >= 0:
            for k in self.bins[c]:
                p = self.prisms[k]
                if p[0] < z < p[1] and p[2] <= x <= p[4] and p[3] <= y <= p[5] and self._inside(p[7], x, y):
                    return True
        return False

    def _build_raster(self):
        occupied = {}
        for p in self.prisms:
            bottom, roof = array("f", p[:2])
            slab = bottom, roof, p[6] == "bridge"
            first = max(0, math.ceil(p[3]-self.y0))
            last = min(self.ny-1, math.floor(p[5]-self.y0))
            for j in range(first, last+1):
                y = self.y0+j+.0001
                cuts = sorted(ax+dx*(y-ay)/dy for ax, ay, bx, by, dx, dy, _ in p[7]
                              if (ay <= y) != (by <= y))
                for a, b in zip(cuts[::2], cuts[1::2]):
                    lo = max(0, math.ceil(a-self.x0))
                    hi = min(self.nx-1, math.floor(b-self.x0))
                    for k in range(j*self.nx+lo, j*self.nx+hi+1):
                        occupied.setdefault(k, []).append(slab)
        self.raster_top = array("f", self.ground)
        self.raster_slabs, self.obstacles = {}, bytearray(len(self.ground))
        for key, intervals in occupied.items():
            ground = top = self.ground[key]
            low, slabs = False, []
            for bottom, roof, bridge in sorted(intervals, key=lambda v: v[0]):
                if roof <= top:
                    continue
                if bottom <= self._single(top+1.5):
                    top = roof
                else:
                    slabs.append((bottom, roof))
                    if self._single(bottom-top) < 10.5 and not (bridge and self._single(roof-ground) < 6.5):
                        low = True
            self.raster_top[key] = top
            self.obstacles[key] = self._single(top-ground) > self._single(1.2) or low
            if slabs:
                self.raster_slabs[key] = tuple(slabs)

    def obstacle_at(self, x, y):
        i = min(self.nx-1, max(0, math.floor(x-self.x0+.5)))
        j = min(self.ny-1, max(0, math.floor(y-self.y0+.5)))
        return bool(self.obstacles[j*self.nx+i])

    def _standable(self, x, y, z, candidates):
        if x-2.6 < self.bx0 or x+2.6 > self.bx1 or y-2.6 < self.by0 or y+2.6 > self.by1:
            return False
        for k in candidates:
            p = self.prisms[k]
            if p[1] <= z+1.2 or p[0] >= z+9 or x+2.6 < p[2] or x-2.6 > p[4] or y+2.6 < p[3] or y-2.6 > p[5]:
                continue
            for ax, ay, bx, by, dx, dy, l2 in p[7]:
                u = max(0., min(1., ((x-ax)*dx+(y-ay)*dy)/l2)) if l2 > 1e-9 else 0.
                if (x-ax-u*dx)**2 + (y-ay-u*dy)**2 < 6.76:
                    return False
            if self._inside(p[7], x, y):
                return False
        return True

    def _build_nav(self):
        self.nnx, self.nny = (self.nx+1)//2, (self.ny+1)//2
        n, w = self.nnx*self.nny, self.nnx
        self.blocked, self.surf = bytearray(n), array("f", [0.])*n
        candidates = {}
        for j in range(self.nny):
            y = self.y0+j*2
            for i in range(w):
                x, k = self.x0+i*2, j*w+i
                g = self.ground[j*2*self.nx+i*2]
                z, ident = self._stack(x, y, ground=g)
                self.surf[k] = z
                c = self._geo_cell(x, y)
                if c not in candidates:
                    cx, cy = c % self.gnx, c // self.gnx
                    ids = set()
                    for yy in range(max(0, cy-1), min(self.gny, cy+2)):
                        for xx in range(max(0, cx-1), min(self.gnx, cx+2)):
                            ids.update(self.bins[yy*self.gnx+xx])
                    candidates[c] = tuple(sorted(ids))
                roof = ident >= 0 and self.prisms[ident][6] != "bridge" and z-g > 1.5
                self.blocked[k] = roof or not self._standable(x, y, z, candidates[c])
        blocked, surface = self.blocked, self.surf
        dist = bytearray([10])*n
        queue = deque()
        for k in range(n):
            if blocked[k]:
                dist[k] = 0
                queue.append(k)
        while queue:
            k = queue.popleft()
            nd = dist[k]+1
            if nd >= 10:
                continue
            i = k % w
            for q in (k+1 if i+1 < w else -1, k-1 if i else -1,
                      k+w if k+w < n else -1, k-w if k >= w else -1):
                if q >= 0 and nd < dist[q]:
                    dist[q] = nd
                    queue.append(q)
        self.clearance = array("f", (v*2 for v in dist))
        self._adj = bytearray(n)
        self._offsets = (1, -1, w, -w, w+1, 1-w, w-1, -w-1)
        for k in range(n):
            if blocked[k]:
                continue
            i, j = k % w, k // w
            flags, height = 0, surface[k]
            for d, (dx, dy) in enumerate(self._dirs):
                if not (0 <= i+dx < w and 0 <= j+dy < self.nny):
                    continue
                q = k+self._offsets[d]
                if blocked[q] or self._single(surface[q]-height) > self._rise_limits[d >= 4]:
                    continue
                if d >= 4 and (blocked[k+dx] or blocked[k+dy*w]):
                    continue
                flags |= 1 << d
            self._adj[k] = flags
        comp, sizes = array("i", [-1])*n, []
        for start in range(n):
            if blocked[start] or comp[start] >= 0:
                continue
            label = len(sizes)
            comp[start], queue, size = label, deque([start]), 0
            while queue:
                k = queue.popleft()
                size += 1
                for d, off in enumerate(self._offsets[:4]):
                    if self._adj[k] & (1 << d):
                        q = k+off
                        if comp[q] < 0 and abs(self._single(surface[q]-surface[k])) <= self._rise_limits[0]:
                            comp[q] = label
                            queue.append(q)
            sizes.append(size)
        self.comp = comp
        self.main_comp = max(range(len(sizes)), key=sizes.__getitem__) if sizes else -1
        self._main_near = array("i", [-1])*n
        depth, queue = bytearray(n), deque()
        for k in range(n):
            if not blocked[k] and comp[k] == self.main_comp:
                self._main_near[k] = k
                queue.append(k)
        while queue:
            k = queue.popleft()
            if depth[k] >= 20:
                continue
            i, j = k % w, k // w
            for (dx, dy), off in zip(self._dirs, self._offsets):
                q = k+off
                if 0 <= i+dx < w and 0 <= j+dy < self.nny and self._main_near[q] < 0:
                    self._main_near[q], depth[q] = self._main_near[k], depth[k]+1
                    queue.append(q)

    def cell(self, x, y):
        i = min(self.nnx-1, max(0, math.floor((x-self.x0)/2+.5)))
        j = min(self.nny-1, max(0, math.floor((y-self.y0)/2+.5)))
        return j*self.nnx+i

    def cell_pos(self, c):
        return self.x0+2*(c % self.nnx), self.y0+2*(c // self.nnx)

    def free(self, x, y):
        return not self.blocked[self.cell(x, y)]

    def reachable(self, x, y):
        c = self.cell(x, y)
        return not self.blocked[c] and self.comp[c] == self.main_comp

    def nearest_free(self, c):
        if not self.blocked[c]:
            return c
        x, y, w = c % self.nnx, c // self.nnx, self.nnx
        for r in range(1, 21):
            best, score = -1, math.inf
            for dy in range(-r, r+1):
                if not 0 <= y+dy < self.nny:
                    continue
                for dx in range(-r, r+1):
                    if max(abs(dx), abs(dy)) != r or not 0 <= x+dx < w:
                        continue
                    q = (y+dy)*w+x+dx
                    dd = dx*dx+dy*dy
                    if not self.blocked[q] and dd < score:
                        best, score = q, dd
            if best >= 0:
                return best
        return -1

    def off_main(self, x, y):
        c = self.nearest_free(self.cell(x, y))
        return c < 0 or self.comp[c] != self.main_comp

    def neighbours(self, c):
        flags = self._adj[c]
        for d, off in enumerate(self._offsets):
            if flags & (1 << d):
                yield c+off

    def line_walkable(self, sx, sy, gx, gy):
        dx, dy = gx-sx, gy-sy
        n, previous = int(math.hypot(dx, dy))+1, self.cell(sx, sy)
        for k in range(1, n+1):
            q = self.cell(sx+dx*k/n, sy+dy*k/n)
            if q != previous:
                if self.blocked[q] or self._single(self.surf[q]-self.surf[previous]) > self._rise_limits[1]:
                    return False
                previous = q
        return True

    def path(self, sx, sy, gx, gy, max_expand=22000, deadline=None):
        goal = self.nearest_free(self.cell(gx, gy))
        job = self._path_job
        def heuristic(c):
            dx, dy = abs(c % self.nnx-goal % self.nnx), abs(c // self.nnx-goal // self.nnx)
            return 2.3*(max(dx, dy)+.4142*min(dx, dy))
        if job is None or job[0] != goal:
            start = self.nearest_free(self.cell(sx, sy))
            if min(start, goal) < 0:
                self.path_pending = False
                return [], False
            job = [goal, [(heuristic(start), 0, start)], {start: 0.},
                   {start: -1}, set(), start, heuristic(start), 0, 0]
        end = self.deadline if deadline is None else deadline
        goal, queue, costs, previous, closed = job[:5]
        found = False
        slice_end = min(max_expand, job[7]+256)
        while queue and job[7] < slice_end:
            if job[7] % 16 == 0 and time.perf_counter() >= end:
                break
            _, _, c = heapq.heappop(queue)
            job[7] += 1
            if c in closed:
                continue
            closed.add(c)
            if c == goal:
                job[5], found = c, True
                break
            h = heuristic(c)
            if h < job[6]:
                job[5], job[6] = c, h
            for q in self.neighbours(c):
                if q in closed:
                    continue
                step = 2 if abs(q-c) in (1, self.nnx) else 2.8284
                clearance = self.clearance[q]
                if clearance < 4:
                    step *= 1+(4-clearance)*.15
                cost = costs[c]+step
                if cost < costs.get(q, math.inf):
                    costs[q], previous[q] = cost, c
                    job[8] += 1
                    heapq.heappush(queue, (cost+heuristic(q), job[8], q))
        self.path_pending = bool(queue) and not found and job[7] < max_expand
        self._path_job = job if self.path_pending else None
        route, c = [], job[5]
        while c >= 0:
            route.append(c)
            c = previous[c]
        route.reverse()
        return route, found

    def escape_plan(self, x, y, deadline=None):
        job = self._escape_job
        if job is None:
            start = self.nearest_free(self.cell(x, y))
            if start < 0:
                self.escape_pending = False
                return (0., 0.), (0., 0.), False
            job = [deque([start]), {start: 0}, -1, math.inf, 0]
        queue, distances = job[:2]
        end = self.deadline if deadline is None else deadline
        slice_end = min(60000, job[4]+256)
        while queue and job[4] < slice_end:
            if job[4] % 16 == 0 and time.perf_counter() >= end:
                break
            c = queue.popleft()
            job[4] += 1
            near = self._main_near[c]
            if near >= 0:
                cx, cy = self.cell_pos(c)
                nx, ny = self.cell_pos(near)
                score = 2*distances[c]+4*math.hypot(cx-nx, cy-ny)
                if score < job[3]:
                    job[2], job[3] = c, score
            for q in self.neighbours(c):
                if q not in distances:
                    distances[q] = distances[c]+1
                    queue.append(q)
        self.escape_pending = bool(queue) and job[4] < 60000
        self._escape_job = job if self.escape_pending else None
        if job[2] < 0:
            return (0., 0.), (0., 0.), False
        launch = self.cell_pos(job[2])
        land = self.cell_pos(self._main_near[job[2]])
        dx, dy = land[0]-launch[0], land[1]-launch[1]
        length = math.hypot(dx, dy)
        if length > .1:
            a, b = land[0]+5*dx/length, land[1]+5*dy/length
            if self.in_bounds(a, b) and self.reachable(a, b):
                land = a, b
        return launch, land, True

    def _build_blocks(self):
        self.bnx, self.bny = (self.nx+7)//8, (self.ny+7)//8
        raw = [-math.inf]*(self.bnx*self.bny)
        for j in range(self.ny):
            row = j*self.nx
            for i in range(self.bnx):
                k = (j//8)*self.bnx+i
                raw[k] = max(raw[k], max(self.ground[row+i*8:row+min(i*8+8, self.nx)]))
        self.blockmax = array("f", raw)
        for j in range(self.bny):
            for i in range(self.bnx):
                self.blockmax[j*self.bnx+i] = max(raw[y*self.bnx+x]
                    for y in range(j, min(j+2, self.bny))
                    for x in range(i, min(i+2, self.bnx)))

    def _ray_prism(self, p, x, y, z, dx, dy, dz):
        lo, hi = 0., 1.
        for origin, change, low, high in ((x, dx, p[2], p[4]),
                                          (y, dy, p[3], p[5]), (z, dz, p[0], p[1])):
            if abs(change) < 1e-9:
                if origin < low or origin > high:
                    return False
            else:
                a, b = (low-origin)/change, (high-origin)/change
                lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
                if lo > hi:
                    return False
        if p[0] <= z <= p[1] and self._inside(p[7], x, y):
            return True
        for ax, ay, bx, by, ex, ey, _ in p[7]:
            den = dx*ey-dy*ex
            if abs(den) < 1e-9:
                continue
            px, py = ax-x, ay-y
            t, u = (px*ey-py*ex)/den, (px*dy-py*dx)/den
            if 0 <= t < 1 and 0 <= u <= 1 and p[0] <= z+dz*t <= p[1]:
                return True
        if abs(dz) > 1e-9:
            t = ((p[1] if dz < 0 else p[0])-z)/dz
            if 0 <= t < 1 and self._inside(p[7], x+dx*t, y+dy*t):
                return True
        return False

    def _terrain_hit(self, x, y, z, dx, dy, dz):
        ground_at = self.ground_at
        if z < ground_at(x, y):
            return True
        horizontal = math.hypot(dx, dy)
        moving = horizontal > 1e-9
        step, t = .5/horizontal if moving else 1., 0.
        floor, infinity = math.floor, math.inf
        x0, y0, width, height = self.x0, self.y0, self.bnx, self.bny
        maxima = self.blockmax
        move_x, move_y = abs(dx) > 1e-9, abs(dy) > 1e-9
        edge_x, edge_y = x0+(8 if dx > 0 else 0), y0+(8 if dy > 0 else 0)
        for _ in range(100001):
            px, py = x+dx*t, y+dy*t
            i, j = floor((px-x0)/8), floor((py-y0)/8)
            end = 1.
            if moving:
                a = (edge_x+i*8-px)/dx if move_x else infinity
                b = (edge_y+j*8-py)/dy if move_y else infinity
                boundary = a if a < b else b
                if boundary < 0:
                    boundary = 0.
                end = t+boundary+.000001
                if end > 1:
                    end = 1.
            low, high = z+dz*t, z+dz*end
            if high < low:
                low = high
            if 0 <= i < width and 0 <= j < height and low > maxima[j*width+i]:
                t = end
            else:
                t += step
                if t > 1:
                    t = 1.
                if z+dz*t < ground_at(x+dx*t, y+dy*t):
                    return True
            if t >= 1:
                return False
        return False

    def clear(self, a, b):
        x, y, z = a
        dx, dy, dz = b[0]-x, b[1]-y, b[2]-z
        i, j = math.floor((x-self.gx0)/16), math.floor((y-self.gy0)/16)
        ei, ej = math.floor((b[0]-self.gx0)/16), math.floor((b[1]-self.gy0)/16)
        sx, sy = 1 if dx > 0 else -1, 1 if dy > 0 else -1
        tx = (self.gx0+(i+(dx > 0))*16-x)/dx if abs(dx) > 1e-9 else math.inf
        ty = (self.gy0+(j+(dy > 0))*16-y)/dy if abs(dy) > 1e-9 else math.inf
        ix, iy = 16/abs(dx) if abs(dx) > 1e-9 else math.inf, 16/abs(dy) if abs(dy) > 1e-9 else math.inf
        seen = set()
        for _ in range(4096):
            if 0 <= i < self.gnx and 0 <= j < self.gny:
                for k in self.bins[j*self.gnx+i]:
                    if k not in seen:
                        seen.add(k)
                        if self._ray_prism(self.prisms[k], x, y, z, dx, dy, dz):
                            return False
            if (i, j) == (ei, ej):
                break
            if tx < ty:
                crossing, tx, i = tx, tx+ix, i+sx
            else:
                crossing, ty, j = ty, ty+iy, j+sy
            if crossing > 1:
                break
        return not self._terrain_hit(x, y, z, dx, dy, dz)

    def exposure(self, x, y):
        z, total = self.walk_at(x, y)+7, 0.
        tops, slabs = self.raster_top, self.raster_slabs
        x0, y0, width = self.x0, self.y0, self.nx
        bx0, bx1, by0, by1 = self.bx0, self.bx1, self.by0, self.by1
        for k in range(24):
            a = k*math.pi/12
            dx, dy, d = math.cos(a), math.sin(a), 2.5
            while d < 200:
                px, py = x+dx*d, y+dy*d
                if not (bx0 < px < bx1 and by0 < py < by1):
                    break
                c = int(py-y0+.5)*width+int(px-x0+.5)
                if z < tops[c]-.05 or any(lo < z < hi for lo, hi in slabs.get(c, ())):
                    break
                d += 2.5
            total += d
        return total/4800



BASE = dict(ghost=True, peek=True, laser_range=85., loot_radius=90.,
            crate_until=150., target_limit=215., hp_weight=60/1400,
            sticky=0., low_bonus=0., fight_loot=0., farm_hp=.7,
            laser_seek=0., laser_up=False, lethal=False, finish=False,
            pursue=0., lose_rule=False)
SQUAD = dict(ghost=False, peek=False, laser_range=120., loot_radius=150.,
             crate_until=1e9, target_limit=240., hp_weight=.2, sticky=120.,
             low_bonus=100., fight_loot=70., farm_hp=.5, laser_seek=240.,
             laser_up=True, lethal=True, finish=True, pursue=1.01,
             lose_rule=True)
UPGRADES = (
    "plating armor gun_damage nanites gun_rate lightning_efficiency "
    "lightning_range laser_damage servos laser_charge gun_mag gun_velocity "
    "gyros lightning_chain reactor capacitor mortar_reload mortar_splash "
    "mortar_velocity sensors jets laser_pierce").split()
LASER_UPGRADES = (
    "plating armor laser_damage laser_charge nanites gun_damage gun_rate "
    "lightning_efficiency lightning_range servos gun_mag gun_velocity gyros "
    "lightning_chain reactor capacitor mortar_reload mortar_splash "
    "mortar_velocity sensors jets laser_pierce").split()
DIRECTIONS = tuple((math.cos(k*math.pi/8), math.sin(k*math.pi/8))
                   for k in range(16))
WORK_SECONDS = .0037
COVER_SLICE = 24


def clamp(value, low, high):
    return min(high, max(low, value))


def gap(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def wrap(value):
    return (value+math.pi) % (2*math.pi)-math.pi


def direction(a, b):
    d = gap(a, b)
    return ((b[0]-a[0])/d, (b[1]-a[1])/d) if d >= 1e-6 else (0., 0.)


class Contact:
    defaults = dict(id=0, kind="", pos=(0., 0., 0.), vel=(0., 0., 0.),
                    aim=(0., 0.), hp=0., max_hp=0., cubes=0,
                    weapons=(), charging=False)

    def __init__(self, record=None):
        self.id, self.kind = -1, "mech"
        self.pos, self.vel, self.aim = (0., 0., 0.), (0., 0., 0.), (0., 0.)
        self.hp = self.max_hp = self.cubes = 0
        self.weapons, self.charging = (), False
        self.seen = self.dist = self.closing = 0.
        self.hit, self.los, self.engage = -100., False, False
        if record is not None:
            self.refresh(record)

    def refresh(self, record):
        for key, default in self.defaults.items():
            setattr(self, key, record.get(key, default))


class Practice:
    def __init__(self, hello, seed):
        self.cfg = hello.get("config") or {}
        self.rng = random.Random(seed)
        self.world = None
        self.last_aim = (0., 0.)
        self.tracks, self.npcs = {}, {}
        self.items = {kind: {} for kind in ("crates", "cubes", "pickups")}
        self.bad = {}
        self.now = 0.
        self.squad = self.not_practice = False
        self.initial_alive, self.kills, self.other_dead = None, 0, 0
        self.p = BASE.copy()
        self.strafe, self.strafe_until = 1, 0.
        self.last_hurt = self.last_threat = -100.
        self.hurt_bearing = self.npc_hurt = self.npc_bearing = 0.
        self.sticky_id, self.sticky_at = 0, 0.
        self.retreat, self.lose_at = False, 0.
        self.loot_id, self.loot_since = -1, 0.
        self.hold_start, self.hold = -1., (0., 0., 0.)
        self.path, self.path_goal, self.path_at, self.path_index = None, (0., 0.), 0., 0
        self.cover_goal, self.cover_at, self.cover_job = None, 0., None
        self.home_goal, self.home_at, self.home_job = None, 0., None
        self.escape_goal, self.escape_at, self.flying = None, 0., False
        self.stuck_at, self.unstuck_until, self.unstuck_dir = 0., 0., (0., 0.)
        self.mode, self.target_id, self.cuts = "idle", None, {}

    def mark_cut(self, name):
        self.cuts[name] = self.cuts.get(name, 0)+1

    def center(self, t, fraction=.5):
        height = (self.cfg["npc"]["height"] if t.kind == "npc" else
                  self.cfg["mech"]["height"]*(1+self.cfg["cubes"]["size_per_cube"]*t.cubes))
        return t.pos[0], t.pos[1], t.pos[2]+height*fraction

    def eye(self, t):
        return (t.pos[0], t.pos[1], t.pos[2]+self.cfg["mech"]["eye_height"]*
                (1+self.cfg["cubes"]["size_per_cube"]*t.cubes))

    def observe(self, obs):
        me, w, now = self.me, self.world, self.now
        muzzle = (*me["pos"][:2], me["pos"][2]+self.st["muzzle_height"])
        eye = (*me["pos"][:2], me["pos"][2]+self.st["eye_height"])
        for record in obs.get("mechs", ()):
            table = self.npcs if record["kind"] == "npc" else self.tracks
            t = table.setdefault(record["id"], Contact())
            t.refresh(record)
            t.seen, t.dist = now, gap(t.pos, me["pos"])
            t.los = w.clear(muzzle, self.center(t))
            if not t.los and t.kind == "mech":
                t.los = w.clear(muzzle, self.center(t, .85))
            if t.dist > 1:
                t.closing = -sum((t.vel[k]-me["vel"][k])*(t.pos[k]-me["pos"][k])
                                 for k in (0, 1))/t.dist
        for table, age in ((self.tracks, 20), (self.npcs, 120)):
            for ident in [ident for ident, t in table.items() if now-t.seen > age]:
                del table[ident]
        for kind, table in self.items.items():
            for item in obs.get(kind, ()):
                table[item["id"]] = (item, now)
            for ident, (item, seen) in list(table.items()):
                p = item["pos"]
                if seen != now and now-seen > .35 and gap(p, me["pos"]) < 40:
                    if w.clear(eye, (p[0], p[1], p[2]+1.5)):
                        del table[ident]
        for event in obs.get("events", ()):
            if event["type"] == "damaged":
                bearing = event.get("bearing")
                if event.get("weapon") == "npc" and bearing is not None:
                    self.npc_hurt, self.npc_bearing = now, bearing
                attacker = event.get("by")
                if attacker is not None:
                    self.last_hurt = now
                    if bearing is not None:
                        self.hurt_bearing = bearing
                    for table in (self.tracks, self.npcs):
                        if attacker in table:
                            table[attacker].hit = now
            elif event["type"] == "kill":
                self.kills += 1
                self.tracks.pop(event.get("target", 0), None)
        if self.initial_alive is None:
            self.initial_alive = obs["alive"]
        unexplained = self.initial_alive-obs["alive"]-self.kills
        self.other_dead = self.other_dead+1 if unexplained > 0 else 0
        self.not_practice |= self.other_dead >= 5
        self.squad = not self.not_practice and now > 20
        self.p = BASE | (SQUAD if self.squad else {})
        z = obs["zone"]
        if self.hold_start != z["shrink_start"] or now <= z["shrink_start"]:
            self.hold = (*z["center"], z["radius"])
            self.hold_start = z["shrink_start"]

    def zone_at(self, z, when):
        start, end = z["shrink_start"], z["shrink_end"]
        if when <= start or end <= start:
            return self.hold
        f = clamp((when-start)/(end-start), 0., 1.)
        future = (*z["next_center"], z["next_radius"])
        return tuple(a+(b-a)*f for a, b in zip(self.hold, future))

    def current_zone(self, z):
        live = (*z["center"], z["radius"])
        if self.now <= z["shrink_start"] or abs(live[2]-self.hold[2]) > .01 or abs(live[0]-self.hold[0]) > .01:
            return live
        return self.zone_at(z, self.now)

    def zone_deadline(self, z, point, pad):
        if gap(point, z["next_center"]) <= z["next_radius"]-pad:
            return math.inf
        for k in range(25):
            when = z["shrink_start"]+(z["shrink_end"]-z["shrink_start"])*k/24
            circle = self.zone_at(z, when)
            if gap(point, circle) > circle[2]-pad:
                return when
        return z["shrink_end"]

    def zone_penalty(self, point):
        z = self.obs["zone"]
        live = self.current_zone(z)
        d, dn = gap(point, live)-live[2], gap(point, z["next_center"])-z["next_radius"]
        result = 150+5*(d+5) if d > -5 else 0.
        if dn > -5:
            result += clamp(1-(z["shrink_start"]-self.now)/25, .1, 1)*(25+.8*(dn+5))
        return result

    def zone_goal(self):
        z, pos = self.obs["zone"], self.me["pos"]
        center, radius = z["next_center"], z["next_radius"]
        if radius <= 30:
            return tuple(center)
        d, r = gap(pos, center), max(0, radius-clamp(.3*radius, 3, 30)-5)
        if d < 1 or d <= r:
            return tuple(pos[:2])
        return tuple(center[k]+(pos[k]-center[k])*r/d for k in (0, 1))

    def targets(self):
        now, me, p = self.now, self.me, self.p
        seen = [self.tracks[k] for k in sorted(self.tracks)
                if now-self.tracks[k].seen <= 2.5]
        target, hidden, best = None, None, math.inf
        for t in seen:
            t.engage = False
            if t.seen != now:
                t.los = False
                continue
            bearing = math.atan2(me["pos"][1]-t.pos[1], me["pos"][0]-t.pos[0])
            aimed = abs(wrap(t.aim[0]-bearing)) < .22
            if p["ghost"]:
                t.engage = (t.dist < 60 or now-t.hit < 4 or
                            aimed and t.charging and t.dist < 120 or
                            t.hp < 350 and t.dist < 120 or self.obs["alive"] <= 2)
            else:
                t.engage = (t.dist < 60 or now-t.hit < 6 or self.late or
                            t.closing > 3 and t.dist < 180 or
                            t.hp < .4*t.max_hp and t.dist < 160 or aimed and t.dist < 190)
            if t.engage and not t.los and t.dist < p["target_limit"]:
                if hidden is None or t.dist < hidden.dist:
                    hidden = t
            if not t.engage or not t.los or t.dist > p["target_limit"]:
                continue
            score = t.dist+p["hp_weight"]*t.hp
            if t.hp <= .3*t.max_hp:
                score -= p["low_bonus"]
            if t.id == self.sticky_id and now-self.sticky_at < 2:
                score -= p["sticky"]
            score -= 40 if now-t.hit < 4 else 0
            score -= 15 if t.closing > 3 else 0
            if score < best:
                best, target = score, t
        if target is not None:
            self.sticky_id, self.sticky_at = target.id, now
        foe = target
        if foe is None and hidden is not None:
            if p["peek"] or hidden.hp < p["pursue"]*hidden.max_hp:
                foe = hidden
        danger = any(t.engage or now-t.hit < 4 for t in seen)
        crowd = sum(t.seen == now and (t.engage or t.los and t.dist < 150) for t in seen)
        if danger or now-self.last_hurt < 3:
            self.last_threat = now
        self.target_id = target.id if target is not None else None
        return seen, target, foe, danger, crowd

    def update_retreat(self, seen, target, crowd):
        health, now = self.health, self.now
        outgunned = (target is not None and "laser" in target.weapons and
                     "laser" not in self.weapons and target.dist > 55 and health < .8)
        swamped = crowd >= 3 or crowd == 2 and health < .65 or outgunned
        if not self.retreat and (health < .38 and now-self.last_threat < 2 or swamped):
            self.retreat, self.cover_at = True, -1.
        if self.retreat and not swamped and (health > .8 or now-self.last_threat > 7 and health > .55):
            self.retreat = False
        if self.p["lose_rule"]:
            count = sum(t.seen == now and t.dist < 160 for t in seen)
            losing = count >= 2 and health < .55 or count >= 3 and health < .8
            if target is not None:
                fraction = target.hp/max(1, target.max_hp)
                if health < .35 and fraction > health+.1:
                    losing = True
                if fraction < .25 and health > .2 and count <= 2:
                    losing = False
            if losing:
                self.lose_at = now
            self.retreat = self.lose_at > 0 and now-self.lose_at < 1.5

    def preferred_range(self, target, finishing=False):
        light = self.weapons.get("lightning")
        radius = 14. if finishing else 85.
        if light is not None and self.me["energy"] > 12:
            radius = 14. if finishing else 28.
        elif "laser" in self.weapons:
            radius = 14. if finishing else self.p["laser_range"]
        if target.kind == "npc":
            return 58.
        if light is None:
            if "lightning" in target.weapons:
                radius = max(radius, 64.)
            if "mortar" in target.weapons:
                radius = max(radius, 80.)
        return radius

    def fight_move(self, target, seen, want_los, finishing=False):
        w, pos, st = self.world, self.me["pos"], self.st
        if self.now >= self.strafe_until:
            if self.rng.random() < .6:
                self.strafe *= -1
            self.strafe_until = self.now+.3+.7*self.rng.random()
        d = gap(pos, target.pos)+1e-9
        sx, sy = -(target.pos[1]-pos[1])/d*self.strafe, (target.pos[0]-pos[0])/d*self.strafe
        cube, cube_distance = None, 40.
        for ident in sorted(self.items["cubes"]):
            point = self.items["cubes"][ident][0]["pos"]
            distance = gap(pos, point)
            if distance < cube_distance and abs(point[2]-pos[2]) < 4:
                cube, cube_distance = point, distance
        preferred, center = self.preferred_range(target, finishing), self.center(target)
        best, movement, blocked = -math.inf, (0., 0.), False
        rings = 2 if self.p["peek"] else 1
        for index in range(-1, 16*rings):
            dx, dy = DIRECTIONS[index % 16] if index >= 0 else (0., 0.)
            radius = 6*(1+index//16) if index >= 0 else 0.
            point = (pos[0]+dx*radius, pos[1]+dy*radius)
            if index >= 0 and (not w.line_walkable(*pos[:2], *point) or not w.free(*point)):
                if index < 16 and dx*sx+dy*sy > .9:
                    blocked = True
                continue
            height = w.walk_at(*point)
            los = w.clear((*point, height+st["muzzle_height"]), center)
            score = -1.1*abs(gap(point, target.pos)-preferred)-.4*radius
            score += 45*want_los if los else 0.
            if self.p["peek"] and 0 <= index < 16 and los == (want_los > 0):
                for qx, qy in DIRECTIONS[::2]:
                    q = point[0]+7*qx, point[1]+7*qy
                    if w.free(*q) and w.clear((*q, w.walk_at(*q)+st["muzzle_height"]), center) != los:
                        score += 8
                        break
            body = (*point, height+st["height"]*.6)
            for enemy in seen:
                if enemy is not target and gap(enemy.pos, point) <= 170 and w.clear(self.eye(enemy), body):
                    score -= 30
            score -= self.zone_penalty(point)
            if cube is not None:
                score += 1.5*(cube_distance-gap(point, cube))
            clearance = w.clearance[w.cell(*point)]
            if clearance < 4:
                score -= (4-clearance)*2.5
            if want_los > 0:
                score += 9*(dx*sx+dy*sy)
            if index < 0:
                score += 6 if want_los < 0 and not los else -8
            if score > best:
                best, movement = score, (dx, dy)
            if index >= 0 and time.perf_counter() > self.deadline:
                self.mark_cut("fight")
                break
        if blocked:
            self.strafe *= -1
            self.strafe_until = self.now+.5
        return movement

    def travel(self, goal):
        pos, w = self.me["pos"], self.world
        if gap(pos, goal) < .8:
            return 0., 0.
        direct = direction(pos, goal)
        if pos[2]-w.ground_at(*pos[:2]) > 3 and w.obstacle_at(*pos[:2]):
            return direct
        if gap(pos, goal) < 45 and w.line_walkable(*pos[:2], *goal):
            return direct
        new_goal = (self.path is None or gap(goal, self.path_goal) > 5 or
                    not w.path_pending and self.now-self.path_at > 2.5)
        if new_goal or w.path_pending:
            if new_goal:
                w.reset_path()
                self.path_goal, self.path_at, self.path_index = tuple(goal), self.now, 0
            self.path, _ = w.path(*pos[:2], *self.path_goal, deadline=self.deadline)
            if not w.path_pending:
                self.path_at = self.now
        if not self.path:
            return direct
        index = min(self.path_index, len(self.path)-1)
        index = min(range(index, min(index+10, len(self.path))),
                    key=lambda i: gap(pos, w.cell_pos(self.path[i])))
        self.path_index = index
        if gap(pos, w.cell_pos(self.path[index])) > 12:
            self.path = None
            return direct
        for i in range(min(index+14, len(self.path)-1), index, -1):
            point = w.cell_pos(self.path[i])
            if w.line_walkable(*pos[:2], *point):
                if i == len(self.path)-1 and gap(point, goal) < 4 and w.line_walkable(*pos[:2], *goal):
                    return direct
                return direction(pos, point)
        return direction(pos, w.cell_pos(self.path[index+1])) if index+1 < len(self.path) else direct

    def escape(self):
        pos, w, me = self.me["pos"], self.world, self.me
        jump = False
        if me["grounded"]:
            if (pos[2]-w.ground_at(*pos[:2]) > 3 and w.obstacle_at(*pos[:2])) or not w.off_main(*pos[:2]):
                self.escape_goal, self.flying = None, False
                w.reset_escape()
                return None
            self.flying = False
            if self.escape_goal is None or self.now-self.escape_at > 6 or w.escape_pending:
                if not w.escape_pending or self.now-self.escape_at > 6:
                    w.reset_escape()
                launch, land, valid = w.escape_plan(*pos[:2], deadline=self.deadline)
                self.escape_at = self.now
                self.escape_goal = (launch, land) if valid else None
                if not valid:
                    return None
            launch, land = self.escape_goal
            if gap(pos, launch) > 2.5:
                return self.travel(launch), False, False
            if me["energy"] < min(70, .7*me["max_energy"]):
                return (0., 0.), False, False
            self.flying, jump = True, True
        elif not self.flying:
            return None
        land = self.escape_goal[1]
        distance = gap(pos, land)
        if distance < 1.5:
            return (0., 0.), False, jump
        dx, dy = direction(pos, land)
        top = max(w.top_at(pos[0]+dx*k, pos[1]+dy*k)
                  for k in range(math.floor(min(distance, 30))+1))
        return (dx, dy), pos[2] < top+2.5 and me["energy"] > 1, jump

    def hidden(self, point, eyes):
        z = self.world.walk_at(*point)
        for eye in eyes:
            for fraction in (1., .5):
                if self.world.clear(eye, (*point, z+self.st["height"]*fraction)):
                    return False
        return True

    def cover(self, seen):
        pos, w = self.me["pos"], self.world
        threats = [t for t in seen if gap(t.pos, pos) < 230]
        if not threats:
            return None
        if len(threats) > 4:
            threats.sort(key=lambda t: gap(t.pos, pos))
            threats = threats[:4]
        eyes = tuple(self.eye(t) for t in threats)
        if self.cover_job is None and self.cover_goal is not None and self.now-self.cover_at < .4:
            return (0., 0.) if gap(pos, self.cover_goal) < 1.5 else self.travel(self.cover_goal)
        if self.hidden(pos[:2], eyes) and self.zone_penalty(pos) == 0:
            self.cover_goal, self.cover_at, self.cover_job = tuple(pos[:2]), self.now, None
            return 0., 0.
        signature = tuple(t.id for t in threats)
        job = self.cover_job
        if job is None or job["ids"] != signature or self.now-job["at"] > 3:
            start = w.nearest_free(w.cell(*pos[:2]))
            if start < 0:
                return None
            job = dict(queue=deque([(start, 0)]), visited={start}, checked=0,
                       best=None, score=math.inf, eyes=eyes,
                       positions=tuple(tuple(t.pos) for t in threats), ids=signature, at=self.now)
            self.cover_job = job
        count = 0
        while job["queue"] and job["checked"] < 350 and count < COVER_SLICE:
            if time.perf_counter() > self.deadline:
                self.mark_cut("cover")
                break
            cell, steps = job["queue"].popleft()
            if steps > 50 or job["best"] is not None and steps*2 > job["score"]+30:
                job["queue"].clear()
                break
            if (cell % w.nnx+cell//w.nnx) % 2 == 0 and steps > 0:
                point = w.cell_pos(cell)
                job["checked"] += 1
                count += 1
                if self.hidden(point, job["eyes"]):
                    near = min(gap(point, p) for p in job["positions"])
                    score = steps*2+self.zone_penalty(point)-.25*min(near, 80)
                    if score < job["score"]:
                        job["score"], job["best"] = score, point
            for other in w.neighbours(cell):
                if other not in job["visited"]:
                    job["visited"].add(other)
                    job["queue"].append((other, steps+1))
        complete = not job["queue"] or job["checked"] >= 350
        if complete:
            self.cover_job, self.cover_at = None, self.now
        goal = job["best"]
        
        if goal is not None and self.hidden(goal, eyes):
            self.cover_goal = goal
            return (0., 0.) if gap(pos, goal) < 1.5 else self.travel(goal)
        self.cover_goal = None
        return None

    def shell_dodge(self):
        gravity = self.cfg["weapons"]["mortar"].get("gravity", 0) or 22
        if gravity < 0:
            gravity = 22
        radius = self.cfg["weapons"]["mortar"]["splash_radius"]+self.st["radius"]+2
        me = self.me["pos"]
        for shell in self.obs.get("projectiles", ()):
            if shell["kind"] != "mortar":
                continue
            x, y, z = shell["pos"]
            vx, vy, vz = shell["vel"]
            elapsed, step = 0., 0
            while elapsed < 4:
                x, y, z, vz = x+vx*.05, y+vy*.05, z+vz*.05, vz-gravity*.05
                if self.world.solid(x, y, z):
                    distance = math.hypot(x-me[0], y-me[1])
                    if distance < radius and elapsed < 2.5:
                        dx, dy = me[0]-x, me[1]-y
                        if distance < .5:
                            dx, dy = -vy, vx
                            distance = math.hypot(dx, dy)
                        dx, dy = dx/distance, dy/distance
                        for angle in (0., .7, -.7, 1.4, -1.4):
                            c, s = math.cos(angle), math.sin(angle)
                            ux, uy = dx*c-dy*s, dx*s+dy*c
                            if self.world.line_walkable(*me[:2], me[0]+6*ux, me[1]+6*uy):
                                return ux, uy
                    break
                if step % 16 == 15 and time.perf_counter() > self.deadline:
                    self.mark_cut("shell")
                    return None
                elapsed, step = elapsed+.05, step+1
        return None

    def dodge(self):
        pos, st = self.me["pos"], self.st
        body, reach = (pos[0], pos[1], pos[2]+.56*st["height"]), st["radius"]+1.1
        dx = dy = 0.
        laser = False
        for projectile in self.obs.get("projectiles", ()):
            if projectile["kind"] == "mortar":
                continue
            p, v = projectile["pos"], projectile["vel"]
            speed2 = sum(a*a for a in v)
            if speed2 < 1:
                continue
            when = sum((body[k]-p[k])*v[k] for k in range(3))/speed2
            if not 0 < when <= .7:
                continue
            mx, my = p[0]+v[0]*when-body[0], p[1]+v[1]*when-body[1]
            horizontal = math.hypot(v[0], v[1])
            if math.hypot(mx, my) < reach and horizontal >= 1:
                px, py = -v[1]/horizontal, v[0]/horizontal
                if px*mx+py*my > 0:
                    px, py = -px, -py
                dx, dy = dx+px, dy+py
        for record in self.obs.get("mechs", ()):
            if record["kind"] != "mech" or not record.get("charging", False):
                continue
            p = record["pos"]
            toward = math.atan2(pos[1]-p[1], pos[0]-p[0])
            if abs(wrap(record["aim"][0]-toward)) <= .15:
                angle = toward+math.pi/2*self.strafe
                dx, dy, laser = dx+1.5*math.cos(angle), dy+1.5*math.sin(angle), True
        length = math.hypot(dx, dy)
        return ((dx/length, dy/length), laser) if length > .01 else ((0., 0.), False)

    def want_pickup(self, kind):
        slots = self.me["weapons"]
        if kind == "gun":
            return bool(slots) and slots[0] is None
        if kind in self.weapons or kind == "mortar":
            return False
        rank = {"laser": 4, "lightning": 3, "mortar": 1}
        current = rank.get(slots[1]["kind"], 0) if len(slots) > 1 and slots[1] else 0
        return rank.get(kind, 0) > current

    def choose_loot(self, danger):
        pos, p, now, w = self.me["pos"], self.p, self.now, self.world
        slots, cap = self.me["weapons"], self.cfg["cubes"]["stat_cap"]
        cube_value = 25 if self.me["cubes"] >= cap else 75
        choices = []
        for ident in sorted(self.items["pickups"]):
            item = self.items["pickups"][ident][0]
            seek = item["kind"] == "laser" and p["laser_seek"] > p["loot_radius"]
            radius = p["laser_seek"] if seek else p["loot_radius"]
            if self.want_pickup(item["kind"]) and gap(pos, item["pos"]) < radius:
                value = 130 if len(slots) > 1 and slots[1] is None else 60
                choices.append(("pickup", ident, item["pos"], max(value, 150) if seek else value))
        for ident in sorted(self.items["cubes"]):
            item = self.items["cubes"][ident][0]
            if gap(pos, item["pos"]) < max(60, .7*p["loot_radius"]):
                choices.append(("cube", ident, item["pos"], cube_value))
        if self.health > p["farm_hp"] and not danger and now < p["crate_until"]:
            for ident in sorted(self.items["crates"]):
                item = self.items["crates"][ident][0]
                if gap(pos, item["pos"]) < p["loot_radius"]:
                    choices.append(("crate", ident, item["pos"], .6*cube_value))
            if self.me["cubes"] < cap:
                for ident in sorted(self.npcs):
                    npc = self.npcs[ident]
                    if now-npc.seen < 12 and gap(pos, npc.pos) < p["loot_radius"]:
                        choices.append(("npc", ident, npc.pos, 85))
        circle, best, utility = self.current_zone(self.obs["zone"]), None, 0.
        for choice in choices:
            kind, ident, point, value = choice
            distance = gap(pos, point)
            if (self.bad.get(ident, -math.inf) > now or distance > 260 or
                    gap(point, circle) > circle[2]-6 or
                    now+distance*1.4/self.st["walk_speed"]+5 > self.zone_deadline(self.obs["zone"], point, 6) or
                    point[2]-w.ground_at(*point[:2]) > 3.2):
                continue
            cell = w.nearest_free(w.cell(*point[:2]))
            if cell < 0 or w.comp[cell] != w.main_comp:
                continue
            score = value/(distance+18)*(1.35 if ident == self.loot_id else 1)
            if score > utility:
                best, utility = choice, score
        if best is None:
            self.loot_id = -1
        elif best[1] != self.loot_id:
            self.loot_id, self.loot_since = best[1], now
        elif now-self.loot_since > 30:
            self.bad[best[1]], self.loot_id, best = now+60, -1, None
        return best

    def home(self):
        z, pos = self.obs["zone"], self.me["pos"]
        signature = (*z["next_center"], z["next_radius"])
        outside = self.home_goal is None or gap(self.home_goal, z["next_center"]) > .8*z["next_radius"]
        job = self.home_job
        if job is not None and job["zone"] != signature:
            self.home_job, job = None, None
        if job is None and (outside or self.now-self.home_at > 12):
            points = []
            for _ in range(40):
                angle, radius = self.rng.random()*2*math.pi, math.sqrt(self.rng.random())*.7*z["next_radius"]
                point = z["next_center"][0]+math.cos(angle)*radius, z["next_center"][1]+math.sin(angle)*radius
                if self.world.in_bounds(*point) and self.world.reachable(*point):
                    points.append(point)
            job = dict(points=deque(points), zone=signature, origin=tuple(pos),
                       enemies=[tuple(t.pos) for t in self.tracks.values() if self.now-t.seen < 20],
                       drops=[tuple(d["pos"]) for d in self.obs.get("drops", ())],
                       best=None, score=math.inf, old=self.home_goal, outside=outside)
            self.home_at, self.home_job = self.now, job
        if job is None:
            return self.home_goal

        def cost(point):
            crowd = sum(max(0, 80-gap(point, p))/80 for p in job["enemies"])
            crowd += sum(max(0, 60-gap(point, p))/60 for p in job["drops"])
            edge = gap(point, job["zone"])/max(30, job["zone"][2])
            return 120*self.world.exposure(*point)+.25*gap(point, job["origin"])+40*crowd+10*edge

        
        if job["points"] and time.perf_counter() <= self.deadline:
            point = job["points"].popleft()
            value = cost(point)
            if value < job["score"]:
                job["best"], job["score"] = point, value
            if job["outside"]:
                self.home_goal = job["best"]
        if not job["points"]:
            if job["best"] is not None and (job["outside"] or job["score"] < cost(job["old"])-15):
                self.home_goal = job["best"]
            self.home_job = None
        return self.home_goal

    def movement(self, seen, target, foe, danger, crowd):
        me, pos, now = self.me, self.me["pos"], self.now
        energy, boost, jump = me["energy"], False, False
        move, mode, farm, crate = (0., 0.), "idle", None, None
        zone_goal = self.zone_goal()
        zone_distance = gap(pos, zone_goal)
        need = zone_distance*1.45/self.st["walk_speed"]+4
        deadline = self.zone_deadline(self.obs["zone"], pos, 8)
        must = not me["in_zone"] or now+need+3 >= deadline
        should = now+need+14 >= deadline
        finishing = target is not None and target.dist < 120 and (target.hp < 200 or target.hp < .5*me["hp"])
        escape = self.escape()
        if escape is not None:
            move, boost, jump = escape
            mode = "escape"
        elif now < self.unstuck_until:
            move, mode = self.unstuck_dir, "unstuck"
        else:
            shell = self.shell_dodge()
            if shell is not None:
                move, boost, mode = shell, energy > 15, "dodge"
            elif must and zone_distance > 2:
                move, mode = self.travel(zone_goal), "zone"
                boost = (not me["in_zone"] or now+need >= deadline) and energy > 5
            elif self.retreat and not finishing and not self.late:
                cover = self.cover(seen)
                if cover is not None:
                    move, boost, mode = cover, energy > 10, "cover"
                elif target is not None:
                    move, mode = self.fight_move(target, seen, 1.), "cornered"
                else:
                    move, mode = self.travel(zone_goal), "flee"
                    if self.npc_hurt > 0 and now-self.npc_hurt < 3 and move == (0., 0.):
                        side = -1 if now % 3 > 1.5 else 1
                        move = -math.sin(self.npc_bearing)*side, math.cos(self.npc_bearing)*side
            else:
                cover = None
                if target is None and now-self.last_hurt < 2.5 and not self.late and self.p["ghost"]:
                    ghost = Contact({"id": -1, "pos": (pos[0]+80*math.cos(self.hurt_bearing),
                                                          pos[1]+80*math.sin(self.hurt_bearing), pos[2])})
                    cover = self.cover([ghost]+seen)
                if cover is not None:
                    move, boost, mode = cover, energy > 30, "cover"
                elif foe is not None:
                    gun, laser, light = (self.weapons.get(k) for k in ("gun", "laser", "lightning"))
                    ready = gun is not None and gun.get("ammo", 0) > 0 and gun.get("reload", 0) <= .25 and foe.dist <= gun["stats"]["range"]-10
                    hot = laser is not None and laser.get("charge", 0) >= laser["stats"]["charge"]-.3 and foe.dist <= laser["stats"]["range"]-5
                    ready |= hot or (light is not None and foe.dist <= light["stats"]["range"]+6 and energy >= 3*light["stats"]["energy"])
                    ready |= not self.p["peek"] and (light is not None or laser is not None)
                    want = 1. if ready else -1.
                    if self.p["peek"] and not hot:
                        for enemy in seen:
                            bearing = math.atan2(pos[1]-enemy.pos[1], pos[0]-enemy.pos[0])
                            if enemy.seen == now and enemy.charging and abs(wrap(enemy.aim[0]-bearing)) < .3:
                                want = -1.6
                    finish_range = self.p["finish"] and foe.hp < .38*foe.max_hp and self.health > .42 and crowd <= 2
                    move, mode = self.fight_move(foe, seen, want, finish_range), "fight"
                    boost = light is not None and foe.dist > 50 and energy > 55 and want > 0
                    radius = self.p["fight_loot"]*(.57 if self.health <= .5 else 1)
                    cube = None
                    for ident in sorted(self.items["cubes"]):
                        point = self.items["cubes"][ident][0]["pos"]
                        distance = gap(pos, point)
                        if distance < radius:
                            cube, radius = point, distance
                    if cube is not None:
                        move, mode = self.travel(cube[:2]), "fight:cube"
                elif should and zone_distance > 2:
                    move, mode = self.travel(zone_goal), "zone"
                else:
                    choice = self.choose_loot(danger)
                    if choice is not None:
                        kind, ident, point, _ = choice
                        mode = "loot:"+kind
                        if kind == "npc":
                            npc = self.npcs.get(ident)
                            if npc is not None and now-npc.seen < 1 and npc.los and npc.dist < 75:
                                farm, move = npc, self.fight_move(npc, seen, 1.)
                            else:
                                move = self.travel(point[:2])
                        elif kind == "crate":
                            center = (point[0], point[1], point[2]+self.cfg["crates"]["height"]*.5)
                            muzzle = (pos[0], pos[1], pos[2]+self.st["muzzle_height"])
                            distance = gap(pos, point)
                            if distance < 50 and self.world.clear(muzzle, center):
                                crate = center
                                if distance < 12:
                                    move = (pos[0]-point[0])/max(distance, .1), (pos[1]-point[1])/max(distance, .1)
                            else:
                                move = self.travel(point[:2])
                        else:
                            move = self.travel(point[:2])
                    elif zone_distance > 3 and (not self.p["ghost"] or self.obs["zone"]["next_radius"] <= 30):
                        move, mode = self.travel(zone_goal), "zonewalk"
                    elif self.p["ghost"]:
                        goal = self.home()
                        if goal is not None and gap(pos, goal) > 3:
                            move, mode = self.travel(goal), "home"
                            if not danger and now-self.last_hurt > 6:
                                quiet = min(1, 4.6/self.st["walk_speed"])
                                move = tuple(v*quiet for v in move)
        if mode not in ("escape", "unstuck"):
            dodge, laser = self.dodge()
            if dodge != (0., 0.):
                move = tuple(.4*a+.9*b for a, b in zip(move, dodge))
                length = math.hypot(*move)
                if length > 1:
                    move = tuple(v/length for v in move)
                if laser and energy > 25:
                    boost = True
        if mode == "escape":
            self.stuck_at = -1.
        elif move != (0., 0.) and math.hypot(*me["vel"][:2]) < 1.2 and me["grounded"]:
            if self.stuck_at < 0:
                self.stuck_at = now
            elif now-self.stuck_at > .7:
                angle = self.rng.random()*2*math.pi
                self.unstuck_dir = math.cos(angle), math.sin(angle)
                self.unstuck_until, self.stuck_at, self.path, jump = now+.5, -1., None, True
                self.world.reset_path()
        else:
            self.stuck_at = -1.
        self.mode = mode
        return move, bool(boost and move != (0., 0.)), jump, farm, crate

    @staticmethod
    def gun_lead(muzzle, point, velocity, speed):
        speed = speed if speed > 0 else 252.
        flight = 0.
        for _ in range(4):
            duration = .075+flight
            x, y = point[0]+velocity[0]*duration, point[1]+velocity[1]*duration
            z = point[2]+(velocity[2]*duration*.5 if abs(velocity[2]) >= .5 else 0)
            flight = max(0., math.dist(muzzle, (x, y, z))-3)/speed
        return math.atan2(y-muzzle[1], x-muzzle[0]), math.atan2(z-muzzle[2], math.hypot(x-muzzle[0], y-muzzle[1]))

    def mortar_aim(self, tube, foot, velocity, weapon):
        speed, gravity = weapon["stats"]["speed"], weapon["stats"]["gravity"]
        if speed <= 0 or gravity <= 0:
            return None
        flight = 0.
        for _ in range(3):
            x, y = foot[0]+velocity[0]*(.075+flight), foot[1]+velocity[1]*(.075+flight)
            horizontal, vertical = gap(tube, (x, y)), foot[2]-tube[2]
            discriminant = speed**4-gravity*(gravity*horizontal**2+2*vertical*speed**2)
            if discriminant < 0 or horizontal < 1:
                return None
            pitch = math.atan((speed**2-math.sqrt(discriminant))/(gravity*horizontal))
            yaw = math.atan2(y-tube[1], x-tube[0])
            flight = horizontal/(speed*math.cos(pitch))
        if not self.st["min_pitch"] <= pitch <= self.st["max_pitch"]:
            return None
        t = .1
        while t < flight*.9:
            distance = speed*math.cos(pitch)*t
            if self.world.solid(tube[0]+math.cos(yaw)*distance, tube[1]+math.sin(yaw)*distance,
                                tube[2]+speed*math.sin(pitch)*t-.5*gravity*t*t):
                return None
            t += .1
        return yaw, pitch

    def shooting(self, seen, target, farm, crate, move, action):
        me, pos, st, now = self.me, self.me["pos"], self.st, self.now
        gun = self.weapons.get("gun")
        muzzle = (pos[0]+me["vel"][0]*.075, pos[1]+me["vel"][1]*.075, pos[2]+st["muzzle_height"])
        defensive = False
        if target is None and self.npc_hurt > 0 and now-self.npc_hurt < 3:
            best = .7
            for ident in sorted(self.npcs):
                npc = self.npcs[ident]
                if now-npc.seen > .5 or not npc.los or npc.dist > 150:
                    continue
                angle = abs(wrap(math.atan2(npc.pos[1]-pos[1], npc.pos[0]-pos[0])-self.npc_bearing))
                if now-npc.hit < 3:
                    angle = 0.
                if angle < best:
                    best, farm, crate, defensive = angle, npc, None, True
        point, velocity, radius, height = None, (0., 0., 0.), 0., 0.
        is_mech = target is not None
        if is_mech:
            scale = 1+self.cfg["cubes"]["size_per_cube"]*target.cubes
            radius, height = self.cfg["mech"]["radius"]*scale, self.cfg["mech"]["height"]*scale
            point, velocity = self.center(target), target.vel
            if not self.world.clear(muzzle, point):
                point = self.center(target, .85)
        elif farm is not None:
            radius, height = self.cfg["npc"]["radius"], self.cfg["npc"]["height"]
            point, velocity = self.center(farm), farm.vel
        elif crate is not None:
            radius, height, point = self.cfg["crates"]["radius"], self.cfg["crates"]["height"], crate
        if not is_mech and (self.retreat or self.health < .5) and not defensive:
            point = None
        aim = (me["aim"][0], 0.)
        if point is not None:
            distance = gap(point, pos)
            direct = (point[0]+velocity[0]*.125, point[1]+velocity[1]*.125, point[2])
            direct_aim = (math.atan2(direct[1]-muzzle[1], direct[0]-muzzle[0]),
                          math.atan2(direct[2]-muzzle[2], gap(direct, muzzle)))
            lead = self.gun_lead(muzzle, point, velocity, gun["stats"].get("speed", 0)) if gun is not None else direct_aim
            aim = lead
            gun_range = gun is not None and distance <= .96*gun["stats"]["range"]
            yaw_tol, pitch_tol = math.atan2(.75*radius, max(1, distance)), math.atan2(.4*height, max(1, distance))
            yaw_error = abs(wrap(direct_aim[0]-me["aim"][0]))
            pitch_error = abs(direct_aim[1]-me["aim"][1])
            aligned = yaw_error < .9*yaw_tol and pitch_error < pitch_tol
            for slot, weapon in enumerate(me["weapons"][:2]):
                if weapon is None:
                    continue
                kind, stats = weapon["kind"], weapon["stats"]
                if kind == "gun":
                    ey = max(0, abs(wrap(lead[0]-me["aim"][0]))-st["turn_rate"]*.05)
                    ep = max(0, abs(lead[1]-me["aim"][1])-st["pitch_rate"]*.05)
                    action["fire"][slot] = bool(gun_range and weapon.get("ammo", 0) > 0 and weapon.get("reload", 0) <= 0 and ey < yaw_tol and ep < pitch_tol)
                elif kind == "lightning":
                    action["fire"][slot] = bool(distance < stats["range"]-1.5 and yaw_error < math.radians(stats["cone_deg"])*.5-.05 and me["energy"] >= stats["energy"])
                elif kind == "laser" and is_mech and distance <= .97*stats["range"]:
                    charge, full = weapon.get("charge", 0), stats["charge"]
                    lethal = False
                    if self.p["lethal"] and stats["min_charge"] <= charge < full-.051:
                        damage = stats["damage"]*(stats["min_frac"]+(1-stats["min_frac"])*charge/full)
                        damage *= 1+self.cfg["cubes"]["damage_per_cube"]*min(me["cubes"], self.cfg["cubes"]["stat_cap"])
                        if "mortar" in target.weapons:
                            damage *= 1+stats["cookoff"]
                        lethal = .8*damage >= target.hp and aligned
                    if lethal:
                        aim = direct_aim
                    elif charge < full-.051:
                        action["fire"][slot] = True
                        if charge > full*.45:
                            aim = direct_aim
                    else:
                        aim, action["fire"][slot] = direct_aim, not aligned
                elif kind == "mortar" and is_mech and weapon.get("cooldown", 0) <= .25 and 16 <= distance <= 200:
                    tube = (muzzle[0], muzzle[1], pos[2]+st["height"]+.5)
                    foot = (point[0], point[1], point[2]-.5*height)
                    lob = self.mortar_aim(tube, foot, velocity, weapon)
                    if lob is not None:
                        if gun is None or gun.get("reload", 0) > 0 or gun.get("ammo", 0) == 0 or not gun_range:
                            aim = lob
                        ey = max(0, abs(wrap(lob[0]-me["aim"][0]))-st["turn_rate"]*.05)
                        ep = max(0, abs(lob[1]-me["aim"][1])-st["pitch_rate"]*.05)
                        action["fire"][slot] = ey < .04 and ep < .03
        else:
            watch = min((t for t in seen if t.engage or now-t.hit < 6), key=lambda t: t.dist, default=None)
            if watch is not None:
                aim = math.atan2(watch.pos[1]-pos[1], watch.pos[0]-pos[0]), 0.
            elif self.npc_hurt > 0 and now-self.npc_hurt < 2.5:
                aim = self.npc_bearing, 0.
            elif now-self.last_hurt < 2.5:
                aim = self.hurt_bearing, 0.
            elif move != (0., 0.):
                aim = math.atan2(move[1], move[0])+1.15*math.sin(now*1.3), 0.
            else:
                aim = me["aim"][0]+.35, 0.
        action["aim"] = [aim[0], clamp(aim[1], st["min_pitch"], st["max_pitch"])]
        if gun is not None and gun.get("reload", 0) <= 0 and gun.get("ammo", 0) < gun["stats"]["mag"]:
            action["reload"] = (target is None and farm is None and crate is None and
                                (gun.get("ammo", 0) <= gun["stats"]["mag"]*.6 or now-self.last_threat > 3))

    def step(self, obs):
        self.deadline = time.perf_counter()+WORK_SECONDS
        self.world.begin_tick(self.deadline)
        self.obs, self.me, self.now = obs, obs["self"], obs["t"]
        self.st = self.me.get("stats") or {}
        if self.st.get("radius", 0) == 0:
            self.st = self.cfg["mech"]
        self.health = self.me["hp"]/max(1, self.me["max_hp"])
        self.weapons = {}
        for weapon in self.me["weapons"]:
            if weapon is not None:
                self.weapons.setdefault(weapon["kind"], weapon)
        self.late = obs["zone"]["next_radius"] <= 70 or obs["alive"] <= 3
        self.observe(obs)
        seen, target, foe, danger, crowd = self.targets()
        self.update_retreat(seen, target, crowd)
        move, boost, jump, farm, crate = self.movement(seen, target, foe, danger, crowd)
        action = dict(tick=obs["tick"], move=list(move), boost=boost, jump=jump,
                      fire=[False, False], reload=False)
        self.shooting(seen, target, farm, crate, move, action)
        if target is None and foe is not None:
            for slot, weapon in enumerate(self.me["weapons"][:2]):
                if weapon is not None and weapon["kind"] == "laser":
                    stats = weapon["stats"]
                    if (weapon.get("cooldown", 0) <= .05 and foe.dist < stats["range"] and
                            weapon.get("charge", 0) < stats["charge"]+stats["hold_s"]-.35):
                        action["fire"][slot] = True
        offer = obs.get("offer")
        if offer and offer.get("choices"):
            order = LASER_UPGRADES if self.p["laser_up"] else UPGRADES
            ranks = {name: rank for rank, name in enumerate(order)}
            action["pick"] = min(range(len(offer["choices"])), key=lambda i: ranks.get(offer["choices"][i]["id"], len(order)))
        slots, pos = self.me["weapons"], self.me["pos"]
        for item in obs.get("pickups", ()):
            if gap(pos, item["pos"]) > self.cfg["loot"]["pickup_radius"]-.3 or abs(item["pos"][2]-pos[2]) > 3.6 or not self.want_pickup(item["kind"]):
                continue
            if len(slots) > 1 and slots[0] is not None and slots[1] is not None:
                if slots[1]["kind"] == "laser" and slots[1].get("charge", 0) > 0:
                    break
                action["drop"] = 1
            action["take"] = item["id"]
            break
        return action


    def load_map(self, data=None, terrain_bytes=None):
        self.world = World(data, terrain_bytes)

    @staticmethod
    def _validate(action, tick):
        if not isinstance(action, dict) or action.get("tick") != tick:
            raise ValueError("invalid practice3 action or tick")
        for field in ("move", "aim"):
            values = action[field]
            if len(values) != 2 or not all(type(v) in (int, float) and math.isfinite(v) for v in values):
                raise ValueError("invalid practice3 vector")
        if math.hypot(*action["move"]) > 1.00000001:
            raise ValueError("invalid practice3 movement")
        if len(action["fire"]) != 2 or any(type(v) is not bool for v in action["fire"]):
            raise ValueError("invalid practice3 triggers")
        for field in ("boost", "jump", "reload"):
            if type(action[field]) is not bool:
                raise ValueError("invalid practice3 flag")
        for field in ("pick", "take", "drop"):
            if field in action and type(action[field]) is not int:
                raise ValueError("invalid practice3 selection")
        return action

    def act(self, obs):
        if self.world is None:
            raise RuntimeError("practice3 map unavailable")
        action = self._validate(self.step(obs), obs["tick"])
        self.last_aim = action["aim"]
        return action
