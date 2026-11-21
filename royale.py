"""Entry point: detect at run time whether this match is the practice squad or a free-for-all.

Practice: 15 house bots on one squad never fight each other, so before the late zone the
only mechs that die are the ones we kill. Free-for-all: other mechs die without us, and we
see beams from one mech ending on another. Until the evidence arrives we play the practice
policy; once it does we switch for the rest of the match.
"""
import mechfight as mf
import example_bot as eb
import duel_bot
import math
import time
from typing import NamedTuple

# Deterministic play: wide time caps so per-call work limits decide, not the wall clock.
eb.PLAN_BUDGET_S = 0.010
eb.ROUTE_SLICE_S = 0.004
from example_bot import obj, seq, number, vec, distance, bearing, angle, limit, raised

SEED = 3                    # the only source of randomness; a different value is a different draw
FORCE_MODE = None           # None = detect; "practice" or "free-for-all" pins the policy
GUARDED_OPENER = True       # squad play fights only mechs that attack or close on us
PAUSE_MED_MS = 8.0
PAUSE_MIN_MS = 4.0
PAUSE_SHOW = False
USE_PAUSE = False
USE_E = False
E_WINDOW_S = 30.0
USE_R = False
USE_H2 = False
FFA_WEDGE = True
FFA_NOT_NEAREST = True
FFA_UNSEEN_OPEN = True
FFA_QUIET_WALK = True

