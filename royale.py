"""Entry point: detect at run time whether this match is the practice squad or a free-for-all.

Practice: 15 house bots on one squad never fight each other, so before the late zone the
only mechs that die are the ones we kill. Free-for-all: other mechs die without us, and we
see beams from one mech ending on another. Until the evidence arrives we play the practice
policy; once it does we switch for the rest of the match.
"""
import math

import mechfight as mf
import example_bot as eb
from example_bot import obj, seq, number, vec, distance

FORCE_MODE = None          # None = detect; "practice" or "free-for-all" pins the policy
OTHER_DEATHS_TO_SWITCH = 2  # deaths we did not cause while the zone is still mild
OTHER_DEATH_EARLY_S = 150.0  # one such death this early is enough
BEAMS_TO_SWITCH = 2        # beams from one mech ending on another mech, not near us
MILD_ZONE_DPS = 60.0


class Detector:
    def __init__(self, hello):
        match = obj(obj(hello.get("config")).get("match"))
        self.slot = number(hello.get("slot"), -1)
        self.mechs = number(match.get("mechs"), 16)
        self.start_alive = None
        self.kills = 0
        self.beams = 0
        self.ffa = False
        self.reason = ""

    def update(self, obs, now):
        if self.ffa:
            return True
        for event in seq(obs.get("events"))[:40]:
            if obj(event).get("type") == "kill":
                self.kills += 1
        alive = number(obs.get("alive"), None)
        dps = number(obj(obs.get("zone")).get("dps"), 0)
        if alive is not None:
            if self.start_alive is None:
                self.start_alive = max(alive, 1)
            others = (self.start_alive - alive) - self.kills
            if dps <= MILD_ZONE_DPS and (others >= OTHER_DEATHS_TO_SWITCH or (others >= 1 and now < OTHER_DEATH_EARLY_S)):
                self.ffa, self.reason = True, f"{others} deaths not ours at {now:.1f}s"
                return True
        me = vec(obj(obs.get("self")).get("pos"), 3)
        mechs = []
        for entry in seq(obs.get("mechs"))[:48]:
            entry = obj(entry)
            p = vec(entry.get("pos"), 3)
            if p is not None and entry.get("kind") == "mech":
                mechs.append((number(entry.get("id"), None), p))
        for beam in seq(obs.get("beams"))[:32]:
            beam = obj(beam)
            path = seq(beam.get("path"))
            if len(path) < 2 or me is None:
                continue
            end = vec(path[1], 3)
            by = number(beam.get("by"), None)
            if end is None or by is None or by == self.slot or distance(end, me) < 15:
                continue
            for ident, p in mechs:
                if ident != by and ident != self.slot and distance(end, p) < 4.0 and abs(end[2] - p[2] - 4) < 7:
                    self.beams += 1
                    break
        if self.beams >= BEAMS_TO_SWITCH:
            self.ffa, self.reason = True, f"{self.beams} mech-on-mech beams at {now:.1f}s"
        return self.ffa


class Royale:
    def __init__(self, hello):
        self.practice = eb.PracticeBot(hello)
        self.ffa = eb.Bot(hello)
        self.detector = Detector(hello)
        self.mode = FORCE_MODE or "practice"

    def __getattr__(self, name):
        # Tools and tests that inspect the policy see the active one.
        if name in ("practice", "ffa", "detector", "mode"):
            raise AttributeError(name)
        return getattr(self.ffa if self.mode == "free-for-all" else self.practice, name)

    def load_map(self):
        self.practice.load_map()
        self.ffa.arena = self.practice.arena
        return True

    def act(self, obs):
        obs = obj(obs)
        now = number(obs.get("t"), 0)
        if FORCE_MODE is None and self.mode == "practice" and self.detector.update(obs, now):
            self.mode = "free-for-all"
            mf.log(f"switching to free-for-all: {self.detector.reason}")
        if self.mode == "free-for-all":
            return self.ffa.act(obs)
        return self.practice.act(obs)


if __name__ == "__main__":
    mf.run(Royale)
