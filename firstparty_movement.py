"""First-party match movement arbitration. Input positions are observed feet coordinates."""

import base64
import heapq
import math
import zlib
from functools import lru_cache
import time

from navigation import circle_at, unit, _DIRECTION_BITS
from navigation_cache import get_graph, IDENTITY


# Generated from the validated first-party seven-metre directed navigation graph.
_ISLAND_MASKS = {
    2.5: "eNrtlEEOgjAQRYs11pWyNTGBG3gEPAo3gaORuPEYHKE7WRDGKWLozI8LF0YTnIQFL5POa2daYxYSCZAak86I8rcrbRGtzT8WHhsgtFKgHCqd01IR/x5HlMVox58np0fdEwx8Wx00usq1wg3oQ8VUOoQsMdWeaK93A6hm5OTFaxhZefF4dVbN1er6bLoxC5By6EkeF8dAsMWXpkaa3qzuBTh4dGCku9ihFpueELm5pU/5ycFG8g+HOpnRVLCJUKHfOOyYocoCymBMLw5Q+jsvdvm5+uVX34s7xpVrFg==",
    2.625: "eNrtlEEOgjAQRYs11pWyNTGBG3gEPAo3gaORuPEYHKE7WRCGATF05uvChWGBTVjwMum8dmZqzEpWBKTEoCui9OtMe0Rb818rXzsgtFEg7wodU1MW/p5HlITowJ8np1vdEzR8XZw0usu9hgloh4yxdBiiRFd7oqM+DaCSkZODVzGycvB4d1ZN1e76bpoxCpByaEleF6+O4IgfTY00fVhdC3Dw6MBIV7FBLTa9IHJzSV/yk4MN5J8OZTSjKWEVoEy/cVgxQ4UFlECb3hygeKEZevNi57/Lli/6XvTFl2sV",
    2.75: "eNrtlE0KwjAQhRMjxpU/e0Fv4BHqUXqT5GgFNx7DI3RnF9JxUivNzNtUEBTqgyzyMUzeZIYxZrKKiE6IDm/nXSKam78mrgUQmilQtkHHXKnIr7sO7XO04lOTz5HtkIVcYavRReZKuqcXN9JDihJTXROtdTWAIiMvUcXI6QpJW+Xs+m8ajEoIvMvvYrUEJY51ehvn1ADSXWzQFjs9IvJDS1/mew8uM//0EO2A+gerDBV6x2HHDAUHCObBnCFIjsfPbexPqfzqvngApitqBw==",
    2.875: "eNrtlE0KwjAQRidGjCt/9oLewCPUo/QmydEKbjyGR+jOLqRjGiudzLepICjUgSzyGGZeMjBEk42A6ITo8HbdJaI5/WPisQDCMwXK1uucKxfyuktoL9EqnpqdRCYhA7X8VqNLXquLe94xNYSsmnmtXwMoRORyVEVkobpWjdX13zSY1SFwB/kW5cea3saZ4tfoKTaoFU2PiNww0pd872CF/NMhmAH1DSuBCr3jcGLE3gKCJDpDEm1+emN/Ksqv7osHOetp3w==",
    3.0: "eNrtlD0OwjAMRp0GESZ+diS4AUdoj9KbpEerxMIxOEI3OqC4IQpq4m8JCwPFUoc+WZ+fYslEi60OUYPo/HHuBtGK/rXwWgNxlQCts7LnznX6ewzolKKt/wY2KVIBKciyB4luedarnvnEMBC6BuadQAyo88jkqPdIQ7pU9eks3mZktgoQgzvIO5QvNX2UmeLTyC2OqOVNL4jMvNK3fHTQiXx0VjOKA/sE1fLG4caIrQYETXSFJtqXn7nq+xf7N2oCn6NpCw==",
    3.125: "eNrtlEEKwjAQRSeNmK4q7gWP4BHqUbxJerSCG4/hEbqzC8kYQ6ST+ZuCLpQ60EUfw59HBoZosdUhOn4it0a0on8tvNZAQqXAKXjdc+VW/u4S2kvUxG9gJ5FJyECW32p0KbOedS8npoHQNTBvFGJAXUSuRH1EFtK1akxn9TYjszeAGNxBPqD8XNPbPFN8Gr3FEbWi6QGRm1b6ks8OVshnZzOhPLAXqNU3DjdG7C0gaKKzfefMVb9wsb+xHrpUaNs=",
    3.25: "eNrllE0KwjAQhZNGbFeKe8Ej6NKdHsWbJEcruPEYOUJ3diEZYym1eW8TsIjFWX6EyfcmP0r9bTlG5yn6VowWc5vNhdGR0ZbRilHJkzeEap3jcPi2g5tsoksigQIHi8jLCcN62WHYRpJ8ukMUxtsNolva61WPdMduQ1rViKwBCSEXEcy9jshQd1SN3aVIUStiNSEhd5IPLJ9res8z5dHgKbasFU33jEq4KmGYlhnJ9876jSze3yG0G6XGE1Ni6Q3wInU1n3xzxRx+7F+sJ+OibUM=",
    3.375: "eNrllE0KwjAQhZNGjCvFveARdOmuPYo3SY4muPEYPUJ3diF5xlJqM28TsIjFWX6EyfcmP0r9bXlG1RR9V4wWc5vNmdGJ0Y7RmpHlyRtCF53jcPy2g59soksigQIHR0ooZdgaexm2QZJPd4jC1OVWolva61WPdMduQ1rVABuBQMhHZGUcwFB3qRq7o0hRCzhNCORO8oHlc03veaY8GnmKLWtF0wMjK65KGKZlRvK9s34jJ+/vENqPUssTU3D0BniRuppPvrliDj/2L9YTeRNs4w==",
    3.5: "eNrllE0KwjAQhZNGjCvFveARdOmuPYo3SY4muPEYPUJ3diF5xlJqM28TsIjFWX6EyfcmP0r9bXlG1RR9V4wWc5vNmdGJ0Y7RmpHlyRtCF53jcPy2g59soksigQIHR0ooZdgaexm2QZJPd4jC1OVWolva61WPdMduQ1rVABuBQMhHZGUcwFB3qRq7o0hRCzhNCORO8oHlc03veaY8GnmKLWtF0wMjK65KGKZlRvK9s34jJ+/vENqPUssTU3D0BniRuppPvrliDj/2L9YTeRNs4w==",
    3.625: "eNrllEEOgjAQRVtqhJXEvYlH0KU7PIo3aY9G4sZjcAR2sjD9IhJk5m9MJEZily/N9M2ftsb87QqMjlPUzRgt5pbNidGB0YbRilHKyTtCpX3HYf9thzBZoksikRqOnpRQ6GYrbHWzNUR/tkPUTFWsNbrIWo91kyd2B9KuGsgVAqBCDozKFjmqrlXb6kgkagBvCYHcST528pkyzeWT7E0TaXp1zyilaalNORo9xYa1WtMdo1RdlTik5UbyvbN9Ia/v7zCxMOpaT8zA0xvgTebsPvnmkjn82L+47lR1bao=",
    3.75: "eNrtlTsOwjAQRO0YkVREdBQIjgAlXTgKN7GPFlFxDI6QDgrkIbGiYO8UIBEhgdjCxZO1fuNPotS/Rq6C0eTbMhwY7RgtGc0Y5UScIVTrVxy2n3YYr6ZEPAX2VsavUcXxu7BnrCO06MI2iPOtdEBxmDL0qubxrG44Jb1C3ZIVVViQZjVAKRAAscmOUd0iQ92hqTuyFF0BqwmB3EneB/lCmJbpk+xNs9T00prq56a8NVaRacWmG0a5uCp+2C0TyffO+oGsvL/DibkotTwxBUtvgCepo3nnM5eN+YYco/1P/DLugCFsfA==",
}


