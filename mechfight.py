




















from __future__ import annotations

import json
import gc
import math
import os
import select
import signal
import re
import statistics
import sys
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

try:
    from typing import NotRequired
except ImportError:  
    pass

MAX_LINE = 64 * 1024
INPUT_DRAIN_S = 0.004
INPUT_FRAME_LIMIT = 8
DECISION_LIMIT_S = 0.014
ORDERED_DECISION_LIMIT_S = 0.035
WRITE_RESERVE_S = 0.002
INIT_LIMIT_S = 15.0
pause_ms = (None, None)  
start_gap_ms = None  
init_ms = None  
start_gap_waited = None  



BotMessage = Union["Ready", "Action"]

Color = str

EffectName = Literal["cookoff", "short", "concuss"]
GameEvent = Union["DamagedEvent", "HitEvent", "EffectEvent", "DropEvent", "KillEvent", "PickupEvent", "UpgradeEvent", "TookEvent", "DroppedEvent", "TakeFailedEvent"]
MechStats = Dict[str, float]

ServerMessage = Union["Hello", "Observation", "EndMsg"]
Vec2 = List[float]
Vec3 = List[float]
WeaponKind = Literal["gun", "mortar", "laser", "lightning"]

class Action(TypedDict):
    type: NotRequired[Literal["action"]]
    
    tick: float
    
    move: NotRequired[Vec2]
    boost: NotRequired[bool]
    jump: NotRequired[bool]
    
    aim: NotRequired[Vec2]
    fire: NotRequired[List[bool]]
    reload: NotRequired[bool]
    
    pick: NotRequired[float]
    
    take: NotRequired[float]
    
    drop: NotRequired[float]
    
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
    
    weapons: NotRequired[List[WeaponKind]]
    
    charging: NotRequired[bool]

class BeamObs(TypedDict):
    
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
    
    drops: NotRequired[ConfigDrops]
    zone: ConfigZone
    replay: Dict[str, float]
    
    debug: DebugCaps
    upgrades: List[UpgradeDef]

class DamagedEvent(TypedDict):
    
    type: Literal["damaged"]
    amount: float
    
    weapon: str
    
    bearing: Optional[float]
    
    by: Optional[float]
    
    rear: NotRequired[bool]

class DebugCaps(TypedDict):
    
    max_lines: float
    max_points: float
    max_text: float
    max_text_chars: float
    max_bytes: float
    max_match_bytes: float
    hold_s: float

class DebugDraw(TypedDict):
    
    lines: NotRequired[List[DebugLine]]
    points: NotRequired[List[DebugPoint]]
    text: NotRequired[List[DebugText]]
    
    label: NotRequired[str]

class DebugLine(TypedDict):
    
    a: Vec3
    b: Vec3
    color: NotRequired[Color]

class DebugPoint(TypedDict):
    
    at: Vec3
    color: NotRequired[Color]
    size: NotRequired[float]

class DebugText(TypedDict):
    
    text: str
    at: NotRequired[Vec3]
    color: NotRequired[Color]

class DropEvent(TypedDict):
    
    type: Literal["drop"]
    id: float
    cubes: float

class DropObs(TypedDict):
    
    id: float
    pos: Vec3
    
    radius: float
    
    lands_in: float
    capture_s: float
    
    progress: float
    
    holder: Optional[float]

class DroppedEvent(TypedDict):
    
    type: Literal["dropped"]
    id: float
    kind: WeaponKind
    slot: float

class Effect(TypedDict):
    path: str
    mul: NotRequired[float]
    add: NotRequired[float]

class EffectEvent(TypedDict):
    
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
    
    slot: float
    
    seed: float
    map: HelloMap
    config: Config

class HitEvent(TypedDict):
    
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
    
    type: Literal["kill"]
    target: float

class Observation(TypedDict):
    type: Literal["obs"]
    tick: float
    
    t: float
    
    alive: float
    self: SelfObs
    
    mechs: List[ActorObs]
    projectiles: List[ProjectileObs]
    crates: List[ItemObs]
    cubes: List[ItemObs]
    
    pickups: List[PickupObs]
    sounds: List[SoundObs]
    
    beams: List[BeamObs]
    events: List[GameEvent]
    zone: ZoneObs
    offer: Optional[Offer]
    
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
    
    type: Literal["pickup"]
    cubes: float

