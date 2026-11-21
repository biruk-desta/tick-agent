"""Entry point: detect at run time whether this match is the practice squad or a free-for-all.

Practice: 15 house bots on one squad never fight each other, so before the late zone the
only mechs that die are the ones we kill. Free-for-all: other mechs die without us, and we
see beams from one mech ending on another. Until the evidence arrives we play the practice
policy; once it does we switch for the rest of the match.
"""
import mechfight as mf
import example_bot as eb
import duel_bot
from example_bot import obj, seq, number, vec, distance

FORCE_MODE = None           # None = detect; "practice" or "free-for-all" pins the policy


class Detector:
    """Strict free-for-all detector: it must stay quiet in the squad game.

    House bots never fight each other, so before the zone turns deadly a mech we did not kill
    almost never dies, and no laser beam goes from one mech into another. Only those two
    signals count here (HP loss can come from drones we cannot see; lightning arcs pick
    drones and crates too). Free-for-all once:
      - 2 deaths we did not cause while zone dps <= 35 (the first two phases), or
      - 3 such deaths while zone dps <= 100, or
      - laser beams from one mech ending on another, away from us and from drones and
        crates, seen at 2 different times.
    """

    def __init__(self, hello):
        self.slot = number(hello.get("slot"), -1)
        self.start_alive = None
        self.kills = 0
        self.beam_times = []
        self.ffa = False
        self.reason = ""
        self.score = 0.0

    def update(self, obs, now):
        if self.ffa:
            return True
        for event in seq(obs.get("events"))[:200]:
            if obj(event).get("type") == "kill":
                self.kills += 1
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
        for beam in seq(obs.get("beams"))[:32]:
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
