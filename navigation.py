"""Bounded static-map A* and acceleration-aware local control (standard library)."""
from __future__ import annotations

import heapq
import math
import os
import time
from navigation_cache import get_graph
from body_stats import effective_mech_stats

_DIRECTION_BITS={(1,0):0,(-1,0):1,(0,1):2,(0,-1):3,(1,1):4,(-1,1):5,(1,-1):6,(-1,-1):7}


def unit(dx, dy):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else (0.0, 0.0)


class Navigator:
    """Lazy coarse routing. Failed/unfinished routes never authorize unsafe movement."""

    def __init__(self, arena, cell=7.0):
        self.arena = arena
        self.cell = cell
        self.path = []
        self.goal = None
        self.goal_region = None
        self._region_zero = False
        self.search = None
        self.last_plan = -100.0
        self.edge_cache = {}
        self.shape = None
        self.expansions = 0
        self.static_cache = os.environ.get('KANYARAASI_NAV_CACHE','off')=='on'
        self._map_identity=tuple(getattr(arena,name,'') for name in ('world_sha256','terrain_sha256','geometry_sha256'))
        self._graph_key=None
        self._graph=None
        self.static_hits=0

    def _key(self, p):
        return round(p[0] / self.cell), round(p[1] / self.cell)

    def _point(self, key):
        x, y = key[0] * self.cell, key[1] * self.cell
        return (x, y, self.arena.terrain_height(x, y))

    def _clear(self, a, b, stats, grounded=True):
        return self.arena.move_clear(a, b, stats['radius'], stats['height'],
                                     stats['step_up'], stats['max_slope_deg'], grounded=grounded)

    def _edge(self, a, b, stats):
        if (self.static_cache and self.shape is not None
                and tuple(stats.get(name) for name in ('radius','height','step_up','max_slope_deg'))==self.shape):
            graph_key=(self.cell,self.shape)
            if graph_key!=self._graph_key:
                self._graph=get_graph(self._map_identity,self.cell,self.shape)
                self._graph_key=graph_key
            direction=_DIRECTION_BITS.get((b[0]-a[0],b[1]-a[1]))
            if self._graph is not None and direction is not None:
                xlo,ylo,nx,ny,data=self._graph
                x,y=a[0]-xlo,a[1]-ylo
                self.static_hits+=1
                return 0<=x<nx and 0<=y<ny and bool(data[y*nx+x]&(1<<direction))
        key = (a, b)
        cached = self.edge_cache.get(key)
        if cached is None:
            cached = self._clear(self._point(a), self._point(b), stats)
            if len(self.edge_cache) > 18000:
                self.edge_cache.clear()
            self.edge_cache[key] = cached
        return cached

    def waypoint(self, pos, goal, stats, now, budget_ms=3.0, goal_region=None):
        if not self.arena.available:
            return goal
        shape = tuple(float(stats[k]) for k in ('radius', 'height', 'step_up', 'max_slope_deg'))
        if shape != self.shape:
            self.edge_cache.clear()
            self.path = []
            self.search = None
            self.shape = shape
        target = (goal[0], goal[1], self.arena.terrain_height(*goal[:2]))
        region=(tuple(goal_region[0]),float(goal_region[1])) if goal_region and goal_region[1]>=self.cell else None
        if region and math.dist(pos[:2],region[0])<=region[1] and self.arena.point_clear(pos,stats['radius'],stats['height']):
            self.path=[];self.search=None;self.goal_region=region;self.goal=goal[:2]
            return pos
        # A direct reachable route avoids unnecessary grid discretization.
        if math.dist(pos[:2], goal[:2]) < 70 and (not region or math.dist(target[:2],region[0])<=region[1]) and self._clear(pos, target, stats):
            self.path = []
            self.search = None
            self.goal = goal[:2]
            self.goal_region = region
            return target
        # Local threat avoidance or terrain curvature can invalidate the join
        # from our new position to a formerly visible waypoint.
        stale_region=self.path and region and math.dist(self.path[-1][:2],region[0])>region[1]
        # Keep goal hysteresis while travelling, but a completed point route
        # must not pin us to its old endpoint after a small blocked goal shift.
        stale_point=(self.path and not region and self.goal_region is None
                     and math.dist(pos[:2],self.path[-1][:2])<=self.cell*.7
                     and math.dist(self.path[-1][:2],target[:2])>1e-6)
        if self.path and (stale_region or stale_point or not self._clear(pos, self.path[0], stats)):
            self.path = []
            self.search = None
            self.last_plan = -100.0
            if stale_region:
                self.goal_region=None
        if region:
            changed=self.goal_region is None or math.dist(self.goal_region[0],region[0])>self.cell or abs(self.goal_region[1]-region[1])>self.cell
        else:
            changed=self.goal_region is not None or self.goal is None or math.dist(self.goal[:2],goal[:2])>self.cell*1.5
        if changed or (not self.path and self.search is None and now - self.last_plan > 1.0):
            self.goal = goal[:2]
            self.goal_region = region
            self._region_zero = False
            self.path = []
            self.last_plan = now
            start, end = self._key(pos), self._key(target)
            # The start cell may overlap a wall even when the actual spawn is clear.
            starts = []
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                key = (start[0] + dx, start[1] + dy)
                if self._clear(pos, self._point(key), stats):
                    cost = math.dist(pos[:2], self._point(key)[:2]) / self.cell
                    starts.append((key, cost))
            def heuristic(key):
                if self.goal_region:
                    if self._region_zero:return 0.
                    center,radius=self.goal_region
                    return max(0.,math.dist((key[0]*self.cell,key[1]*self.cell),center)-radius)/self.cell
                return math.dist(key,end)
            frontier = [(cost + heuristic(key), cost, key) for key, cost in starts]
            heapq.heapify(frontier)
            self.search = [frontier, {key: cost for key, cost in starts}, {key: None for key, _ in starts}, end]
        if self.search is not None:
            frontier, costs, parents, end = self.search
            if region and self.goal_region and not self._region_zero:
                # The frozen region heuristic remains a lower bound for a
                # nested shrink. If the current region expands or shifts out,
                # retain search progress with zero (always admissible) h.
                if math.dist(region[0],self.goal_region[0])+region[1]>self.goal_region[1]+1e-6:
                    self._region_zero=True
                    frontier[:]=[(cost,cost,node) for _,cost,node in frontier]
                    heapq.heapify(frontier)
            def heuristic(key):
                if self.goal_region:
                    if self._region_zero:return 0.
                    center,radius=self.goal_region
                    return max(0.,math.dist((key[0]*self.cell,key[1]*self.cell),center)-radius)/self.cell
                return math.dist(key,end)
            deadline = time.perf_counter() + budget_ms / 1000
            iterations = 0
            while frontier and iterations < 140 and time.perf_counter() < deadline:
                _, cost, node = heapq.heappop(frontier)
                if cost > costs.get(node, float('inf')) + 1e-9:
                    continue
                self.expansions += 1
                iterations += 1
                p = self._point(node)
                arrived=math.dist(p[:2],region[0])<=region[1] if region else math.dist(node,end)<=1.5 and self._clear(p,target,stats)
                if arrived:
                    route = [p if self.goal_region else target]
                    while node is not None:
                        route.append(self._point(node))
                        node = parents[node]
                    self.path = list(reversed(route))
                    self.search = None
                    break
                if len(costs) > 14000:
                    self.search = None
                    break
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
                    nxt = (node[0] + dx, node[1] + dy)
                    new_cost = cost + math.hypot(dx, dy)
                    if new_cost >= costs.get(nxt, float('inf')):
                        continue
                    if self._edge(node, nxt, stats):
                        costs[nxt] = new_cost
                        parents[nxt] = node
                        heapq.heappush(frontier, (new_cost + heuristic(nxt), new_cost, nxt))
            if self.search is not None and not frontier:
                self.search = None
                if self.cell > 3.5:
                    # A coarse lattice can miss the entrance to a narrow but
                    # walkable corridor. Retry once on a finer static graph.
                    self.cell = 3.5
                    self.edge_cache.clear()
                    self.goal = None
                    self.last_plan = -100.0
        if self.path:
            while len(self.path) > 1 and math.dist(pos[:2], self.path[0][:2]) < self.cell * 0.7 and self._clear(pos, self.path[1], stats):
                self.path.pop(0)
            # Bounded shortcutting, checked at current size.
            for index in range(min(5, len(self.path) - 1), 0, -1):
                if self._clear(pos, self.path[index], stats):
                    self.path = self.path[index:]
                    break
            return self.path[0]
        # Local controller checks every proposed motion while the search progresses.
        return target


