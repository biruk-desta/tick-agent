"""mechfight/1 bot wrapper. One file, standard library only (Python 3.9+): copy it next to your bot.

    import mechfight as mf

    class Bot:
        def __init__(self, hello: mf.Hello): ...
        def act(self, obs: mf.Observation) -> mf.Action:
            return {"move": [1, 0]}

    mf.run(Bot)

What run() does for you (protocol.md section 2):
- answers `hello` with `ready` (your class's `name`), then calls act() for each observation;
- if observations queue up, answers the newest one in a bounded input batch;
- sets `tick` on your action (you don't have to);
- bounds incoming lines and decision time, with map-free steering on failure;
- exits on `end`.

The types below are generated from mechfight.schema.json; they are TypedDicts, so at runtime every
message is a plain dict. Fields may be added to the protocol: read them with .get() if unsure.
"""
from __future__ import annotations

import json
import gc
import math
import os
import select
import signal
import statistics
import sys
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

try:
    from typing import NotRequired
except ImportError:  # Python < 3.11: only type checkers read it (annotations are lazy above)
    pass

MAX_LINE = 64 * 1024
INPUT_DRAIN_S = 0.004
INPUT_FRAME_LIMIT = 8
DECISION_LIMIT_S = 0.014
WRITE_RESERVE_S = 0.002
INIT_LIMIT_S = 6.0
pause_ms = (None, None)  # Median and minimum of the first ten eligible gaps.

# --- generated from mechfight.schema.json: do not edit ---
# Every message a bot sends the server.
BotMessage = Union["Ready", "Action"]
# A color: "#rgb" or "#rrggbb". Anything else is replaced by your mech's color.
Color = str
# cookoff: laser on a mortar carrier. short: lightning on a laser carrier. concuss: any mortar blast.
EffectName = Literal["cookoff", "short", "concuss"]
GameEvent = Union["DamagedEvent", "HitEvent", "EffectEvent", "DropEvent", "KillEvent", "PickupEvent", "UpgradeEvent", "TookEvent", "DroppedEvent", "TakeFailedEvent"]
MechStats = Dict[str, float]
# Every message the server sends a bot.
ServerMessage = Union["Hello", "Observation", "EndMsg"]
Vec2 = List[float]
Vec3 = List[float]
WeaponKind = Literal["gun", "mortar", "laser", "lightning"]

class Action(TypedDict):
    type: NotRequired[Literal["action"]]
    # echo the observation tick; stale answers are dropped
    tick: float
    # desired horizontal direction in world frame, length <= 1
    move: NotRequired[Vec2]
    boost: NotRequired[bool]
    jump: NotRequired[bool]
    # desired [yaw, pitch]; the torso slews toward it at turn_rate
    aim: NotRequired[Vec2]
    fire: NotRequired[List[bool]]
    reload: NotRequired[bool]
    # index into the current offer's choices
    pick: NotRequired[float]
    # id of a weapon pickup within loot.pickup_radius
    take: NotRequired[float]
    # slot (0/1) to empty: with `take`, the slot the new weapon replaces; alone, just drops it
    drop: NotRequired[float]
    # debug drawing, shown only to your team; never affects the match
    debug: NotRequired[DebugDraw]

class ActorObs(TypedDict):
    id: float
    kind: Literal["mech", "npc"]
    pos: Vec3
    vel: Vec3
    aim: Vec2
    hp: NotRequired[float]
    max_hp: NotRequired[float]
    cubes: NotRequired[float]
    # weapons held (empty slots omitted)
    weapons: NotRequired[List[WeaponKind]]
    # laser charging (telegraph)
    charging: NotRequired[bool]

class BeamObs(TypedDict):
    """an instant shot (laser beam or lightning arc) by another mech, from its muzzle along `path`"""
    by: float
    kind: Literal["laser", "lightning"]
    path: List[Vec3]
    age: float

class ConfigVision(TypedDict):
    range: float
    fov_deg: float
    near_range: float
    canopy_blocks: bool
    show_enemy_hp: bool
    memory_s: NotRequired[float]