FFA_SIGHT_MEMORY_S = 3.0
FFA_WEDGE_MARGIN = math.radians(10)
FFA_WEDGE_COST = 40.0
FFA_LASER_MULT = 1.5
FFA_HIDDEN_REWARD = 12.0
FFA_NEAREST_COST = 25.0
FFA_NEAREST_RATIO = 0.9
FFA_POSITION_RAYS = 24
FFA_STEERING_RAYS = 12


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
    """Latch on the first pause, unexplained death, HP loss, crossfire or beam signal."""

    def __init__(self, hello):
        self.slot = number(hello.get("slot"), -1)
        self.start_alive = None
        self.kills = 0
        self.beam_times = []
        self.seen_hp = {}
        self.latest_attacker = None
        self.ffa = False
        self.reason = ""
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
            self.ffa, self.reason = True, f"pause {g_med:.1f}/{g_min:.1f} ms"
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
                self.ffa, self.reason = True, f"{others} deaths not ours at {now:.1f}s (dps {dps:.0f})"
                return True
            if USE_E and others >= 1 and now < E_WINDOW_S:
                self.ffa, self.reason = True, f"death not ours before {E_WINDOW_S:g}s at {now:.1f}s"
                return True
        if USE_R and self.other_hp_drop(obs, events):
            self.ffa, self.reason = True, f"other mech lost 45 HP at {now:.1f}s"
            return True
        if USE_H2 and self.kills == 0 and self.two_attackers(events, now):
            self.ffa, self.reason = True, f"two mechs hit us before our first kill at {now:.1f}s"
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
            self.ffa, self.reason = True, f"laser beams mech-to-mech at {self.beam_times[:2]}"
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

    def record(self, obs, pos, now):
        """Update bounded observation history without running any policy or map queries."""
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
            source = mech_attacker(event, self.slot)
            if source is not None:
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
            for ident, (_, _, point) in list(self.pickups.items()):
                if ident in self.visible_pickups:
                    continue
                d = distance(pos, point)
                expected = d <= self.near_vision + 15 * sensors - 3 or (
                    d <= self.vision + 25 * sensors - 10
                    and abs(angle(bearing(pos, point) - actual[0])) < self.half_fov - 0.10
                )
                if expected and (self.arena is None or self.arena.clear_ray(eye, raised(point, 0.5))):
                    del self.pickups[ident]

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
        for ident in sorted(recent, key=lambda i: distance_sq(pos, self.last_seen[i].pos)):
            seen = self.last_seen[ident]
            scale = 1 + size_per_cube * limit(seen.cubes or 0, 0, number(self.cubes.get("stat_cap"), 10))
            facing = (math.cos(seen.yaw), math.sin(seen.yaw)) if seen.yaw is not None else None
            weight = FFA_WEDGE_COST * (FFA_LASER_MULT if "laser" in seen.weapons else 1)
            self.observers[ident] = Observer(seen.pos, raised(seen.pos, eye * scale), facing, weight)
        if FFA_NOT_NEAREST:
            # Only destinations beyond this radius give the observer a closer rival.
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
            # A candidate with untested rays cannot claim cover.
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
        # Two rays per known opponent at most, even if the route changes during steering.
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
        return all(segment_distance_sq(pos, goal, enemy) > self.PICKUP_CLEARANCE ** 2
                   for enemy in self.known_enemies.values())

    def weapon_goal(self, pos, zone, weapons, urgent, action):
        if "laser" in self.kinds:
            return None
        spare = next((i for i, w in enumerate(weapons) if not w.get("kind")), None)
        swap = next((i for i, w in enumerate(weapons) if w.get("kind") in self.SECONDARIES), None)
        if urgent or (spare is None and swap is None):
            return None
        options = []
        reach = limit(number(self.loot.get("pickup_radius"), 4), 0.5, 15)
        for ident, (_, kind, point) in self.pickups.items():
            if kind not in self.SECONDARIES or kind in self.kinds:
                continue
            priority = self.SECONDARIES.index(kind)
            if spare is None and priority >= self.SECONDARIES.index(weapons[swap]["kind"]):
                continue
            d, climb = distance(pos, point), point[2] - pos[2]
            if d > 150 or not -65 <= climb <= 36 or (climb > 4 and self.energy <= 45):
                continue
            take = math.hypot(d, climb) <= reach and ident in self.visible_pickups
            outside = max(0, distance(point, zone.next_center) - zone.next_radius + 10)
            cost = 0 if take else d + max(0, climb - 4) * 2 + outside * 0.55
            option = priority, cost, ident, point, take
            if zone.gap(point, 0 if take else d / 9 + 4) > 0 and self.safe_pickup_route(pos, point):
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
        return point[:2]

    def loot_goal(self, obs, pos, zone, contacts, weapons, hp_fraction, cubes, safe, urgent, action):
        if self.disengage:
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
        if self.disengage:
            return pos[:2]
        if terminal_burn:
            point_score = self.position_score if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) else None
            return super().shelter_point(pos, zone, contacts, direction, radius, height, now, until, True,
                                         point_score=point_score)
        if self.farm is not None:
            return pos[:2]
        if self.goal is not None and now < self.goal_until and distance(pos, self.goal) > 3:
            if (not self.opening or distance(self.goal, zone.next_center) < zone.next_radius) and (
                    self.clear_approach(pos, self.goal, self.OPENING_CLEARANCE, strict=self.opening)):
                return self.goal

        arena = self.arena
        goal_radius = max(0, zone.next_radius - min(16, zone.next_radius * 0.22))
        next_gap = goal_radius - distance(pos, zone.next_center)
        roam = ((self.alive > 3 and self.kinds.isdisjoint(self.SECONDARIES) and self.hp_share > 0.65)
                or (self.alive == 2 and not self.rivals and self.hp_share > 0.86))
        scout = self.scout_yaw + math.floor(now / 10) * 1.91
        sx, sy = math.cos(scout), math.sin(scout)
        enemies = self.rivals
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
            # Give the best candidates under open sightlines first use of the ray budget.
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
        if self.disengage:
            return goal
        arena, pickup = self.arena, self.weapon_point
        if (arena is not None and pickup is not None and pickup[:2] == goal
                and 3.5 < pickup[2] - pos[2] and distance(pos, pickup) < 30
                and not arena.solid(raised(pos, height + 1.5))):
            self.climb = True
            return goal
        waypoint_score = self.position_score if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) else None
        waypoint = super().route(pos, goal, zone, radius, height, stuck, until, waypoint_score=waypoint_score)
        if pickup is not None:
            points = self.path[self.path_index:] if self.path and self.route_goal == goal else ()
            if not self.safe_pickup_route(pos, waypoint) or any(
                    not self.safe_pickup_route(start, end) for start, end in zip(points, points[1:])):
                self.weapon_point = None
                self.mode = "survive"
                self.search = self.route_goal = None
                self.path, self.path_index = (), 0
                return self.shelter_point(pos, zone, (), None, radius, height, zone.now, until, False)
        elif waypoint != goal and not self.clear_approach(pos, waypoint, self.OPENING_CLEARANCE if self.opening else 105):
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
        self.escape_bearings = [(span, bearing(pos, point)) for span, point in attackers]
        cover_threats = sorted(attackers)[:2] if FFA_WEDGE else attackers
        best, move = None, (0.0, 0.0)
        center, size = zone.circle_in(1.5)
        gap = size - distance(pos, center)
        next_gap = zone.next_radius - distance(pos, zone.next_center)
        for dx, dy in eb.COVER_ANGLES:
            end = pos[0] + dx * pace * 0.58 + vel[0] * 0.12, pos[1] + dy * pace * 0.58 + vel[1] * 0.12
            if arena is not None and not arena.corridor(pos, end, radius, height):
                continue
            end_gap = size - distance(end, center)
            min_gap = gap + 0.1 if urgent and gap < 0 else min(-0.2, gap - 0.2)
            if end_gap < min_gap:
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
            option = (worst > 0, score)
            if best is None or option > best:
                best, move = option, (dx * scale, dy * scale)
        if best is None:
            return None
        return {"move": list(move), "boost": boost, "jump": False}

    def movement(self, pos, vel, waypoint, zone, urgent, evade, threats, hazards, direction, stats,
                 grounded, energy, now, until, in_zone, terminal_burn, drop_hint):
        quiet = self.walk_quietly(pos)
        speed_cap = self.quiet_speed if quiet else None
        steer_score = self.steer_score if self.observers and (FFA_WEDGE or FFA_NOT_NEAREST) else None
        if self.disengage:
            escape = self.escape_move(pos, vel, waypoint, zone, hazards, stats, grounded, energy, urgent, quiet)
            if escape is not None:
                self.course = escape["move"]
                self.sprinting = escape["boost"]
                return escape
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
            projected = pos[0] + 12 * move["move"][0], pos[1] + 12 * move["move"][1]
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
        self.course = move["move"]
        self.sprinting = bool(move.get("boost"))
        return move

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
        """Estimate landed damage in 1.5 s with our current magazines, cooldowns and aim."""
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
                if self.can_open(enemy.id, pos):
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
        # A charging laser fires on release, so farm with a weapon we can stop immediately.
        if target.kind != "mech" and weapon.get("kind") != "gun":
            return None
        return super().aim_for(weapon, target, base, muzzle, pitch_bounds)

    def contacts(self, obs, pos, eye):
        contacts = super().contacts(obs, pos, eye)
        self.exposed = any(c.kind == "mech" and c.clear and c.dist < 100 for c in contacts)
        if self.alive != 2 or self.disengage:
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
        # A false trigger releases an existing charge. Hold only until the beam
        # clears any visible unauthorized target, then release and regain speed.
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
        self.course = (0.0, 0.0)
        self.escape_bearings = []
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
                self.observe(me, pos, self.actual, now)
                # Seed the inherited contact ranking with hits seen before the switch.
                self.hits.update({ident: when for ident, (when, _) in self.attackers.items()
                                  if 0 <= now - when < eb.HIT_MEMORY_S})
            self.last_fire_target = None
            action = super().act(obs)
            if pos is not None:
                if self.disengage and self.last_fire_target is None:
                    action["aim"] = [self.escape_facing(), 0.0]
                elif self.last_fire_target is None and self.weapon_point is not None and not self.exposed:
                    action["aim"] = [bearing(pos, self.weapon_point), 0.0]
                elif self.last_fire_target is None and not self.rivals and now - self.last_damage >= eb.HIT_MEMORY_S:
                    action["aim"] = [angle(self.scout_yaw + now * 1.9), 0.0]
                action.setdefault("fire", [False, False])
                self.release_laser_safely(obs, action, pos)
        except errors:
            try:
                self.duel.arena = self.arena
                action = self.duel.act(obs) or {}
                for key in ("fire", "take", "drop"):
                    action.pop(key, None)
            except errors:
                action = {}
        if offer:
            index = min(len(seq(me.get("upgrades"))), len(self.UPGRADES) - 1)
            rank = self.UPGRADES[index]
            def priority(i):
                upgrade = obj(offer[i]).get("id")
                if not isinstance(upgrade, str):
                    return 0
                if upgrade in rank:
                    return 200 - rank.index(upgrade)
                return eb.UPGRADE_RANK.get(upgrade, 0)
            action["pick"] = max(range(len(offer)), key=priority)
        return action


class Royale:
    def __init__(self, hello):
        duel_bot.SEED_SALT = SEED
        self.practice = duel_bot.DuelBot(hello)
        self.practice.guarded = GUARDED_OPENER
        self.ffa = Selective(hello)
        self.detector = Detector(hello)
        self.mode = FORCE_MODE or "practice"
        self.first_ffa = None

    def __getattr__(self, name):
        # Tools and tests that inspect the policy see the active one.
        if name in ("practice", "ffa", "detector", "mode", "first_ffa"):
            raise AttributeError(name)
        return getattr(self.ffa if self.mode == "free-for-all" else self.practice, name)

    def load_map(self):
        self.practice.load_map()
        self.ffa.arena = self.practice.arena
        return True

    def act(self, obs):
        obs = obj(obs)
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
                mf.log(f"mode {want}: {self.detector.reason}")
        if self.mode == "free-for-all":
            return self.ffa.act(obs)
        self.ffa.record(obs, vec(obj(obs.get("self")).get("pos"), 3), now)
        return self.practice.act(obs)


if __name__ == "__main__":
    mf.run(Royale, pause_show=PAUSE_SHOW)