def circle_at(zone, now, future=0.0):
    """Observation circle is current, not the phase's original circle."""
    remaining = zone['shrink_end'] - max(now, zone['shrink_start'])
    elapsed = max(0.0, now + future - max(now, zone['shrink_start']))
    alpha = min(1.0, elapsed / remaining) if remaining > 1e-6 else 1.0
    center = tuple(zone['center'][i] + (zone['next_center'][i] - zone['center'][i]) * alpha for i in range(2))
    radius = zone['radius'] + (zone['next_radius'] - zone['radius']) * alpha
    return center, max(0.0, radius)


def outside_distance(point, center, radius):
    return max(0.0, math.dist(point[:2], center) - radius)


class LocalController:
    """Short-horizon velocity sampling; all costs are proxy objectives, not score."""

    def __init__(self, arena, config, slot, energy_hysteresis=False, contact_repair=False):
        self.arena = arena
        self.config = config
        self.side = 1 if slot % 2 else -1
        self.last_move = (0.0, 0.0)
        self.last_pos = None
        self.stuck_s = 0.0
        self.last_t = None
        self.metrics = {}
        self.energy_hysteresis = energy_hysteresis
        self.contact_repair = contact_repair
        self.repair_when_stalled = False
        self.repair_active = False
        self.recharging = False

    def _stats(self, me):
        return effective_mech_stats(self.config, me)

    def choose(self, obs, waypoint, goal, recovering=False, allow_dodge=True, deadline=None, extra_moves=()):
        me, now = obs['self'], obs['t']
        stats = self._stats(me)
        pos = me['pos']
        dt = min(0.3, max(0.0, now - self.last_t)) if self.last_t is not None else 0.1
        if self.last_pos is not None and math.dist(pos[:2], goal[:2]) > 6 and math.dist(pos[:2], self.last_pos[:2]) < dt * 1.0:
            self.stuck_s += dt
        else:
            self.stuck_s = max(0.0, self.stuck_s - dt * 2)
        self.last_t, self.last_pos = now, pos[:]
        stranded = (self.repair_when_stalled and me['grounded'] and self.stuck_s >= .3
                    and self.metrics.get('valid_moves') == 0)
        repairing = ((self.contact_repair or stranded or (self.repair_active and me['grounded'])) and hasattr(self.arena, 'escape_clear')
                     and not self.arena.point_clear(pos, stats['radius'], stats['height']))
        self.repair_active = self.repair_when_stalled and repairing
        dx, dy = unit(waypoint[0] - pos[0], waypoint[1] - pos[1])
        theta = math.atan2(dy, dx)
        # Exact goal direction plus uniform samples prevents grid-locked movement.
        headings = [theta + a for a in (0, .35, -.35, .7, -.7, 1.1, -1.1, 1.57, -1.57, 2.2, -2.2, math.pi)]
        commands = [(math.cos(a), math.sin(a)) for a in headings] + [(0.0, 0.0)]
        # A fixed full-speed horizon otherwise prefers stopping a few meters
        # before a corner, where it cannot safely skip the next waypoint yet.
        arrival = min(1.0, math.dist(pos[:2], waypoint[:2]) / max(1., stats['walk_speed'] * .6))
        if arrival < .98:
            commands += [(math.cos(a) * arrival, math.sin(a) * arrival) for a in headings[:7]]
        for candidate in extra_moves[:2]:
            if len(candidate)==2 and all(math.isfinite(x) for x in candidate):
                length=max(1.,math.hypot(*candidate))
                commands.append((candidate[0]/length,candidate[1]/length))
        enemies = [e for e in obs['mechs'] if e['kind'] == 'mech']
        enemies.sort(key=lambda e: math.dist(e['pos'][:2], pos[:2]))
        enemies = enemies[:6]
        # Bound work even under dense projectile observations.
        projectiles = []
        imminent = False
        if allow_dodge:
            threats = []
            reach = stats['radius'] + 3 + 1.2 * stats['boost_speed']
            for projectile in obs['projectiles']:
                rx, ry = projectile['pos'][0]-pos[0], projectile['pos'][1]-pos[1]
                vx, vy = projectile['vel'][0]-me['vel'][0], projectile['vel'][1]-me['vel'][1]
                vv = vx*vx + vy*vy
                tca = max(0., min(.6, -(rx*vx+ry*vy)/vv)) if vv > 1e-9 else 0.
                closest = math.hypot(rx+vx*tca,ry+vy*tca)
                if closest <= reach:
                    threats.append((closest, tca, projectile))
                    imminent |= closest < stats['radius']+1.5 and 0<tca<.3
            threats.sort(key=lambda item:(item[0],item[1]))
            projectiles = [item[2] for item in threats[:32]]
        danger = any(math.dist(e['pos'][:2], pos[:2]) < 130 for e in enemies)
        urgent = not me['in_zone'] or outside_distance(pos, *circle_at(obs['zone'], now, 5.0)) > 0
        if self.energy_hysteresis:
            low,high = .28*me['max_energy'],.70*me['max_energy']
            if self.recharging and me['energy'] >= high:
                self.recharging=False
            elif not self.recharging and me['energy'] <= low:
                self.recharging=True
            permit = (not self.recharging and me['energy'] > low) or (urgent and me['energy'] > 12) or (imminent and me['energy'] > 20)
            can_boost = permit and (urgent or danger or self.stuck_s > 1.0 or imminent)
        else:
            can_boost = me['energy'] > (12 if urgent else 28) and (urgent or danger or self.stuck_s > 1.0)
        charging = any(w and w['kind'] == 'laser' and w.get('charge', 0) > 0 for w in me['weapons'])
        best, best_score = ((0., 0.), False), -float('inf')
        valid = 0
        # First sample at 0.1s includes true acceleration; horizon reacts to bullets.
        horizons = (.1, .3, .6)
        # Projectile physics is independent of our candidate: compute it once.
        projectile_paths = {}
        for horizon in horizons:
            paths = []
            for projectile in projectiles:
                kind = projectile['kind']
                start = tuple(projectile['pos'][i]-pos[i] for i in range(3))
                end = [start[i]+projectile['vel'][i]*horizon for i in range(3)]
                blast = False
                if kind == 'mortar':
                    end[2] -= .5*self.config['weapons']['mortar']['gravity']*horizon*horizon
                    blast = end[2]+pos[2] <= self.arena.terrain_height(end[0]+pos[0],end[1]+pos[1])+3
                paths.append((*start,*end,kind=='mortar',blast))
            projectile_paths[horizon] = paths
        for move in commands:
            if deadline is not None and time.perf_counter() >= deadline:
                break
            for boost in ((False, True) if can_boost and move != (0., 0.) else (False,)):
                speed = stats['boost_speed'] if boost and me['grounded'] else stats['walk_speed']
                if charging:
                    speed *= stats.get('charge_move_mult', .5)
                acceleration = stats['ground_accel'] if me['grounded'] else stats['air_accel']
                vx, vy = me['vel'][:2]
                vz = me['vel'][2]
                px, py, pz = pos
                score = 0.0
                previous_t = 0.0
                good = True
                for horizon in horizons:
                    segment_dt = horizon - previous_t
                    previous_t = horizon
                    dvx, dvy = move[0] * speed - vx, move[1] * speed - vy
                    factor = min(1.0, acceleration * segment_dt / max(1e-9, math.hypot(dvx, dvy)))
                    nvx, nvy = vx + dvx * factor, vy + dvy * factor
                    nx, ny = px + (vx + nvx) * .5 * segment_dt, py + (vy + nvy) * .5 * segment_dt
                    if me['grounded']:
                        nz = self.arena.surface_height(nx, ny, pz, stats['step_up'], stats['height'])
                        # A roof edge starts a fall; it does not teleport feet to terrain.
                        if nz < pz - stats['step_up']:
                            nz = pz
                    else:
                        vertical_accel = (stats['jet_accel'] if boost else 0.) - stats['gravity']
                        nvz = vz + vertical_accel * segment_dt
                        if boost:
                            nvz = min(stats['max_rise_speed'], nvz)
                        nz = max(self.arena.terrain_height(nx, ny), pz + (vz+nvz)*.5*segment_dt)
                        vz = nvz
                    if self.arena.available:
                        start,end=(px,py,pz),(nx,ny,nz)
                        clear=self.arena.move_clear(start,end,stats['radius'],stats['height'],stats['step_up'],stats['max_slope_deg'],grounded=me['grounded'])
                        if not clear and repairing:
                            clear=self.arena.escape_clear(start,end,stats['radius'],stats['height'],stats['step_up'],stats['max_slope_deg'],grounded=me['grounded'])
                        if not clear:
                            good = False
                            break
                    center, radius = circle_at(obs['zone'], now, horizon)
                    score -= outside_distance((nx, ny), center, max(0.0, radius - stats['radius'])) * (4 + obs['zone']['dps'] * .08)
                    if allow_dodge:
                        score -= self._projectile_cost(projectile_paths[horizon], me, (nx, ny, nz), stats)
                    px, py, pz, vx, vy = nx, ny, nz, nvx, nvy
                if not good:
                    continue
                valid += 1
                score += (math.dist(pos[:2], waypoint[:2]) - math.dist((px, py), waypoint[:2])) * 3.0
                for enemy in enemies:
                    ex = enemy['pos'][0] + enemy['vel'][0] * .6
                    ey = enemy['pos'][1] + enemy['vel'][1] * .6
                    dist = math.hypot(px - ex, py - ey)
                    current_dist = math.dist(pos[:2], enemy['pos'][:2])
                    preferred = 120 if recovering else (75 if 'lightning' in enemy.get('weapons', []) else 45)
                    score -= max(0.0, preferred - dist) * (0.17 if recovering else .09)
                    # Make telegraphed laser line expensive, with full responsibility.
                    if enemy.get('charging'):
                        yaw = enemy['aim'][0]
                        along = (px - ex) * math.cos(yaw) + (py - ey) * math.sin(yaw)
                        across = abs((px - ex) * math.sin(yaw) - (py - ey) * math.cos(yaw))
                        if 0 < along < self.config['weapons']['laser']['range']:
                            score -= max(0., stats['radius'] + 4 - across) * 12
                    # Favor strafing over moving along enemy's aim when engaged.
                    if current_dist < 180 and allow_dodge:
                        ux, uy = unit(pos[0] - ex, pos[1] - ey)
                        score += abs(vx * uy - vy * ux) * .09
                score -= .4 if boost else 0.0
                score -= math.dist(move, self.last_move) * .06
                if math.dist(pos[:2], goal[:2]) < 2 and not danger:
                    score -= math.hypot(*move) * 3
                if score > best_score:
                    best, best_score = (move, boost), score
        move, boost = best
        jump = False
        # Controlled escape: only after a measured stall; verify vertical clearance.
        if self.stuck_s > 1.2 and me['grounded'] and me['energy'] > 40:
            up = (pos[0], pos[1], pos[2] + min(3, stats['step_up'] + 1.5))
            if not self.arena.available or self.arena.move_clear(pos, up, stats['radius'], stats['height'], stats['step_up'], stats['max_slope_deg'], grounded=False):
                jump = True
                move = (dx, dy)
        if not me['grounded'] and self.stuck_s > 1.2 and me['energy'] > 20:
            boost = True
        self.last_move = move
        self.metrics = {'valid_moves':valid, 'score':round(best_score,3) if valid else None, 'stuck_s':round(self.stuck_s,2)}
        return {'move':list(move), 'boost':bool(boost), 'jump':jump}

    def _projectile_cost(self, paths, me, future_pos, stats):
        cost = 0.0
        mx,my,mz = (future_pos[i]-me['pos'][i] for i in range(3))
        radius = stats['radius'] + 1.5
        height = stats['height'] + .5
        splash = self.config['weapons']['mortar']['splash_radius'] + stats['radius'] + 2
        for sx,sy,sz,ex,ey,ez,mortar,blast in paths:
            if blast:
                cost += max(0.,splash-math.hypot(ex-mx,ey-my))*9
            dx,dy,dz = ex-mx-sx,ey-my-sy,ez-mz-sz
            norm = dx*dx+dy*dy
            alpha = min(1.,max(0.,-(sx*dx+sy*dy)/norm)) if norm>1e-9 else 0.
            z = sz+alpha*dz
            if -.5<z<height:
                distance = math.hypot(sx+alpha*dx,sy+alpha*dy)
                cost += max(0.,radius-distance)*(16 if mortar else 7)
        return cost