class ConfigSound(TypedDict):
    bearing_noise_deg: float
    near: float
    mid: float
    step_speed: float
    step_every: float
    range: Dict[str, float]

class ConfigWeapons(TypedDict):
    gun: Dict[str, float]
    mortar: Dict[str, float]
    laser: Dict[str, float]
    lightning: Dict[str, float]

class ConfigCubes(TypedDict):
    upgrade_thresholds: List[float]

class ConfigLootWeights(TypedDict):
    gun: float
    mortar: float
    laser: float
    lightning: float

class ConfigLoot(TypedDict):
    pickup_radius: float
    equip_s: float
    floor_count: float
    floor_roof_fraction: float
    crate_weapon_chance: float
    death_drop: float
    weights: ConfigLootWeights

class ConfigDrops(TypedDict):
    """Supply drops (optional: absent = none)."""
    times: List[float]
    fall_s: float
    radius: float
    capture_s: float
    cubes: float
    repair: float
    spread: float

class ConfigZone(TypedDict):
    start_center: List[float]
    start_radius: float
    phases: List[ZonePhase]

class Config(TypedDict):
    match: Dict[str, float]
    bot: Dict[str, float]
    mech: MechStats
    vision: ConfigVision
    sound: ConfigSound
    weapons: ConfigWeapons
    projectile: Dict[str, float]
    cubes: ConfigCubes
    crates: Dict[str, float]
    loot: ConfigLoot
    npc: Dict[str, float]
    # Supply drops (optional: absent = none).
    drops: NotRequired[ConfigDrops]
    zone: ConfigZone
    replay: Dict[str, float]
    # Caps on action.debug: the server silently cuts each decision's drawing to these.
    debug: DebugCaps
    upgrades: List[UpgradeDef]

class DamagedEvent(TypedDict):
    """You took damage."""
    type: Literal["damaged"]
    amount: float
    # gun, mortar, laser, lightning, npc or zone
    weapon: str
    # world-frame yaw toward the source (null for the zone)
    bearing: Optional[float]
    # attacker id (null for the zone)
    by: Optional[float]
    # it came from outside your front arc (x mech.rear_mult)
    rear: NotRequired[bool]

class DebugCaps(TypedDict):
    """Caps on the debug drawing a bot may attach to an action."""
    max_lines: float
    max_points: float
    max_text: float
    max_text_chars: float
    max_bytes: float
    max_match_bytes: float
    hold_s: float

class DebugDraw(TypedDict):
    """Debug drawing for one decision. Stays on screen until your next decision that carries `debug`, or `debug.hold_s` seconds, whichever comes first; send `{}` to clear it early. The server truncates to the `[debug]` caps in hello.config (item counts, text length, bytes per decision, bytes per match) without telling you. It is recorded to a file only your team can download, never to the public replay, and has no effect on the match."""
    lines: NotRequired[List[DebugLine]]
    points: NotRequired[List[DebugPoint]]
    text: NotRequired[List[DebugText]]
    # one short status line drawn above your mech
    label: NotRequired[str]

class DebugLine(TypedDict):
    """A line segment from world point `a` to `b` (x east, y north, z up, meters)."""
    a: Vec3
    b: Vec3
    color: NotRequired[Color]

class DebugPoint(TypedDict):
    """A dot at a world point. `size` is its radius in screen pixels (1..12, default 4)."""
    at: Vec3
    color: NotRequired[Color]
    size: NotRequired[float]

class DebugText(TypedDict):
    """A text label. With `at`, drawn at that world point; without, stacked above your mech."""
    text: str
    at: NotRequired[Vec3]
    color: NotRequired[Color]

class DropEvent(TypedDict):
    """You captured supply drop `id`; `cubes` is your new total."""
    type: Literal["drop"]
    id: float
    cubes: float

