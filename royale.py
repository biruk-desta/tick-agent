"""Entry point: detect at run time whether this match is the practice squad or a free-for-all.

Practice: 15 house bots on one squad never fight each other, so before the late zone the
only mechs that die are the ones we kill. Free-for-all: other mechs die without us, and we
see beams from one mech ending on another. Until the evidence arrives we play the practice
policy; once it does we switch for the rest of the match.
"""
import math

import mechfight as mf
import example_bot as eb
import duel_bot
from example_bot import obj, seq, number, vec, distance

FORCE_MODE = None           # None = detect; "practice" or "free-for-all" pins the policy
SWITCH_ON = 2.5             # evidence score that selects free-for-all
SWITCH_OFF = 1.0            # score below which we fall back to practice play
HALF_LIFE_S = 120.0         # evidence fades so one odd event cannot lock a mode
PAIR_WINDOW_S = 3.0         # one credit per (kind, target) per window: a burst counts once
W_SHOT, W_BEAM, W_HP, W_DEATH, W_DEATH_LATE = 1.0, 1.5, 1.0, 0.5, 0.25


def _closest(p, v, q, horizon):
    """Closest horizontal approach of a point moving p + v t (0 <= t <= horizon) to q."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    vv = v[0] * v[0] + v[1] * v[1]
    t = 0.0 if vv < 1e-9 else limit((dx * v[0] + dy * v[1]) / vv, 0.0, horizon)
    return math.hypot(dx - v[0] * t, dy - v[1] * t)


def limit(x, lo, hi):
    return max(lo, min(hi, x))


class Detector:
    """Weighs evidence that other mechs fight each other (free-for-all) against the squad.

    Strong evidence: an enemy bullet passing far from us but into another mech; a beam from
    one mech ending on another; a visible mech losing health inside the circle when we did not
    hit it and no drone is near. Weak evidence: a death we did not cause (zone, drones and
    lost kill credit also do that). The score fades, and the mode can switch back.
    """

    def __init__(self, hello):
        self.slot = number(hello.get("slot"), -1)
        self.start_alive = None
        self.kills = 0
        self.score = 0.0
        self.last_t = None
        self.credited = {}
        self.hp = {}            # id -> (time, hp) at the previous observation only
        self.our_hits = {}      # id -> last time we hit it
        self.prev_t = None
        self.seen_projectiles = set()
        self.deaths_seen = 0
        self.ffa = False
        self.reason = ""

    def credit(self, key, weight, now, why):
        if now - self.credited.get(key, -math.inf) < PAIR_WINDOW_S:
            return
        self.credited[key] = now
        self.score += weight
        self.reason = f"{why} at {now:.1f}s (score {self.score:.1f})"

    def update(self, obs, now):
        if self.last_t is not None and now > self.last_t:
            self.score *= 0.5 ** ((now - self.last_t) / HALF_LIFE_S)
        self.last_t = now
        me_obj = obj(obs.get("self"))
        me = vec(me_obj.get("pos"), 3)
        hit_now = set()
        for event in seq(obs.get("events"))[:64]:
            event = obj(event)
            kind = event.get("type")
            if kind == "kill":
                self.kills += 1
            elif kind == "hit":
                target = number(event.get("target"), None)
                if target is not None:
                    hit_now.add(target)
                    self.our_hits[target] = now
        zone = obj(obs.get("zone"))
        dps = number(zone.get("dps"), 0)
        center = vec(zone.get("center"), 2)
        radius = number(zone.get("radius"), 0)
        alive = number(obs.get("alive"), None)
        if alive is not None:
            if self.start_alive is None:
                self.start_alive = max(alive, 1)
            others = (self.start_alive - alive) - self.kills
            while others > self.deaths_seen:
                self.deaths_seen += 1
                self.score += W_DEATH if dps <= 60 else W_DEATH_LATE
                self.reason = f"death not ours at {now:.1f}s (score {self.score:.1f})"
        mechs, npcs = [], []
        for entry in seq(obs.get("mechs"))[:48]:
            entry = obj(entry)
            p = vec(entry.get("pos"), 3)
            ident = number(entry.get("id"), None)
            if p is None or ident is None or ident == self.slot:
                continue
            if entry.get("kind") == "mech":
                mechs.append((ident, p, number(entry.get("hp"), None)))
            else:
                npcs.append(p)
        props = [p for item in seq(obs.get("crates"))[:40] if (p := vec(obj(item).get("pos"), 3)) is not None]

        def quiet(q):  # nothing else around q that a shot could have been meant for
            return all(distance(q, n) > 12 for n in npcs) and all(distance(q, c) > 8 for c in props)

        if me is not None:
            for item in seq(obs.get("projectiles"))[:64]:
                item = obj(item)
                pid = number(item.get("id"), None)
                p, v = vec(item.get("pos"), 3), vec(item.get("vel"), 3)
                if pid is None or p is None or v is None or item.get("kind") not in ("gun", "mortar"):
                    continue
                if pid in self.seen_projectiles:
                    continue
                if len(self.seen_projectiles) > 4000:
                    self.seen_projectiles.clear()
                self.seen_projectiles.add(pid)
                if _closest(p, v, me, 1.5) < 14:
                    continue
                for ident, q, _ in mechs:
                    if _closest(p, v, q, 1.5) < 4.5 and distance(p, q) > 6 and quiet(q):
                        self.credit(("shot", ident), W_SHOT, now, f"bullet into mech {ident:.0f}")
                        break
            for beam in seq(obs.get("beams"))[:32]:
                beam = obj(beam)
                path = seq(beam.get("path"))
                end = vec(path[1], 3) if len(path) >= 2 else None
                by = number(beam.get("by"), None)
                if end is None or by is None or by == self.slot or distance(end, me) < 15:
                    continue
                for ident, q, _ in mechs:
                    if ident != by and distance(end, q) < 4.5 and quiet(q):
                        self.credit(("beam", ident), W_BEAM, now, f"beam {by:.0f}->{ident:.0f}")
                        break
        previous_t, self.prev_t = self.prev_t, now
        seen_hp = {}
        for ident, q, hp in mechs:
            if hp is None:
                continue
            seen_hp[ident] = hp
            before = self.hp.get(ident)
            if before is None or previous_t is None or before[0] != previous_t or before[1] - hp < 20:
                continue
            if ident in hit_now or now - self.our_hits.get(ident, -math.inf) < 1.0:
                continue
            inside = center is not None and distance(q, center) < radius - 3
            if inside and quiet(q) and all(distance(q, n) > 60 for n in npcs):
                self.credit(("hp", ident), W_HP, now, f"mech {ident:.0f} lost {before[1] - hp:.0f} HP")
        self.hp = {ident: (now, hp) for ident, hp in seen_hp.items()}
        if not self.ffa and self.score >= SWITCH_ON:
            self.ffa = True
        elif self.ffa and self.score < SWITCH_OFF and (alive is None or alive > 4):
            self.ffa = False
        return self.ffa


class Royale:
    def __init__(self, hello):
        self.practice = duel_bot.DuelBot(hello)
        self.ffa = eb.Bot(hello)
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
        return self.practice.act(obs)


if __name__ == "__main__":
    mf.run(Royale)
