"""mechfight/1 bot wrapper. One file, standard library only (Python 3.9+): copy it next to your bot.

    import mechfight as mf

    class Bot:
        def __init__(self, hello: mf.Hello): ...
        def act(self, obs: mf.Observation) -> mf.Action:
            return {"move": [1, 0]}

    mf.run(Bot)

What run() does for you (protocol.md section 2):
- answers `hello` with `ready` (your class's `name`), then calls act() for each observation;
- if observations queue up, answers only the newest one;
- sets `tick` on your action (you don't have to);
- bounds incoming lines and decision time, with a minimal valid action on decision failure;
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
import sys
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

try:
    from typing import NotRequired
except ImportError:  # Python < 3.11: only type checkers read it (annotations are lazy above)
    pass

MAX_LINE = 64 * 1024
MAX_BATCH_BYTES = 2 * MAX_LINE
MAX_BATCH_LINES = 8
READ_BATCH_S = 0.003
DECISION_LIMIT_S = 0.014
INIT_LIMIT_S = 6.0

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


class DeadlineExceeded(Exception):
    pass


def _interrupt(_signum, _frame):
    raise DeadlineExceeded


def log(*args: Any) -> None:
    """print() to stderr: stdout is the protocol. Your team sees stderr after each match."""
    print(*args, file=sys.stderr, flush=True)


def _send(msg: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(msg, separators=(",", ":"), allow_nan=False) + "\n")
    sys.stdout.flush()


def _batches(fd):
    pending = bytearray()
    discarding = False
    while True:
        lines = []
        remaining = MAX_BATCH_BYTES
        until = None
        while remaining:
            chunk = os.read(fd, min(32768, remaining))
            if not chunk:
                break
            if until is None:
                until = time.perf_counter() + READ_BATCH_S
            remaining -= len(chunk)
            parts = chunk.split(b"\n")
            for part in parts[:-1]:
                if not discarding and len(pending) + len(part) <= MAX_LINE:
                    lines.append(bytes(pending) + part)
                pending.clear()
                discarding = False
            tail = parts[-1]
            if not discarding:
                if len(pending) + len(tail) <= MAX_LINE:
                    pending.extend(tail)
                else:
                    pending.clear()
                    discarding = True
            if time.perf_counter() >= until or not select.select([fd], [], [], 0)[0]:
                break
        if lines:
            # Keep the first line for a coalesced handshake and the newest work at the end.
            yield lines if len(lines) <= MAX_BATCH_LINES else [lines[0], *lines[1 - MAX_BATCH_LINES:]]
        if not chunk:
            return


def run(make_bot: Any) -> None:
    """Run a bot until end or EOF, with a watchdog around each decision."""
    # Each process runs a single match. The JSON and policy state are acyclic.
    gc.disable()
    signal.signal(signal.SIGALRM, _interrupt)
    bot = None
    handshaken = False
    last_tick = -2
    for batch in _batches(sys.stdin.fileno()):
        latest = None
        for raw in batch:
            try:
                msg = json.loads(raw)
            except (ValueError, RecursionError):
                continue
            if not isinstance(msg, dict):
                continue
            kind = msg.get("type")
            if kind == "hello" and not handshaken:
                handshaken = True
                try:
                    signal.setitimer(signal.ITIMER_REAL, INIT_LIMIT_S)
                    bot = make_bot(msg)
                except Exception:
                    log("Bot initialization failed. Using protocol fallback.")
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                _send({"type": "ready"})
            elif kind == "obs":
                latest = msg
            elif kind == "end":
                return
        if latest is None:
            continue
        tick = latest.get("tick")
        if type(tick) not in (int, float) or not -1e15 <= tick <= 1e15 or not math.isfinite(tick):
            tick = last_tick + 2
        last_tick = tick
        action = {"tick": tick}
        if bot is not None:
            try:
                signal.setitimer(signal.ITIMER_REAL, DECISION_LIMIT_S)
                action.update(bot.act(latest))
                action["tick"] = tick
            except DeadlineExceeded:
                action = {"tick": tick}
            except Exception:
                action = {"tick": tick}
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            _send(action)
        except (TypeError, ValueError):
            _send({"tick": tick})


if __name__ == "__main__":
    log("mechfight.py is a library: import it from your bot and call run()")