class DropObs(TypedDict):
    """A supply drop. Known to every mech from the moment it is called, like the zone."""
    id: float
    pos: Vec3
    # stand inside this, alone, for capture_s
    radius: float
    # seconds until it can be captured (0 = on the ground)
    lands_in: float
    capture_s: float
    # seconds the current holder has banked
    progress: float
    # mech currently capturing
    holder: Optional[float]

class DroppedEvent(TypedDict):
    """A weapon left your `slot` and lies on the ground as pickup `id`."""
    type: Literal["dropped"]
    id: float
    kind: WeaponKind
    slot: float

class Effect(TypedDict):
    path: str
    mul: NotRequired[float]
    add: NotRequired[float]

class EffectEvent(TypedDict):
    """A signature effect landed on you."""
    type: Literal["effect"]
    effect: EffectName
    by: Optional[float]

class EndMsg(TypedDict):
    type: Literal["end"]
    place: float
    kills: float

class HelloMap(TypedDict):
    dir: str
    files: List[str]

class Hello(TypedDict):
    type: Literal["hello"]
    protocol: Literal["mechfight/1"]
    # your mech id, 0..15
    slot: float
    # per-bot seed, use it for your own RNG to stay reproducible
    seed: float
    map: HelloMap
    config: Config

class HitEvent(TypedDict):
    """You damaged `target` (a mech, NPC or crate id)."""
    type: Literal["hit"]
    target: float
    amount: float
    weapon: str
    effect: NotRequired[EffectName]
    rear: NotRequired[bool]

class ItemObs(TypedDict):
    id: float
    pos: Vec3
    hp: NotRequired[float]

class KillEvent(TypedDict):
    """You killed a mech."""
    type: Literal["kill"]
    target: float

class Observation(TypedDict):
    type: Literal["obs"]
    tick: float
    # match time, seconds
    t: float
    # mechs alive (not NPCs)
    alive: float
    self: SelfObs
    # visible mechs and NPCs
    mechs: List[ActorObs]
    projectiles: List[ProjectileObs]
    crates: List[ItemObs]
    cubes: List[ItemObs]
    # visible weapons on the ground
    pickups: List[PickupObs]
    sounds: List[SoundObs]
    # laser beams and lightning arcs by other mechs that you saw (any point of the path in view) since your last observation
    beams: List[BeamObs]
    events: List[GameEvent]
    zone: ZoneObs
    offer: Optional[Offer]
    # supply drops called or on the ground
    drops: List[DropObs]

class Offer(TypedDict):
    id: float
    choices: List[OfferChoice]
    expires: float

class OfferChoice(TypedDict):
    id: str
    name: str
    desc: str

class PickupEvent(TypedDict):
    """You picked up a cube; `cubes` is your new total."""
    type: Literal["pickup"]
    cubes: float

class PickupObs(TypedDict):
    """A weapon lying on the ground. Take it with the `take` action."""
    id: float
    kind: WeaponKind
    pos: Vec3

class ProjectileObs(TypedDict):
    id: float
    kind: Literal["gun", "mortar", "npc"]
    pos: Vec3
    vel: Vec3

class Ready(TypedDict):
    type: Literal["ready"]
    name: NotRequired[str]

class SelfObs(TypedDict):
    id: float
    pos: Vec3
    vel: Vec3
    # [yaw, pitch] actual (slewed) aim
    aim: Vec2
    hp: float
    max_hp: float
    energy: float
    max_energy: float
    grounded: bool
    cubes: float
    upgrades: List[str]
    # null = empty slot
    weapons: List[Optional[WeaponObs]]
    in_zone: bool
    # your current [mech] numbers after upgrades
    stats: Dict[str, float]

class SoundObs(TypedDict):
    kind: str
    bearing: float
    dist: Literal["near", "mid", "far"]
    age: float

class TakeFailedEvent(TypedDict):
    """Your `take` didn't happen."""
    type: Literal["take_failed"]
    id: float
    reason: Literal["gone", "range", "have", "full", "busy"]