class PickupObs(TypedDict):
    
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
    
    aim: Vec2
    hp: float
    max_hp: float
    energy: float
    max_energy: float
    grounded: bool
    cubes: float
    upgrades: List[str]
    
    weapons: List[Optional[WeaponObs]]
    in_zone: bool
    
    stats: Dict[str, float]

class SoundObs(TypedDict):
    kind: str
    bearing: float
    dist: Literal["near", "mid", "far"]
    age: float

class TakeFailedEvent(TypedDict):
    
    type: Literal["take_failed"]
    id: float
    reason: Literal["gone", "range", "have", "full", "busy"]

class TookEvent(TypedDict):
    
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
    
    type: Literal["upgrade"]
    id: str

class WeaponObs(TypedDict):
    kind: WeaponKind
    
    cooldown: float
    
    ammo: NotRequired[float]
    
    reload: NotRequired[float]
    
    charge: NotRequired[float]
    
    stats: Dict[str, float]

class ZoneObs(TypedDict):
    center: Vec2
    radius: float
    next_center: Vec2
    next_radius: float
    
    shrink_start: float
    shrink_end: float
    dps: float

class ZonePhase(TypedDict):
    hold_s: float
    shrink_s: float
    radius: float
    dps: float



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


def _watch_ordered(seconds, work, *args):
    global _watchdog_active
    try:
        _watchdog_active = True
        signal.setitimer(signal.ITIMER_REAL, seconds)
        return work(*args)
    finally:
        _watchdog_active = False
        signal.setitimer(signal.ITIMER_REAL, 0)


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
    
    print(*args, file=sys.stderr, flush=True)