@lru_cache(maxsize=11)
def _islands(radius):
    return zlib.decompress(base64.b64decode(_ISLAND_MASKS[radius]))


def _component(bot, stats, p):
    arena = bot.arena
    identity = tuple(
        getattr(arena, k, "") for k in ("world_sha256", "terrain_sha256", "geometry_sha256")
    )
    shape = tuple(stats[k] for k in ("radius", "height", "step_up", "max_slope_deg"))
    graph = get_graph(identity, 7.0, shape)
    key = round(shape[0], 4)
    if graph is None or key not in _ISLAND_MASKS:
        return None
    x0, y0, nx, ny, data = graph
    x, y = round(p[0] / 7) - x0, round(p[1] / 7) - y0
    if not (0 <= x < nx and 0 <= y < ny):
        return None
    index = y * nx + x
    if not data[index]:
        return None
    island = _islands(key)
    return "isolated" if island[index // 8] & (1 << (index % 8)) else "main"


class _LiveGroundSurvey:
    """Budgeted directed walks to the arena's central ground node with the full live body."""

    def __init__(self, arena, shape):
        self.arena, self.shape = arena, shape
        self.points = {}
        self.edges = {}
        self.support = {}
        self.partial = None
        self.known = {}
        self.pending = None
        self.exhausted = set()
        center = self.point((0, 0))
        if arena.point_clear(center, *shape[:2]):
            self.known[(0, 0)] = "main"

    def point(self, cell):
        if cell not in self.points:
            x, y = 7 * cell[0], 7 * cell[1]
            self.points[cell] = (x, y, self.arena.terrain_height(x, y))
        return self.points[cell]

    def walk(self, start, end):
        return self.arena.move_clear(start, end, *self.shape)

    def neighbors(self, cell, deadline):
        if cell in self.edges:
            return self.edges[cell]
        if self.partial is None:
            self.partial = (iter(_DIRECTION_BITS), [])
        directions, neighbors = self.partial
        start = self.point(cell)
        while time.perf_counter() < deadline:
            direction = next(directions, None)
            if direction is None:
                self.edges[cell] = neighbors
                self.partial = None
                return neighbors
            key = (cell[0] + direction[0], cell[1] + direction[1])
            end = self.point(key)
            if key not in self.support:
                self.support[key] = (self.arena.in_bounds(*end[:2], self.shape[0])
                                     and self.arena.point_clear(end, *self.shape[:2]))
            if self.support[key] and self.walk(start, end):
                neighbors.append(key)
        return None

    def classify(self, point):
        key = (round(point[0] / 7), round(point[1] / 7))
        if not self.known or key in self.exhausted or not self.walk(point, self.point(key)):
            return None
        if key not in self.known and self.pending is None and len(self.edges) < 8192:
            self.pending = (key, [(abs(key[0]) + abs(key[1]), key)], {key: None})
        return self.known.get(key)

    def advance(self, deadline):
        if self.pending is None:
            return
        start, frontier, parent = self.pending
        while frontier and time.perf_counter() < deadline:
            _, cur = frontier[0]
            if self.known.get(cur) == "main":
                while cur is not None:
                    self.known[cur], cur = "main", parent[cur]
                self.pending = None
                return
            if len(parent) > 2048 or len(self.edges) >= 8192:
                self.exhausted.add(start)
                self.pending = None
                return
            neighbors = self.neighbors(cur, deadline)
            if neighbors is None:
                return
            heapq.heappop(frontier)
            for nxt in neighbors:
                if nxt in parent or self.known.get(nxt) == "isolated":
                    continue
                parent[nxt] = cur
                heapq.heappush(frontier, (abs(nxt[0]) + abs(nxt[1]), nxt))
        if not frontier:
            # Only exhaustive directed search can prove there is no path to center.
            self.known.update((cell, "isolated") for cell in parent)
            self.pending = None

    def approaches(self, point):
        origin = round(point[0] / 7), round(point[1] / 7)
        queue = [(origin, [self.point(origin)])]
        visited = {origin}
        sites = []
        for cell, path in queue:
            if len(path) > 4:
                continue
            # An exhausted isolated component already has all outgoing edges enumerated.
            for nxt in self.edges.get(cell, ()):
                if nxt in visited:
                    continue
                visited.add(nxt)
                route = path + [self.point(nxt)]
                sites.append(route)
                queue.append((nxt, route))
                if len(sites) == 48:
                    return sites
        return sites


_AUTO = object()


class AdaptiveMovement:
    def __init__(self):
        self.withdraw_until = -1.0
        self.lose_until = -1.0
        self.last_threat = -100.0
        self.recovering = False
        self.cover = None
        self.confirmed_cover = False
        self.last_player_hit = -100.0
        self.home = None
        self.last_foe = None
        self.live_ground = None
        self.launch = None
        self.staging = None
        self.survey = None
        self.approach_point = None
        self.island_again = -1.0
        self.last_pos = None
        self.stalled_since = None
        self.last_move = (0.0, 0.0)
        self.intent = None
        self.zone_slack = math.inf
        self.untangle = None
        self.untangle_after = -1.0
        self.laser_alert = -1.0
        self.bullet_step = None
        self.corner_step = None
        self.close_with_arc = False
        self.drone_bearing = None
        self.stop = math.inf

    def _supported(self, bot, obs, stats, x, y):
        radius = stats["radius"]
        if not bot.arena.in_bounds(x, y, max(radius, bot.config["match"].get("arena_margin", 0))):
            return None
        z = bot.arena.surface_height(x, y, obs["self"]["pos"][2], stats["step_up"], stats["height"])
        p = (x, y, z)
        if bot._safe_objective(p, obs, stats) and bot.arena.point_clear(p, radius, stats["height"]):
            return p
        return None

    @staticmethod
    def _walk(bot, stats, a, b, grounded=True):
        return bot.arena.move_clear(
            a,
            b,
            stats["radius"],
            stats["height"],
            stats["step_up"],
            stats["max_slope_deg"],
            grounded=grounded,
        )

    def _zone(self, bot, obs, stats):
        pos, now, zone = obs["self"]["pos"], obs["t"], obs["zone"]
        center = zone["next_center"]
        margin = min(zone["next_radius"] * 0.3, stats["radius"] + 7.0)
        inside_radius = max(0.0, zone["next_radius"] - margin)
        dx, dy = pos[0] - center[0], pos[1] - center[1]
        d = math.hypot(dx, dy)
        if d <= inside_radius and obs["self"]["in_zone"]:
            return math.inf, tuple(pos)
        ux, uy = unit(dx, dy)
        goal = (center[0] + ux * inside_radius, center[1] + uy * inside_radius)
        travel = math.dist(pos[:2], goal) / max(1.0, stats["walk_speed"] * 0.73)
        # Standard phases shrink into a contained circle, so a point exits once.
        lo, hi = 0.0, max(0.0, zone["shrink_end"] - now)
        for _ in range(10):
            mid = (lo + hi) * 0.5
            c, r = circle_at(zone, now, mid)
            if math.dist(pos[:2], c) <= max(0.0, r - margin):
                lo = mid
            else:
                hi = mid
        slack = hi - travel if obs["self"]["in_zone"] else -math.inf
        return slack, (*goal, bot.arena.terrain_height(*goal))

    @staticmethod
    def _recovery_anchor(bot, obs):
        pos, zone = obs["self"]["pos"], obs["zone"]
        x, y = zone["next_center"]
        radius = zone["next_radius"]
        if radius > 30:
            dx, dy = pos[0] - x, pos[1] - y
            distance = math.hypot(dx, dy)
            interior = radius - min(30, max(3, 0.3 * radius)) - 5
            if distance <= interior:
                return tuple(pos)
            x += dx * interior / distance
            y += dy * interior / distance
        return x, y, bot.arena.terrain_height(x, y)

    def _blocked(self, bot, stats, p, eyes):
        for eye in eyes:
            for h in (0.48, 0.9):
                if bot.arena.line_clear(eye, (p[0], p[1], p[2] + h * stats["height"])):
                    return False
        return bool(eyes)

    def _shelter(self, bot, obs, stats, eyes, reserve=0.0):
        pos, now = obs["self"]["pos"], obs["t"]
        self.confirmed_cover = False
        if self.cover is not None:
            point, until, old_eyes = self.cover
            if (
                now < until
                and len(eyes) == len(old_eyes)
                and all(math.dist(a, b) < 1.5 for a, b in zip(eyes, old_eyes))
            ):
                self.confirmed_cover = True
                return point
        if self._blocked(bot, stats, pos, eyes) and bot._safe_objective(pos, obs, stats):
            self.confirmed_cover = True
            self.cover = tuple(pos), now + 0.45, tuple(eyes)
            return tuple(pos)
        phase = (obs["tick"] // bot.config["match"]["decide_every"]) % 12
        threat = eyes[0]
        away = math.atan2(pos[1] - threat[1], pos[0] - threat[0])
        fallback = None
        for angle, reach in (
            (away, 11.0),
            (away + 0.9, 16.0),
            (away - 0.9, 16.0),
            (phase * math.tau / 12, 28.0),
            ((phase + 5) * math.tau / 12, 40.0),
        ):
            if time.perf_counter() >= self.stop - reserve:
                break
            p = self._supported(
                bot, obs, stats, pos[0] + reach * math.cos(angle), pos[1] + reach * math.sin(angle)
            )
            if p is None:
                continue
            if self._blocked(bot, stats, p, eyes):
                self.confirmed_cover = True
                self.cover = p, now + 0.6, tuple(eyes)
                return p
            if fallback is None and self._walk(bot, stats, pos, p):
                fallback = p
        return fallback

    def _cornered(self, bot, obs, stats, foe, eyes, opening, squad):
        pos = obs["self"]["pos"]
        target = foe["pos"]
        d = math.dist(pos[:2], target[:2])
        preferred, ready, _ = self._fight_profile(bot, obs, foe, squad, False)
        if opening:
            preferred = d + 20
        away = math.atan2(pos[1] - target[1], pos[0] - target[0])
        center = bot.combat._center(foe)
        best = None
        best_value = -math.inf
        # Tangents first so a short budget still permits lateral escape. Shorter
        # fallback steps fit narrow openings that reject the forward cover routes.
        for reach in (6.0, 2.5):
            for offset in (-4, 4, -3, 3, 0, -2, 2, -1, 1, -5, 5, -6, 6, -7, 7, 8):
                if time.perf_counter() >= self.stop:
                    break
                ang = (round(away / (math.pi / 8)) + offset) * math.pi / 8
                p = self._supported(
                    bot, obs, stats, pos[0] + reach * math.cos(ang), pos[1] + reach * math.sin(ang)
                )
                if p is None or not self._walk(bot, stats, pos, p):
                    continue
                clearance = math.dist(p[:2], target[:2])
                los = bot.arena.line_clear((p[0], p[1], p[2] + stats["muzzle_height"]), center)
                value = -abs(clearance - preferred) + (8 if los == bool(ready and not opening) else 0)
                if eyes and self._blocked(bot, stats, p, eyes):
                    value += 7
                # If possible avoid closing on the stronger shooter during withdrawal.
                if opening and clearance < d - 0.15:
                    value -= 10
                if value > best_value:
                    best, best_value = p, value
            if best is not None:
                break
        self.corner_step = best
        return best

    def _anchor(self, bot, obs, stats):
        pos, now = obs["self"]["pos"], obs["t"]
        if self.home:
            point, expires = self.home
            if now < expires and bot._safe_objective(point, obs, stats):
                return point
        center, radius = circle_at(obs["zone"], now, 15)
        best = None
        score = math.inf
        contacts = [
            a for a, t in getattr(bot, "contacts", {}).values() if a["kind"] == "mech" and now - t < 20
        ]
        for k in range(6):
            if time.perf_counter() >= self.stop:
                break
            a = bot.slot * 0.63 + k * 2.4 + int(now / 9) * 0.7
            x, y = center[0] + min(110.0, radius * 0.58) * math.cos(a), center[1] + min(
                110.0, radius * 0.58
            ) * math.sin(a)
            p = self._supported(bot, obs, stats, x, y)
            if p is None:
                continue
            muzzle = (x, y, p[2] + stats["muzzle_height"])
            open_sides = 0
            for dx, dy in ((25.0, 0.0), (0.0, 25.0), (-25.0, 0.0), (0.0, -25.0)):
                open_sides += bot.arena.line_clear(muzzle, (x + dx, y + dy, muzzle[2]))
            risk = sum(max(0.0, 1 - math.dist(p[:2], q["pos"][:2]) / 85) for q in contacts)
            risk += sum(max(0.0, 1 - math.dist(p[:2], q["pos"][:2]) / 55) for q in obs.get("drops", []))
            cost = open_sides * 13 + math.dist(pos[:2], p[:2]) * 0.15 + risk * 24
            if cost < score:
                score, best = cost, p
        if best is not None:
            self.home = best, now + 9
        return best

    @staticmethod
    def _fight_profile(bot, obs, foe, squad, finish):
        me = obs["self"]
        pos = me["pos"]
        distance = math.dist(pos[:2], foe["pos"][:2])
        held = {w["kind"]: w for w in me["weapons"] if w}
        gun, laser, arc = held.get("gun"), held.get("laser"), held.get("lightning")
        preferred = 85.0
        if arc and me["energy"] > 12:
            preferred = 28.0
        elif laser and squad:
            preferred = 120.0
        if squad and finish:
            preferred = 20.0
        if foe["kind"] == "npc":
            preferred = 58.0
        elif not arc:
            if "lightning" in foe["weapons"]:
                preferred = max(64.0, preferred)
            if "mortar" in foe["weapons"]:
                preferred = max(80.0, preferred)
        gun_stats = bot.combat._weapon_stats(gun) if gun else {}
        laser_stats = bot.combat._weapon_stats(laser) if laser else {}
        arc_stats = bot.combat._weapon_stats(arc) if arc else {}
        firing = bool(
            gun
            and gun.get("ammo", 0) > 0
            and gun.get("reload", 0) <= 0.25
            and distance <= gun_stats["range"] - 10
        )
        hot = bool(
            laser
            and laser.get("charge", 0) >= laser_stats["charge"] - 0.3
            and distance <= laser_stats["range"] - 5
        )
        arc_ready = bool(
            arc and distance <= arc_stats["range"] + 6 and me["energy"] >= 3 * arc_stats["energy"]
        )
        firing |= hot or arc_ready or bool(squad and (laser or arc))
        if not squad and not hot:
            for other in obs["mechs"]:
                if other["kind"] == "mech" and other.get("charging"):
                    bearing = math.atan2(pos[1] - other["pos"][1], pos[0] - other["pos"][0])
                    if abs(math.remainder(other["aim"][0] - bearing, math.tau)) < 0.3:
                        firing = False
                        break
        return preferred, firing, bool(arc and distance > 50 and me["energy"] > 55 and firing)

    def _tactical(self, bot, obs, stats, foe, others, squad, finish):
        me = obs["self"]
        pos = me["pos"]
        dst = foe["pos"]
        now = obs["t"]
        preferred, firing, self.close_with_arc = self._fight_profile(bot, obs, foe, squad, finish)
        if time.perf_counter() >= self.stop:
            return None
        center = bot.combat._center(foe)
        d = math.dist(pos[:2], dst[:2])
        radial = unit(dst[0] - pos[0], dst[1] - pos[1])
        orient = 1 if (int(now * 1.25) + bot.slot) % 3 else -1
        correct = max(-1.0, min(1.0, (d - preferred) / 12.0))
        best = None
        score = None
        for sid, step in ((orient, 10.0), (-orient, 10.0), (orient, 5.0), (0, 9.0), (0, 0.0)):
            if time.perf_counter() >= self.stop:
                break
            dx, dy = unit(correct * radial[0] - sid * radial[1], correct * radial[1] + sid * radial[0])
            p = self._supported(bot, obs, stats, pos[0] + step * dx, pos[1] + step * dy)
            if p is None or (step and not self._walk(bot, stats, pos, p)):
                continue
            clear = bot.arena.line_clear((p[0], p[1], p[2] + stats["muzzle_height"]), center)
            cost = abs(math.dist(p[:2], dst[:2]) - preferred) + 28 * (clear != firing)
            if others and not self._blocked(bot, stats, p, others[:2]):
                cost += 14
            if not step and firing:
                cost += 4
            if score is None or cost < score:
                best, score = p, cost
        if squad:
            # Cubes still grant body growth and can deny resources after the combat stat cap.
            radius = 70.0 if me["hp"] > 0.5 * me["max_hp"] else 39.9
            remembered = {
                i: entry[1] for i, entry in getattr(bot, "memory", {}).items() if entry[0] == "cubes"
            }
            remembered.update({c["id"]: c for c in obs["cubes"]})
            closest = min(
                remembered.values(), key=lambda c: math.dist(pos[:2], c["pos"][:2]), default=None
            )
            if closest is not None:
                point = closest["pos"]
                if math.dist(pos[:2], point[:2]) < radius and self._supported(
                    bot, obs, stats, *point[:2]
                ):
                    self.intent = "fight_cube"
                    return point
        self.intent = "finish" if finish and squad else "fight" if firing else "peek_cover"
        return best

    def _bullet_step(self, bot, obs, stats):
        me = obs["self"]
        pos = me["pos"]
        if not me["grounded"]:
            return None
        best = None
        for shot in obs["projectiles"][:32]:
            if shot["kind"] not in ("gun", "npc") or shot.get("owner") == me["id"]:
                continue
            p, v = shot["pos"], shot["vel"]
            rx, ry = p[0] - pos[0], p[1] - pos[1]
            vx, vy = v[0] - me["vel"][0], v[1] - me["vel"][1]
            vv = vx * vx + vy * vy
            if vv < 1:
                continue
            t = -(rx * vx + ry * vy) / vv
            if not 0 < t < 0.72:
                continue
            nearx, neary = rx + t * vx, ry + t * vy
            z = p[2] + t * v[2] - pos[2] - t * me["vel"][2]
            if math.hypot(nearx, neary) > stats["radius"] + 1 or not -0.4 < z < stats["height"] + 0.4:
                continue
            if best is None or t < best[0]:
                best = (t, p, v, nearx, neary)
        if best is None:
            return None
        t, p, v, nx, ny = best
        impact = tuple(p[k] + v[k] * t for k in range(3))
        if not bot.arena.line_clear(p, impact):
            return None
        dx, dy = unit(-v[1], v[0])
        sign = -1 if nx * dx + ny * dy > 0 else 1
        for side in (sign, -sign):
            ux, uy = dx * side, dy * side
            q = self._supported(bot, obs, stats, pos[0] + ux * 5.0, pos[1] + uy * 5.0)
            if q and self._walk(bot, stats, pos, q):
                return ux, uy
        return None

    def _shell(self, bot, obs, stats):
        pos = obs["self"]["pos"]
        weapon = bot.config["weapons"]["mortar"]
        gravity = max(0.1, weapon["gravity"])
        danger = weapon["splash_radius"] + stats["radius"] + 2.0
        for shell in obs["projectiles"][:32]:
            if shell["kind"] != "mortar" or shell.get("owner") == obs["self"]["id"]:
                continue
            start, vel = shell["pos"], shell["vel"]
            vx, vy = vel[:2]
            closest = max(
                0.0,
                min(
                    2.5,
                    ((pos[0] - start[0]) * vx + (pos[1] - start[1]) * vy)
                    / max(0.01, vx * vx + vy * vy),
                ),
            )
            if (
                math.hypot(start[0] + closest * vx - pos[0], start[1] + closest * vy - pos[1])
                > danger + 2
            ):
                continue

            def location(t):
                return (
                    start[0] + vx * t,
                    start[1] + vy * t,
                    start[2] + vel[2] * t - 0.5 * gravity * t * t,
                )

            def clear(a, b):
                return b[2] > bot.arena.terrain_height(*b[:2]) and bot.arena.line_clear(a, b)

            previous = start
            impact = None
            for n in range(1, 15):
                if time.perf_counter() >= self.stop:
                    break
                hi = min(2.5, n * 0.18)
                q = location(hi)
                if not clear(previous, q):
                    lo = (n - 1) * 0.18
                    for _ in range(4):
                        middle = (lo + hi) * 0.5
                        if clear(previous, location(middle)):
                            lo = middle
                        else:
                            hi = middle
                    impact = location(hi)
                    break
                previous = q
            if impact is None or math.dist(impact[:2], pos[:2]) > danger:
                continue
            ux, uy = unit(pos[0] - impact[0], pos[1] - impact[1])
            if ux == uy == 0:
                ux, uy = unit(-vy, vx)
                if ux == uy == 0:
                    ux = 1.0
            for dx, dy in ((ux, uy), (-uy, ux), (uy, -ux)):
                p = self._supported(bot, obs, stats, pos[0] + dx * 11, pos[1] + dy * 11)
                if p and self._walk(bot, stats, pos, p):
                    return p
        return None

    def _air_corridor(self, bot, stats, start, landing, height):
        rise = (start[0], start[1], height)
        above = (landing[0], landing[1], height)
        return (
            self._walk(bot, stats, start, rise, False)
            and self._walk(bot, stats, rise, above, False)
            and self._walk(bot, stats, above, landing, False)
        )

    @staticmethod
    def _survey_hint(bot, stats, point):
        # The smaller profile can nominate coordinates only. A live center route,
        # actual-body staging, and three live flight sweeps still gate movement.
        nominal = dict(stats, radius=3.75, height=13.5)
        return _component(bot, nominal, point)

    def _potential_island(self, bot, stats, pos):
        if self.live_ground and self._survey_hint(bot, stats, pos) == "isolated":
            return True
        return self._ground_component(bot, stats, pos) == "isolated"

    def _ground_component(self, bot, stats, pos):
        if self.live_ground is not None:
            return self.live_ground.classify(pos)
        return _component(bot, stats, pos)

    def _flight_from(self, bot, obs, stats, start, isolated):
        for k in range(8):
            if time.perf_counter() >= self.stop:
                break
            a = (k + (obs["tick"] // 2) % 8) * math.pi / 4
            land = self._supported(
                bot, obs, stats, start[0] + 20 * math.cos(a), start[1] + 20 * math.sin(a)
            )
            if not land:
                continue
            if not isolated and start[2] - land[2] < 3:
                continue
            if isolated and self.live_ground:
                if (self._survey_hint(bot, stats, land) == "isolated"
                        or not bot.arena.point_clear(start, stats["radius"], stats["height"])
                        or self._walk(bot, stats, start, land)):
                    continue
            elif isolated and self._ground_component(bot, stats, land) != "main":
                continue
            height = max(start[2], land[2]) + (7.0 if isolated else 2.0)
            if self._air_corridor(bot, stats, start, land, height):
                if not isolated or not self.live_ground or self.live_ground.classify(land) == "main":
                    return land, height
        return None

    def _launch_sites(self, bot, stats, pos):
        # Every predecessor edge is a directed, body-specific traversal from this
        # island start. The endpoint mask by itself cannot prove reachability.
        arena = bot.arena
        shape = tuple(stats[k] for k in ("radius", "height", "step_up", "max_slope_deg"))
        identity = tuple(
            getattr(arena, k, "") for k in ("world_sha256", "terrain_sha256", "geometry_sha256")
        )
        graph = get_graph(identity, 7.0, shape)
        if graph is None and self.live_ground:
            surveyed = self.live_ground.approaches(pos)
            if surveyed:
                return surveyed
            # These paths are proposals. Verify every chosen edge at current body size.
            graph = get_graph(identity, 7.0, (3.75, 13.5, shape[2], shape[3]))
        if graph is None:
            return []
        x0, y0, nx, ny, data = graph
        x, y = round(pos[0] / 7) - x0, round(pos[1] / 7) - y0
        if not (0 <= x < nx and 0 <= y < ny):
            return []
        origin = y * nx + x

        def point(i):
            x, y = 7.0 * (x0 + i % nx), 7.0 * (y0 + i // nx)
            return (x, y, arena.terrain_height(x, y))

        start = point(origin)
        if not self._walk(bot, stats, pos, start):
            return []
        queue = [origin]
        paths = {origin: [start]}
        sites = []
        for node in queue:
            if len(paths[node]) > 4:
                continue
            for (dx, dy), bit in _DIRECTION_BITS.items():
                if not data[node] & (1 << bit):
                    continue
                x, y = node % nx + dx, node // nx + dy
                if not (0 <= x < nx and 0 <= y < ny):
                    continue
                nxt = y * nx + x
                if nxt in paths:
                    continue
                path = paths[node] + [point(nxt)]
                paths[nxt] = path
                queue.append(nxt)
                sites.append(path)
                if len(sites) >= 48:
                    return sites
        return sites

    def _approach_launch(self, bot, obs, stats):
        path, land, height, until = self.staging
        me = obs["self"]
        pos = me["pos"]
        now = obs["t"]
        if now > until or not bot._safe_objective(land, obs, stats) or not me["grounded"]:
            self.staging = None
            return None
        if math.dist(pos[:2], path[-1][:2]) <= 1.25:
            self.staging = None
            if self._air_corridor(bot, stats, pos, land, height):
                self.launch = land, height, now + 3.3
                return land
            return None
        for index in range(len(path) - 1, -1, -1):
            waypoint = path[index]
            if math.dist(pos[:2], waypoint[:2]) > 1.25 and self._walk(bot, stats, pos, waypoint):
                self.approach_point = waypoint
                return waypoint
        self.staging = None
        return None

    def _roof(self, bot, obs, stats):
        me = obs["self"]
        pos = me["pos"]
        now = obs["t"]
        self.approach_point = None
        shape = tuple(stats[k] for k in ("radius", "height", "step_up", "max_slope_deg"))
        if self.live_ground is not None and self.live_ground.shape != shape:
            self.live_ground = self.staging = self.survey = self.launch = None
        if shape[0] > max(_ISLAND_MASKS):
            if self.live_ground is None:
                identity = tuple(getattr(bot.arena, k, "") for k in ("world_sha256", "terrain_sha256", "geometry_sha256"))
                if identity == IDENTITY:
                    self.staging = self.survey = self.launch = None
                    self.live_ground = _LiveGroundSurvey(bot.arena, shape)
            if self.live_ground is not None:
                self.live_ground.advance(min(self.stop - .0007, time.perf_counter() + .0014))
        if self.launch:
            land, height, expiry = self.launch
            if now < expiry and (
                not me["grounded"]
                or pos[2] - bot.arena.terrain_height(*pos[:2]) > 3
                or self._potential_island(bot, stats, pos)
            ):
                if me["grounded"] and me["energy"] < 0.58 * me["max_energy"]:
                    self.launch = land, height, now + 3.3
                return land
            self.launch = None
        if self.staging:
            existing = self._approach_launch(bot, obs, stats)
            if existing is not None:
                return existing
        if not me["grounded"]:
            return None
        elevated = pos[2] - bot.arena.terrain_height(*pos[:2]) > 3
        roof_stall = elevated and self.stalled_since is not None and now - self.stalled_since > 0.65
        if not roof_stall and self.survey is None and now < self.island_again:
            return None
        isolated = not elevated and self._potential_island(bot, stats, pos)
        if not (roof_stall or isolated):
            self.survey = None
            return None
        if self.survey is None or math.dist(self.survey[0][:2], pos[:2]) > 3:
            self.island_again = now + 0.45
            flight = self._flight_from(bot, obs, stats, pos, isolated)
            if flight:
                self.launch = (*flight, now + 3.3)
                self.survey = None
                return flight[0]
            if not isolated:
                return None
            self.survey = (tuple(pos), self._launch_sites(bot, stats, pos))
        _, pending = self.survey
        for _ in range(3):
            if not pending:
                self.survey = None
                break
            if time.perf_counter() >= self.stop:
                break
            path = pending.pop(0)
            flight = self._flight_from(bot, obs, stats, path[-1], True)
            if flight:
                if self.live_ground and not all(self._walk(bot, stats, p, q)
                        for p, q in zip([pos] + path, path)):
                    continue
                self.staging = path, *flight, now + 10
                self.survey = None
                return self._approach_launch(bot, obs, stats)
        return None

    def _mark(self, bot, mode, goal):
        self.intent = mode
        bot.mode = mode
        if hasattr(bot, "goal_id"):
            bot.goal_id = None
        return goal

    def goal(self, bot, obs, stats, fallback_goal, deadline=None, target=_AUTO):
        if bot.match_policy != "adaptive":
            return fallback_goal
        self.intent = None
        self.bullet_step = None
        self.corner_step = None
        self.close_with_arc = False
        now, me = obs["t"], obs["self"]
        pos = me["pos"]
        self.stop = min(time.perf_counter() + 0.003, deadline if deadline is not None else math.inf)
        squad = bot.field_mode == "squad"
        late = obs["alive"] <= 3 or obs["zone"]["next_radius"] <= 70
        for event in obs["events"]:
            if event["type"] == "damaged" and event.get("by") is not None:
                self.last_player_hit = now
            if (
                event["type"] == "damaged"
                and event.get("weapon") == "npc"
                and event.get("bearing") is not None
            ):
                self.drone_bearing = (event["bearing"], now)
        if (
            self.last_pos is not None
            and math.hypot(*self.last_move) > 0.2
            and math.dist(self.last_pos[:2], pos[:2]) < 0.14
        ):
            if self.stalled_since is None:
                self.stalled_since = now
        else:
            self.stalled_since = None
        self.last_pos = tuple(pos)
        if time.perf_counter() >= self.stop:
            return fallback_goal if fallback_goal is not None else tuple(pos)
        roof = self._roof(bot, obs, stats)
        if roof is not None:
            return self._mark(bot, "island_approach" if self.approach_point else "roof_escape", roof)
        if self.untangle and now < self.untangle[1]:
            return self._mark(bot, "unstuck_step", self.untangle[0])
        if (
            me["grounded"]
            and self.stalled_since is not None
            and now - self.stalled_since > 0.8
            and now >= self.untangle_after
        ):
            self.untangle_after = now + 1.2
            dx, dy = unit(*self.last_move)
            for sign in (1, -1):
                sidestep = self._supported(
                    bot, obs, stats, pos[0] - sign * dy * 5.0, pos[1] + sign * dx * 5.0
                )
                if sidestep and self._walk(bot, stats, pos, sidestep):
                    self.untangle = (sidestep, now + 0.4)
                    return self._mark(bot, "unstuck_step", sidestep)
        shell = self._shell(bot, obs, stats)
        if shell is not None:
            return self._mark(bot, "shell_escape", shell)
        self.bullet_step = self._bullet_step(bot, obs, stats)
        slack, safe = self._zone(bot, obs, stats)
        self.zone_slack = slack
        if slack <= 2.0 and math.dist(pos[:2], safe[:2]) > 2:
            self.withdraw_until = -1.0
            return self._mark(bot, "zone_must", safe)
        listed = [a for a in obs["mechs"] if a["kind"] == "mech"]
        selected_id = (
            target.get("id") if isinstance(target, dict) and target.get("kind") == "mech" else None
        )
        prescribed = next((a for a in listed if a["id"] == selected_id), None)
        live = sorted(listed, key=lambda a: (a["id"] != selected_id, math.dist(pos[:2], a["pos"][:2])))[
            :6
        ]
        frac = me["hp"] / max(1.0, me["max_hp"])
        candidates = []
        reported_hidden = []
        eligibility = getattr(bot.combat, "engagement_ids", None)
        threats = []
        any_danger = False
        crowd = 0
        for foe in live:
            if time.perf_counter() >= self.stop:
                break
            fx, fy = foe["pos"][:2]
            d = math.hypot(fx - pos[0], fy - pos[1])
            if d > 240:
                continue
            center = bot.combat._center(foe)
            scale = 1.0 + foe.get("cubes", 0) * bot.config["cubes"].get("size_per_cube", 0.05)
            enemyeye = (fx, fy, foe["pos"][2] + scale * bot.config["mech"]["eye_height"])
            origin = (pos[0], pos[1], pos[2] + stats["muzzle_height"])
            los = bot.arena.line_clear(origin, center) or bot.arena.line_clear(
                origin, (fx, fy, foe["pos"][2] + 0.85 * scale * bot.config["mech"]["height"])
            )
            aim = (
                abs(math.remainder(math.atan2(pos[1] - fy, pos[0] - fx) - foe["aim"][0], math.tau))
                < 0.24
            )
            if los and d < 165:
                threats.append((foe, enemyeye))
            if los and aim and foe.get("charging") and d < bot.config["weapons"]["laser"]["range"]:
                self.laser_alert = now + 0.2
            ux, uy = unit(pos[0] - fx, pos[1] - fy)
            approach = (foe["vel"][0] - me["vel"][0]) * ux + (foe["vel"][1] - me["vel"][1]) * uy
            recent = (
                foe["id"] in getattr(bot, "last_weapon_attackers", ())
                and now - getattr(bot, "last_weapon_damage", -100) < 4
            )
            pressed = (
                (late if squad else obs["alive"] <= 2)
                or d < 62
                or recent
                or (aim and foe.get("charging") and d < 125)
                or (foe["hp"] < 330 and d < 120)
            )
            if squad:
                pressed |= d < 175 and (aim or approach > 3.0 or foe["hp"] < 0.4 * foe["max_hp"])
            any_danger |= pressed or recent
            crowd += int(pressed or (los and d < 150))
            if not los and (pressed if eligibility is None else foe["id"] in eligibility):
                reported_hidden.append((d, foe))
            if los and pressed:
                candidates.append((d * 0.55 + foe["hp"] * 0.07, foe))
        if any_danger or now - self.last_player_hit < 3:
            self.last_threat = now
        foe = (
            prescribed
            if target is not _AUTO
            else (min(candidates, key=lambda pair: pair[0])[1] if candidates else None)
        )
        near = crowd
        hurt = now - getattr(bot, "last_weapon_damage", -100)
        finish = bool(foe and foe["hp"] < 0.38 * foe["max_hp"] and frac > 0.42 and near <= 2)
        keep_fighting = bool(
            foe
            and math.dist(pos[:2], foe["pos"][:2]) < 120
            and (foe["hp"] < 200 or foe["hp"] < 0.5 * me["hp"])
        )
        if squad:
            close_count = sum(math.dist(pos[:2], a["pos"][:2]) < 160 for a in listed)
            losing = (close_count >= 3 and frac < 0.8) or (close_count >= 2 and frac < 0.55)
            losing |= bool(foe and frac < 0.35 and foe["hp"] / foe["max_hp"] > frac + 0.1)
            if foe and foe["hp"] < 0.25 * foe["max_hp"] and frac > 0.2 and close_count <= 2:
                losing = False
            if losing:
                self.lose_until = now + 1.5
            self.recovering = now < self.lose_until
        else:
            outgunned = bool(
                foe
                and "laser" in foe["weapons"]
                and not any(w and w["kind"] == "laser" for w in me["weapons"])
                and math.dist(pos[:2], foe["pos"][:2]) > 55
                and frac < 0.8
            )
            if (
                near >= 3
                or (near >= 2 and frac < 0.65)
                or outgunned
                or (frac < 0.38 and now - self.last_threat < 2)
            ):
                self.recovering = True
            elif frac > 0.8 or (now - self.last_threat > 7 and frac > 0.55):
                self.recovering = False
        if (
            now < 60
            and foe
            and foe["id"] in getattr(bot, "last_weapon_attackers", ())
            and hurt < 1.5
            and frac < 0.8
            and not keep_fighting
        ):
            gun_only = {w["kind"] for w in me["weapons"] if w} == {"gun"}
            armed = any(kind != "gun" for kind in foe["weapons"])
            worse_trade = foe["hp"] > me["hp"] * 1.15 and foe["hp"] / foe["max_hp"] > frac + 0.12
            equipment_loss = gun_only and armed and foe["hp"] >= me["hp"] * 0.90
            if worse_trade or equipment_loss:
                self.withdraw_until = max(self.withdraw_until, now + 5.5)
        if keep_fighting or late or frac >= 0.8 or slack < 13:
            self.withdraw_until = -1
        retreat = (self.recovering or now < self.withdraw_until) and not late and not keep_fighting
        # Movement and an independently selected defensive shot can proceed together.
        bot.recovering = retreat
        eyes = [eye for _, eye in threats[:3]]
        if retreat or (
            not squad and not late and not foe and now - getattr(bot, "incoming_bearing_at", -100) < 2.4
        ):
            # Cover is judged against the four closest recent opponents, including
            # source-only contacts. An occluded actor can see another location.
            nearby = {
                a["id"]: a
                for a, t in getattr(bot, "contacts", {}).values()
                if a["kind"] == "mech" and now - t <= 2.5
            }
            nearby.update({a["id"]: a for a in listed})
            ranked = sorted(
                (a for a in nearby.values() if math.dist(pos[:2], a["pos"][:2]) < 230),
                key=lambda a: math.dist(pos[:2], a["pos"][:2]),
            )[:4]
            eyes = [
                (
                    a["pos"][0],
                    a["pos"][1],
                    a["pos"][2]
                    + bot.config["mech"]["eye_height"]
                    * (1 + a.get("cubes", 0) * bot.config["cubes"].get("size_per_cube", 0.05)),
                )
                for a in ranked
            ]
            if (
                not eyes
                and getattr(bot, "incoming_bearing", None) is not None
                and now - bot.incoming_bearing_at < 2.4
            ):
                a = bot.incoming_bearing
                eyes = [
                    (
                        pos[0] + 65 * math.cos(a),
                        pos[1] + 65 * math.sin(a),
                        pos[2] + stats["muzzle_height"],
                    )
                ]
            if not eyes and self.drone_bearing and now - self.drone_bearing[1] < 3:
                a = self.drone_bearing[0]
                eyes = [
                    (
                        pos[0] + 35 * math.cos(a),
                        pos[1] + 35 * math.sin(a),
                        pos[2] + stats["muzzle_height"],
                    )
                ]
            when_hidden = (
                self._shelter(bot, obs, stats, eyes, 0.001 if foe else 0.0) if eyes else None
            )
            if when_hidden is not None:
                mode = (
                    "shelter"
                    if self.confirmed_cover
                    else ("opening_withdraw" if now < self.withdraw_until else "flee")
                )
                return self._mark(bot, mode, when_hidden)
            if retreat:
                opening = now < self.withdraw_until
                if foe is None:
                    if opening and not nearby:
                        return self._mark(bot, "opening_recover", tuple(pos))
                    return self._mark(bot, "flee", self._recovery_anchor(bot, obs))
                short = (
                    self._cornered(bot, obs, stats, foe, eyes, opening, squad)
                    if me["grounded"]
                    else None
                )
                return self._mark(
                    bot, "opening_withdraw" if opening and short else "cornered", short or tuple(pos)
                )
        if foe:
            self.last_foe = (foe["id"], now)
            g = self._tactical(
                bot,
                obs,
                stats,
                foe,
                [eye for other, eye in threats if other["id"] != foe["id"]],
                squad,
                finish,
            )
            if g is not None:
                return self._mark(bot, self.intent, g)
        elif not squad and reported_hidden:
            # A listed opponent can be currently occluded. Seek a firing lane
            # without manufacturing a combat target or replacing the fire selector.
            hidden = min(reported_hidden, key=lambda pair: pair[0])[1]
            g = self._tactical(
                bot,
                obs,
                stats,
                hidden,
                [eye for other, eye in threats if other["id"] != hidden["id"]],
                False,
                False,
            )
            if g is not None:
                return self._mark(bot, "peek_reported", g)
        elif not squad and self.last_foe and now - self.last_foe[1] < 1.6:
            found = getattr(bot, "contacts", {}).get(self.last_foe[0])
            if found:
                actor, t = found
                if now - t < 1.6 and math.dist(pos[:2], actor["pos"][:2]) < 120:
                    g = self._tactical(bot, obs, stats, actor, eyes, False, False)
                    if g is not None:
                        return self._mark(bot, "peek_last_contact", g)
        if slack < 13 and math.dist(pos[:2], safe[:2]) > 2:
            return self._mark(bot, "zone_turn", safe)
        if fallback_goal is None:
            # A combat or evacuation tick must not advance the loot pursuit timer.
            fallback_goal = bot._goal(obs, stats)
        if not squad and bot.mode in ("explore", "zone", "recover", "disengage"):
            anchor = self._anchor(bot, obs, stats)
            if anchor is not None:
                return self._mark(bot, "concealed_home", anchor)
        return fallback_goal

    def motion(self, bot, obs, action):
        if bot.match_policy != "adaptive":
            return action
        me = obs["self"]
        if self.intent == "island_approach" and self.approach_point and me["grounded"]:
            p = self.approach_point
            dx, dy = unit(p[0] - me["pos"][0], p[1] - me["pos"][1])
            if action["move"][0] * dx + action["move"][1] * dy < 0.3:
                action["move"] = [dx, dy]
            action["jump"] = False
            action["boost"] = False
        elif self.intent == "roof_escape" and self.launch:
            landing, height, _ = self.launch
            ux, uy = unit(landing[0] - me["pos"][0], landing[1] - me["pos"][1])
            if not me["grounded"] and math.dist(me["pos"][:2], landing[:2]) < 1.5:
                action.update(move=[0.0, 0.0], jump=False, boost=False)
            elif me["grounded"] and me["energy"] < 0.58 * me["max_energy"]:
                action.update(move=[0.0, 0.0], jump=False, boost=False)
            else:
                action.update(
                    move=[ux, uy],
                    jump=me["grounded"],
                    boost=not me["grounded"] and me["pos"][2] < height + 0.5 and me["energy"] > 12,
                )
        elif self.intent in ("cornered", "opening_withdraw") and me["grounded"]:
            if self.corner_step:
                p = self.corner_step
                dx, dy = unit(p[0] - me["pos"][0], p[1] - me["pos"][1])
                if action["move"][0] * dx + action["move"][1] * dy < 0.35:
                    action["move"] = [dx, dy]
            elif self.intent == "cornered":
                action["move"] = [0.0, 0.0]
            if self.intent == "opening_withdraw" and math.hypot(*action["move"]) > 0.15:
                action["boost"] = me["energy"] > 0.3 * me["max_energy"]
        elif me["grounded"] and math.hypot(*action["move"]) > 0.15:
            if self.intent == "zone_must":
                action["boost"] = me["energy"] > 5 and (not me["in_zone"] or self.zone_slack <= 0)
            elif self.intent == "shell_escape":
                action["boost"] = me["energy"] > 15
        if (
            self.intent in ("fight", "finish", "fight_cube")
            and self.close_with_arc
            and math.hypot(*action["move"]) > 0.1
        ):
            action["boost"] = True
        if self.intent == "concealed_home" and obs["t"] - self.last_threat > 5 and me["in_zone"]:
            action["boost"] = False
        elif (
            self.laser_alert >= obs["t"]
            and self.intent not in ("roof_escape", "island_approach", "unstuck_step")
            and me["grounded"]
            and me["energy"] > 0.32 * me["max_energy"]
            and math.hypot(*action["move"]) > 0.2
        ):
            action["boost"] = True
        if self.bullet_step is not None and self.intent not in (
            "roof_escape",
            "unstuck_step",
            "shell_escape",
        ):
            dx, dy = self.bullet_step
            if action["move"][0] * dx + action["move"][1] * dy < 0.60:
                action["move"] = [dx, dy]
        self.last_move = tuple(action["move"])
        return action