class TookEvent(TypedDict):
    """Your `take` succeeded: pickup `id` is now in `slot`."""
    type: Literal["took"]
    id: float
    kind: WeaponKind
    slot: float

class UpgradeDef(TypedDict):
    id: str
    name: str
    desc: str
    requires: NotRequired[WeaponKind]
    max: float
    effects: List[Effect]

class UpgradeEvent(TypedDict):
    """An upgrade was applied."""
    type: Literal["upgrade"]
    id: str

class WeaponObs(TypedDict):
    kind: WeaponKind
    # seconds until it can fire again
    cooldown: float
    # gun only
    ammo: NotRequired[float]
    # gun only: seconds of reload left (0 = not reloading)
    reload: NotRequired[float]
    # laser only: seconds charged so far (0 = not charging); it fires at weapons.laser.charge, or on release after min_charge
    charge: NotRequired[float]
    # this weapon's [weapons.<kind>] numbers after upgrades
    stats: Dict[str, float]

class ZoneObs(TypedDict):
    center: Vec2
    radius: float
    next_center: Vec2
    next_radius: float
    # match time (s) the current shrink starts (or started)
    shrink_start: float
    shrink_end: float
    dps: float

class ZonePhase(TypedDict):
    hold_s: float
    shrink_s: float
    radius: float
    dps: float
# --- end generated ---


class DeadlineExceeded(BaseException):
    pass


_watchdog_active = False


def _interrupt(_signum, _frame):
    if _watchdog_active:
        raise DeadlineExceeded


def _watched(seconds, work, *args):
    global _watchdog_active
    try:
        try:
            _watchdog_active = True
            signal.setitimer(signal.ITIMER_REAL, seconds)
            return work(*args)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            _watchdog_active = False
    except (DeadlineExceeded, Exception):
        _watchdog_active = False
        return None


def _pair(value):
    if isinstance(value, list) and len(value) >= 2:
        x, y = value[:2]
        if all(type(n) in (int, float) and -1e9 <= n <= 1e9 for n in (x, y)):
            return x, y
    return None


def _fallback(obs, tick):
    me = obs.get("self")
    zone = obs.get("zone")
    me = me if isinstance(me, dict) else {}
    zone = zone if isinstance(zone, dict) else {}
    pos, center = _pair(me.get("pos")), _pair(zone.get("center"))
    action = {"tick": tick, "move": [0.0, 0.0], "aim": _pair(me.get("aim")) or [0.0, 0.0]}
    if pos is not None and center is not None:
        dx, dy = center[0] - pos[0], center[1] - pos[1]
        distance = math.hypot(dx, dy)
        radius = zone.get("radius")
        at_edge = type(radius) in (int, float) and 0 <= radius <= 1e9 and distance >= radius * 0.72
        if distance and (me.get("in_zone") is False or at_edge):
            scale = max(distance, 3.0)
            action["move"] = [dx / scale, dy / scale]
            action["aim"] = [math.atan2(dy, dx), 0.0]
    return action


def log(*args: Any) -> None:
    """print() to stderr: stdout is the protocol. Your team sees stderr after each match."""
    print(*args, file=sys.stderr, flush=True)