def _encode(msg):
    return json.dumps(msg, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def _send(fd, payload, deadline):
    
    
    while True:
        try:
            return time.perf_counter() if os.write(fd, payload) == len(payload) else None
        except BlockingIOError:
            remaining = deadline - time.perf_counter()
            if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                return
        except OSError:
            return


def _lines(fd, *, complete_timestamp=False):
    use_complete_time = complete_timestamp if callable(complete_timestamp) else lambda: complete_timestamp
    pending = bytearray()
    started = None
    discarding = False
    while True:
        chunk = os.read(fd, 32768)
        if not chunk:
            if not use_complete_time():
                yield None, None
            return
        received = time.perf_counter()
        parts = chunk.split(b"\n")
        for part in parts[:-1]:
            if not discarding and len(pending) + len(part) <= MAX_LINE:
                timestamp = received if started is None or use_complete_time() else started
                yield bytes(pending) + part, timestamp
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
        
        yield None, received if select.select([fd], [], [], 0)[0] else None


def _observation_tick(obs, default_tick):
    tick = obs.get("tick")
    valid = type(tick) in (int, float) and -1e15 <= tick <= 1e15
    return (tick if valid else default_tick), valid


class _QueuedInput:
    def __init__(self, fd, lines, default_tick):
        self.fd = fd
        self.lines = lines
        self.default_tick = default_tick
        self.buffered = True
        self.count = 0
        self.latest = None

    def drain(self):
        while self.fd is not None and (self.buffered or select.select([self.fd], [], [], 0)[0]):
            item = next(self.lines, None)
            if item is None:
                self.fd = None
                return
            raw, received = item
            self.buffered = received is not None
            if raw is None:
                continue
            try:
                msg = json.loads(raw)
            except (ValueError, RecursionError):
                continue
            if isinstance(msg, dict):
                kind = msg.get("type")
                if kind == "end":
                    self.fd = None
                elif kind == "obs":
                    tick, valid = _observation_tick(msg, self.default_tick)
                    self.latest = msg, tick, valid, received
                    self.count += 1
                    yield msg, raw + b"\n", tick, received


def _encode_action(action, obs, pause_show):
    g_med, g_min = pause_ms
    now = obs.get("t")
    if pause_show and g_med is not None and type(now) in (int, float) and 1.3 <= now < 3.7:
        gap = g_med if now < 2.5 else g_min
        action["aim"] = [math.radians(-170 + 5 * min(gap, 68)), 0.0]
        action["fire"] = [False, False]
    return _encode(action)


def _decision(bot, obs, tick, pause_show, *args):
    action = bot.act(obs, *args)
    if isinstance(action, dict) and action:
        return _encode_action({**action, "tick": tick}, obs, pause_show)
    return None


def _construct(make_bot, msg, raw, relay, zone_schedule=False):
    if zone_schedule:
        bot = make_bot(msg)
        if relay is not None and bot.mode in ("practice", "undecided"):
            relay.start(raw + b"\n")
        return bot
    if relay is not None:
        relay.start(raw + b"\n")
    return make_bot(msg)


def run(make_bot: Any, *, pause_show: bool = False, practice_wire: bool = False,
        raw_wire: Any = None, practice_router: Any = None, zone_schedule: bool = False,
        ordered_decisions: bool = False) -> None:
    
    global pause_ms, start_gap_ms, init_ms, start_gap_waited
    pause_ms = (None, None)
    start_gap_ms = init_ms = start_gap_waited = None
    hello_at = ready_at = None
    queued_at_wait = False
    if ordered_decisions:
        pause_show = False
    gc.disable()
    signal.signal(signal.SIGALRM, _interrupt)
    stdin, stdout = sys.stdin.fileno(), sys.stdout.fileno()
    os.set_blocking(stdout, False)
    frame_limit = os.fpathconf(stdout, "PC_PIPE_BUF")
    bot = None
    handshaken = False
    decide_every = 2
    last_tick = -2
    last_sent = None
    observations = 0
    gaps = None if ordered_decisions else []
    last_complete = None
    last_ordered_tick = None
    deadline_hits = 0
    latest = None
    batch_start = None
    frames = 0
    default_observation = False
    complete_timestamp = raw_wire is not None
    routed_relay = practice_router is not None and bool(practice_router.relays)
    if zone_schedule or routed_relay:
        
        complete_timestamp = lambda: raw_wire is not None or (routed_relay and practice_router is not None)
    lines = _lines(stdin, complete_timestamp=complete_timestamp)
    for raw, received in lines:
        early_ffa = False
        if raw is not None:
            try:
                msg = json.loads(raw)
            except (ValueError, RecursionError):
                msg = None
                if (practice_wire and (bot is None or bot.mode == "practice")
                        and re.search(rb'"type"\s*:\s*"obs"', raw)):
                    match = re.search(rb'"tick"\s*:\s*(-?\d{1,16})(?![\d.])', raw)
                    if latest is None:
                        batch_start = received
                    latest = {"tick": int(match[1])} if match else {}
                    default_observation = True
            if isinstance(msg, dict):
                kind = msg.get("type")
                if kind == "hello" and not handshaken:
                    handshaken = True
                    config = msg.get("config")
                    match = config.get("match") if isinstance(config, dict) else None
                    stride = match.get("decide_every") if isinstance(match, dict) else None
                    if type(stride) in (int, float) and 1 <= stride <= 1e15 and stride == int(stride):
                        decide_every = stride
                    started = time.perf_counter()
                    hello_at = received
                    bot = _watched(INIT_LIMIT_S, _construct, make_bot, msg, raw,
                                   raw_wire if raw_wire is not None else practice_router,
                                   zone_schedule)
                    constructed = time.perf_counter()
                    if zone_schedule and bot is not None and bot.mode == "free-for-all":
                        raw_wire = practice_router = None
                        practice_wire = False
                    if bot is None:
                        log("Bot initialization failed.")
                    load_map = getattr(bot, "load_map", None)
                    map_elapsed = 0.0
                    if load_map is not None:
                        map_started = time.perf_counter()
                        remaining = started + INIT_LIMIT_S - map_started
                        loaded = _watched(remaining, load_map) if remaining > 0 else None
                        map_elapsed = time.perf_counter() - map_started
                        if loaded is None:
                            log("Arena unavailable.")
                    ready_at = _send(stdout, b'{"type":"ready"}\n', time.perf_counter() + DECISION_LIMIT_S)
                    log(f"Ready: construction {constructed - started:.6f}s, load_map {map_elapsed:.6f}s")
                    try:
                        queued_at_wait = bool(select.select([stdin], [], [], 0)[0])
                    except (OSError, ValueError):
                        queued_at_wait = True
                elif kind == "obs":
                    if observations == 0 and ready_at is not None and received is not None and start_gap_ms is None:
                        start_gap_ms = (received - ready_at) * 1000
                        init_ms = (ready_at - hello_at) * 1000 if hello_at is not None else None
                        start_gap_waited = not queued_at_wait
                        log(f"Start: init {init_ms if init_ms is not None else -1:.1f}ms, gap {start_gap_ms:.1f}ms"
                            + ("" if start_gap_waited else " (queued)"))
                        latch = getattr(bot, "start_gap", None)
                        if latch is not None and latch(start_gap_ms, start_gap_waited):
                            early_ffa = True
                            ordered_decisions = False
                    if zone_schedule and bot is not None:
                        read_schedule = bot.read_zone_schedule(msg)
                        early_ffa = early_ffa or (bot.mode == "free-for-all" and (read_schedule or observations == 0))
                    if early_ffa:
                        
                        if raw_wire is not None:
                            raw_wire.stop()
                        if practice_router is not None:
                            practice_router.stop()
                        raw_wire = practice_router = None
                        practice_wire = False
                    if practice_router is not None and bot is not None:
                        practice_wire, raw_wire = practice_router.select(bot, msg)
                        if getattr(practice_router, "ordered_decisions", False):
                            ordered_decisions = True
                            pause_show = False
                            gaps = None
                        practice_router = None
                    queued = latest is not None
                    if not queued or early_ffa:
                        batch_start = received
                    observations += 1
                    latest = msg
                    default_observation = practice_wire and bot is None
                elif kind == "end":
                    if ordered_decisions:
                        break
                    return
        if latest is None:
            continue
        if raw is not None:
            frames += 1
        if (raw_wire is None and not ordered_decisions and not early_ffa and received is not None
                and frames < INPUT_FRAME_LIMIT and time.perf_counter() < batch_start + INPUT_DRAIN_S):
            continue
        obs = latest
        latest = None
        frames = 0
        deadline = batch_start + DECISION_LIMIT_S
        tick, valid_tick = _observation_tick(obs, last_tick + 2)
        if ordered_decisions and valid_tick:
            if last_ordered_tick is not None and tick <= last_ordered_tick:
                continue
            last_ordered_tick = tick
        input_queue = None
        if raw_wire is not None:
            input_queue = _QueuedInput(stdin, lines, last_tick + 2)
            if bot is not None:
                payload, deadline = raw_wire.decide(bot, obs, raw + b"\n", tick, batch_start,
                                                    frame_limit, pause_show, input_queue)
            else:
                payload = None
                for _ in input_queue.drain():
                    pass
            if input_queue.latest is not None:
                obs, tick, valid_tick, batch_start = input_queue.latest
                observations += input_queue.count
                queued = True
                if bot is None:
                    deadline = batch_start + DECISION_LIMIT_S
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
        if ordered_decisions and raw_wire is None:
            deadline = time.perf_counter() + ORDERED_DECISION_LIMIT_S + WRITE_RESERVE_S
            payload = None
            if bot is not None and not default_observation:
                try:
                    payload = _watch_ordered(ORDERED_DECISION_LIMIT_S, _decision, bot, obs, tick, pause_show)
                except DeadlineExceeded:
                    deadline_hits += 1
                    log(f"Decision safety deadline hit at tick {tick}")
                    if last_complete is not None:
                        payload = _encode({**json.loads(last_complete), "tick": tick})
                except Exception:
                    pass
                else:
                    if payload is not None and len(payload) <= frame_limit:
                        last_complete = payload
        elif raw_wire is None:
            remaining = deadline - WRITE_RESERVE_S - time.perf_counter()
            payload = (_watched(remaining, _decision, bot, obs, tick, pause_show)
                       if bot is not None and remaining > 0 and not default_observation else None)
        if payload is None or len(payload) > frame_limit:
            if default_observation:
                payload = _encode({"tick": tick})
            else:
                payload = _encode_action(_fallback(obs, tick), obs, pause_show)
        sent = _send(stdout, payload, deadline)
        last_sent = sent if valid_tick else None
        if input_queue is not None and input_queue.fd is None:
            return
    if ordered_decisions:
        log(f"Decision safety deadline hits: {deadline_hits}")


if __name__ == "__main__":
    log("mechfight.py is a library: import it from your bot and call run()")