def _encode(msg):
    return json.dumps(msg, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def _send(fd, payload, deadline):
    # Frames fit in PIPE_BUF, so the unbuffered write either flushes a whole line
    # or leaves stdout untouched. A slow reader cannot hold up later decisions.
    while True:
        try:
            return time.perf_counter() if os.write(fd, payload) == len(payload) else None
        except BlockingIOError:
            remaining = deadline - time.perf_counter()
            if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                return
        except OSError:
            return


def _lines(fd):
    pending = bytearray()
    started = None
    discarding = False
    while True:
        chunk = os.read(fd, 32768)
        if not chunk:
            yield None, None
            return
        received = time.perf_counter()
        parts = chunk.split(b"\n")
        for part in parts[:-1]:
            if not discarding and len(pending) + len(part) <= MAX_LINE:
                yield bytes(pending) + part, started if started is not None else received
            pending.clear()
            started = None
            discarding = False
        tail = parts[-1]
        if not discarding and tail:
            if len(pending) + len(tail) <= MAX_LINE:
                pending.extend(tail)
                if started is None:
                    started = received
            else:
                pending.clear()
                discarding = True
        # Give the caller a deadline check even in the middle of an oversized line.
        yield None, received if select.select([fd], [], [], 0)[0] else None


def _decision(bot, obs, tick):
    action = bot.act(obs)
    if isinstance(action, dict) and action:
        return _encode({**action, "tick": tick})
    return None


def run(make_bot: Any) -> None:
    """Run a bot until end or EOF, with a watchdog around each decision."""
    global pause_ms
    pause_ms = (None, None)
    # Each process runs a single match. The JSON and policy state are acyclic.
    gc.disable()
    signal.signal(signal.SIGALRM, _interrupt)
    stdout = sys.stdout.fileno()
    os.set_blocking(stdout, False)
    frame_limit = os.fpathconf(stdout, "PC_PIPE_BUF")
    bot = None
    handshaken = False
    decide_every = 2
    last_tick = -2
    last_sent = None
    observations = 0
    gaps = []
    latest = None
    batch_start = None
    frames = 0
    for raw, received in _lines(sys.stdin.fileno()):
        if raw is not None:
            try:
                msg = json.loads(raw)
            except (ValueError, RecursionError):
                msg = None
            if isinstance(msg, dict):
                kind = msg.get("type")
                if kind == "hello" and not handshaken:
                    handshaken = True
                    config = msg.get("config")
                    match = config.get("match") if isinstance(config, dict) else None
                    stride = match.get("decide_every") if isinstance(match, dict) else None
                    if type(stride) in (int, float) and 1 <= stride <= 1e15 and stride == int(stride):
                        decide_every = stride
                    bot = _watched(INIT_LIMIT_S, make_bot, msg)
                    if bot is None:
                        log("Bot initialization failed. Using map-free steering.")
                    load_map = getattr(bot, "load_map", None)
                    if load_map is not None and _watched(INIT_LIMIT_S, load_map) is None:
                        log("Arena unavailable. Using the full policy without map routing.")
                    _send(stdout, b'{"type":"ready"}\n', time.perf_counter() + DECISION_LIMIT_S)
                elif kind == "obs":
                    queued = latest is not None
                    if not queued:
                        batch_start = received
                    observations += 1
                    latest = msg
                elif kind == "end":
                    return
        if latest is None:
            continue
        if raw is not None:
            frames += 1
        if (received is not None and frames < INPUT_FRAME_LIMIT
                and time.perf_counter() < batch_start + INPUT_DRAIN_S):
            continue
        obs = latest
        latest = None
        frames = 0
        deadline = batch_start + DECISION_LIMIT_S
        tick = obs.get("tick")
        valid_tick = type(tick) in (int, float) and -1e15 <= tick <= 1e15
        if not valid_tick:
            tick = last_tick + 2
        if gaps is not None:
            now = obs.get("t")
            if type(now) in (int, float):
                if (0 <= now <= 3.0 and observations > 2 and not queued and valid_tick
                        and tick == last_tick + decide_every and last_sent is not None
                        and batch_start >= last_sent):
                    gaps.append((batch_start - last_sent) * 1000)
                if len(gaps) == 10:
                    pause_ms = (statistics.median(gaps), min(gaps))
                    gaps = None
                elif now >= 3.0:
                    gaps = None
        last_tick = tick
        remaining = deadline - WRITE_RESERVE_S - time.perf_counter()
        payload = (_watched(remaining, _decision, bot, obs, tick)
                   if bot is not None and remaining > 0 else None)
        if payload is None or len(payload) > frame_limit:
            payload = _encode(_fallback(obs, tick))
        sent = _send(stdout, payload, deadline)
        last_sent = sent if valid_tick else None


if __name__ == "__main__":
    log("mechfight.py is a library: import it from your bot and call run()")
