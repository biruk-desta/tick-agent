"""Bounded fire control derived from mechfight/1, without third-party code.

The target motion model is constant world velocity. Projectile velocity inheritance
is unspecified by the protocol, so it is deliberately not assumed.
"""
from __future__ import annotations

import math
import time
from body_stats import effective_mech_stats


def angle_delta(a, b):
    return (a - b + math.pi) % (2 * math.pi) - math.pi


def intercept(origin, target, velocity, speed, max_time=float("inf")):
    """Return (intercept_point, flight_seconds), or None if unreachable."""
    if speed <= 0:
        return None
    r = [target[i] - origin[i] for i in range(3)]
    a = sum(v * v for v in velocity) - speed * speed
    b = 2 * sum(r[i] * velocity[i] for i in range(3))
    c = sum(v * v for v in r)
    if c < 1e-12:
        return list(target), 0.0
    if abs(a) < 1e-10:
        times = [-c / b] if abs(b) > 1e-10 else []
    else:
        disc = b * b - 4 * a * c
        if disc < 0:
            return None
        # This form avoids cancellation for nearly parallel target motion.
        q = -0.5 * (b + math.copysign(math.sqrt(disc), b))
        times = [q / a]
        if abs(q) > 1e-12:
            times.append(c / q)
    valid = [t for t in times if 0 <= t <= max_time]
    if not valid:
        return None
    t = min(valid)
    return [target[i] + velocity[i] * t for i in range(3)], t


def _poly_roots(coeff, lower, upper):
    """Isolate real polynomial roots using derivative monotonic intervals.

    Degree is at most four. Critical-point subdivision also finds tangent roots
    that uniform time sampling misses near maximum ballistic range.
    """
    while len(coeff) > 1 and abs(coeff[0]) < 1e-12:
        coeff = coeff[1:]
    degree = len(coeff) - 1
    if degree <= 0:
        return []
    if degree == 1:
        t = -coeff[1] / coeff[0]
        return [t] if lower <= t <= upper else []

    def evaluate(t):
        v = 0.0
        for c in coeff:
            v = v * t + c
        return v

    critical = _poly_roots([c * (degree - i) for i, c in enumerate(coeff[:-1])], lower, upper)
    points = [lower] + critical + [upper]
    roots = []
    for t in points:
        scale = sum(abs(c) * abs(t) ** (degree - i) for i, c in enumerate(coeff))
        if abs(evaluate(t)) <= 1e-10 * max(1.0, scale):
            roots.append(t)
    for left, right in zip(points, points[1:]):
        fl, fr = evaluate(left), evaluate(right)
        if fl * fr >= 0:
            continue
        for _ in range(55):
            mid = (left + right) * 0.5
            fm = evaluate(mid)
            if fl * fm <= 0:
                right = mid
            else:
                left, fl = mid, fm
        roots.append((left + right) * 0.5)
    result = []
    for root in sorted(roots):
        if not result or root - result[-1] > 1e-6:
            result.append(root)
    return result


def ballistic_solutions(origin, target, velocity, speed, gravity, max_time=7.0,
                        min_pitch=-0.7, max_pitch=1.3):
    """Return valid (yaw, pitch, flight_seconds) roots in flight-time order."""
    if speed <= 0 or gravity < 0 or max_time <= 0:
        return []
    r = [target[i] - origin[i] for i in range(3)]
    coeff = [0.25 * gravity * gravity, gravity * velocity[2],
             sum(v * v for v in velocity) + gravity * r[2] - speed * speed,
             2 * sum(r[i] * velocity[i] for i in range(3)), sum(v * v for v in r)]
    result = []
    for t in _poly_roots(coeff, 1e-4, max_time):
        d = [r[i] + velocity[i] * t for i in range(3)]
        d[2] += 0.5 * gravity * t * t
        pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
        if min_pitch <= pitch <= max_pitch:
            result.append((math.atan2(d[1], d[0]), pitch, t))
    return result


def _angles(origin, target):
    dx, dy, dz = [target[i] - origin[i] for i in range(3)]
    return math.atan2(dy, dx), math.atan2(dz, math.hypot(dx, dy))


def turn_motion(pos, velocity, omega, horizon):
    """Exact deterministic planar CT transition, with a stable zero-rate limit."""
    theta=omega*horizon
    if abs(theta)<1e-4:
        sinc=1-theta*theta/6
        cosc=theta*.5-theta**3/24
    else:
        sinc=math.sin(theta)/theta
        cosc=(1-math.cos(theta))/theta
    vx,vy,vz=velocity
    point=[pos[0]+horizon*(vx*sinc-vy*cosc),pos[1]+horizon*(vx*cosc+vy*sinc),pos[2]+vz*horizon]
    c,s=math.cos(theta),math.sin(theta)
    return point,[vx*c-vy*s,vx*s+vy*c,vz]


class MotionBank:
    """CV/CT selection from authoritative world velocities and past residuals.

    This is a bounded deterministic adaptation, not a Kalman/particle posterior.
    Gaps, stops, speed changes and inconsistent turns invalidate the turn model.
    """
    def __init__(self):
        self.tracks={}

    def update(self, actors, now):
        for actor in actors:
            ident=actor['id'];pos=actor['pos'];vel=actor['vel']
            old=self.tracks.get(ident)
            rates=[];errors=[];rate=0.;trusted=False
            if old and 0<now-old['t']<=.35:
                dt=now-old['t'];previous=old['vel']
                speed=math.hypot(*vel[:2]);prior_speed=math.hypot(*previous[:2])
                if min(speed,prior_speed)>=3 and abs(speed-prior_speed)<=max(.6,.08*speed) and abs(vel[2])<1.5:
                    omega=math.atan2(previous[0]*vel[1]-previous[1]*vel[0],previous[0]*vel[0]+previous[1]*vel[1])/dt
                    if .06<=abs(omega)<=2.:
                        rates=(old['rates']+[omega])[-4:]
                        rate=sum(rates)/len(rates)
                        cv=[old['pos'][i]+previous[i]*dt for i in range(3)]
                        ct,_=turn_motion(old['pos'],previous,old['rate'],dt)
                        errors=(old['errors']+[(math.dist(cv[:2],pos[:2]),math.dist(ct[:2],pos[:2]))])[-3:]
                        cv_error=sum(e[0] for e in errors);ct_error=sum(e[1] for e in errors)
                        consistent=max(rates)-min(rates)<=max(.08,.25*abs(rate))
                        trusted=len(rates)>=3 and consistent and cv_error>.04 and ct_error<cv_error*.7
            elif old and now==old['t']:
                continue
            self.tracks[ident]={'t':now,'pos':list(pos),'vel':list(vel),'rates':rates,'rate':rate,'errors':errors,'trusted':trusted}
        if len(self.tracks)>32:
            self.tracks={k:v for k,v in self.tracks.items() if now-v['t']<2.}

    def rate(self, actor):
        state=self.tracks.get(actor['id'])
        return state['rate'] if state and state['trusted'] else 0.


def curved_intercept(origin, center, velocity, omega, speed, max_time):
    """Fixed point contracts when target speed is comfortably below shot speed."""
    if speed<=math.sqrt(sum(v*v for v in velocity))*1.2:
        return None
    flight=math.dist(origin,center)/speed
    for _ in range(8):
        point,_=turn_motion(center,velocity,omega,flight)
        updated=math.dist(origin,point)/speed
        if abs(updated-flight)<1e-6:
            flight=updated;break
        flight=updated
    if not 0<flight<=max_time:
        return None
    point,_=turn_motion(center,velocity,omega,flight)
    if abs(math.dist(origin,point)-speed*flight)>.03:
        return None
    return point,flight


def curved_ballistic(origin,center,velocity,omega,speed,gravity,max_time,min_pitch,max_pitch):
    """Bounded time bracketing for a trusted turning target; no tangent guarantee."""
    def residual(t):
        point,_=turn_motion(center,velocity,omega,t)
        r=[point[i]-origin[i] for i in range(3)];r[2]+=.5*gravity*t*t
        return sum(x*x for x in r)-speed*speed*t*t
    solutions=[];left=.01;fl=residual(left)
    for index in range(1,33):
        right=max_time*index/32;fr=residual(right)
        if left<right and fl*fr<0:
            lo,hi,flo=left,right,fl
            for _ in range(26):
                mid=(lo+hi)*.5;fm=residual(mid)
                if flo*fm<=0:hi=mid
                else:lo,flo=mid,fm
            flight=(lo+hi)*.5;point,_=turn_motion(center,velocity,omega,flight)
            displacement=[point[i]-origin[i] for i in range(3)];displacement[2]+=.5*gravity*flight*flight
            pitch=math.atan2(displacement[2],math.hypot(*displacement[:2]))
            if min_pitch<=pitch<=max_pitch:
                solutions.append((math.atan2(displacement[1],displacement[0]),pitch,flight))
            if len(solutions)>=2:break
        left,fl=right,fr
    return solutions


class Combat:
    def __init__(self, config, slot=0, prospective=False, motion_models=False):
        self.config = config
        self.slot = slot
        self.target = None
        self.field_mode = None
        self.engagement_ids = None
        self._prepared_obs = None
        self._charge_start = None
        self.contacts = {}
        self.watching = False
        self._focus_id = None
        self._attack_times = {}
        self._focus_at = -math.inf
        self._last_threat_at = -math.inf
        self._laser_target = None
        self._last_damage_by = None
        self._last_damage_t = -100.0
        self._plan_cache = {}
        self._blocked_until = {}
        self._deadline = None
        self.prospective = prospective
        self.command_delay = config['match']['decide_every'] / config['match']['tick_hz'] * .5
        self.motion = MotionBank() if motion_models else None

    def _expired(self):
        return self._deadline is not None and time.perf_counter() >= self._deadline

    def _slewed(self, me, command, delay):
        stats=self._mech_stats(me)
        turn_mult=1.
        for weapon in me['weapons']:
            if weapon and weapon['kind']=='laser' and weapon.get('charge',0)>0:
                turn_mult=self._weapon_stats(weapon).get('charge_turn_mult',1.)
        yaw_step=stats['turn_rate']*turn_mult*delay
        pitch_step=stats['pitch_rate']*turn_mult*delay
        yaw=me['aim'][0]+max(-yaw_step,min(yaw_step,angle_delta(command[0],me['aim'][0])))
        pitch=me['aim'][1]+max(-pitch_step,min(pitch_step,command[1]-me['aim'][1]))
        return [yaw,max(stats['min_pitch'],min(stats['max_pitch'],pitch))]

    def _future_origin(self, me, kind, arena, delay):
        origin=self._origin(me,kind,arena)
        return [origin[i]+me['vel'][i]*delay for i in range(3)]

    def _mech_stats(self, me):
        return effective_mech_stats(self.config, me)

    def _weapon_stats(self, weapon):
        return {**self.config.get("weapons", {}).get(weapon["kind"], {}),
                **weapon.get("stats", {})}

    def _shape(self, target):
        kind = target.get("kind", "crate")
        if kind == "mech":
            scale = 1 + self.config.get("cubes", {}).get("size_per_cube", 0.05) * target.get("cubes", 0)
            base = self.config.get("mech", {})
            return base.get("radius", 2.5) * scale, base.get("height", 9.0) * scale
        base = self.config.get("npc" if kind == "npc" else "crates", {})
        return base.get("radius", 1.8 if kind == "npc" else 1.4), base.get("height", 3.5 if kind == "npc" else 2.4)

    def _center(self, target):
        _, height = self._shape(target)
        return [target["pos"][0], target["pos"][1], target["pos"][2] + height * target.get("_aim_fraction", .5)]

    def _origin(self, me, kind="gun", arena=None):
        stats = self._mech_stats(me)
        # Protocol §5: mortar uses height+0.5, other weapons muzzle_height;
        # all origins extend radius+0.5 along actual torso aim, capped by walls.
        height = stats.get("height", 9.0) + 0.5 if kind == "mortar" else stats.get("muzzle_height", 7.0)
        base = [me["pos"][0], me["pos"][1], me["pos"][2] + height]
        yaw, pitch = me.get("aim", [0.0, 0.0])
        reach = stats.get("radius", 2.5) + 0.5
        direction = [math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)]
        tip = [base[i] + direction[i] * reach for i in range(3)]
        if arena is not None and not self._clear(arena, base, tip):
            low, high = 0.0, reach
            for _ in range(10):
                mid = (low + high) * 0.5
                point = [base[i] + direction[i] * mid for i in range(3)]
                if self._clear(arena, base, point):
                    low = mid
                else:
                    high = mid
            tip = [base[i] + direction[i] * max(0.0, low - 0.02) for i in range(3)]
        return tip

    @staticmethod
    def _clear(arena, a, b):
        # A missing map cannot establish safe blind fire through remembered cover.
        return arena is not None and getattr(arena, "available", True) and arena.line_clear(a, b)

    def _all_targets(self, obs):
        return list(obs.get("mechs", [])) + [dict(c, kind="crate", vel=[0.0, 0.0, 0.0]) for c in obs.get("crates", [])]

    def select_target(self, obs, arena, allow_combat=True, defensive=False, mechs_only=False):
        if not allow_combat:
            return None
        me = obs["self"]
        origin = self._origin(me, arena=arena)
        enemies = [m for m in obs.get("mechs", []) if m.get("kind") == "mech"]
        nearest_enemy = min((math.dist(me["pos"], m["pos"]) for m in enemies), default=float("inf"))
        hp_ratio = me.get("hp", 0) / max(1.0, me.get("max_hp", 1))
        ranked = []
        held = [w for w in me.get("weapons", []) if w]
        if defensive:
            held = [w for w in held if w['kind'] in ('gun','lightning') and w.get('cooldown',0)<=.10
                    and (w['kind']!='gun' or (w.get('ammo',0)>0 and not w.get('reload',0)))
                    and (w['kind']!='lightning' or me.get('energy',0)>=self._weapon_stats(w).get('energy',3)+12)]
        def effective_range(w):
            stats=self._weapon_stats(w)
            reach=stats.get('range',stats.get('speed',0)*stats.get('ttl',0))
            return min(reach,stats['speed']*.35) if defensive and w['kind']=='gun' else reach
        max_range = max((effective_range(w) for w in held), default=0)
        mortar = next((w for w in held if w["kind"] == "mortar" and w.get("cooldown", 0) <= 0.1), None)
        for target in enemies if mechs_only else self._all_targets(obs):
            if (target.get('kind')=='mech' and self.engagement_ids is not None
                    and target['id'] not in self.engagement_ids):
                continue
            if target.get("hp", 1) <= 0:
                continue
            center = self._center(target)
            distance = math.dist(origin, center)
            if self.field_mode and target['kind']=='mech' and not defensive:
                limit = 240 if self.field_mode=='squad' else 215
                if math.dist(me['pos'][:2],target['pos'][:2])>limit:
                    continue
            elif distance > max_range:
                continue
            kind = target["kind"]
            if defensive and kind != 'mech':
                continue
            if kind == "mech":
                if self.field_mode:
                    dx = target['pos'][0]-me['pos'][0]
                    dy = target['pos'][1]-me['pos'][1]
                    horizontal = math.hypot(dx,dy)
                    squad = self.field_mode=='squad'
                    score = -horizontal - target['hp']*(.21 if squad else 60./1400.)
                    if squad and target['hp']<=.30*target['max_hp']:
                        score += 200
                    if squad and target['id']==self._focus_id and obs['t']-self._focus_at<2:
                        score += 200
                    if obs['t']-self._attack_times.get(target['id'],-math.inf)<4:
                        score += 40
                    relative = [target['vel'][i]-me['vel'][i] for i in (0,1)]
                    if horizontal>1 and -(relative[0]*dx+relative[1]*dy)/horizontal>3:
                        score += 15
                else:
                    score = 200 - distance * 0.45
                    score += 65 * (1 - min(1.0, target.get("hp", 1400) / max(1, target.get("max_hp", 1400))))
                    if target.get("charging"):
                        score += 20
                    if target["id"] == self._last_damage_by and obs.get("t", 0) - self._last_damage_t < 3:
                        score += 35
            else:
                # Farm near the route only while healthy and without a nearby
                # hostile. Navigation policy may explicitly prefer a safe crate.
                if hp_ratio < 0.65 or nearest_enemy < 80 or distance > 95:
                    continue
                score = (130 if kind == "crate" else 95) - distance
            if not self.field_mode and self.target is not None and self.target.get("id") == target["id"]:
                score += 12
            if not self.field_mode and target["id"] == self._laser_target:
                score += 100
            ranked.append((score, target))
        ranked.sort(key=lambda item: (bool(self.field_mode and item[1]['kind']=='mech'),item[0]), reverse=True)
        now = obs.get("t", 0)
        checks, blind_checks, upper_checks = 0, 0, 0
        for _, target in ranked:
            if self._expired():
                break
            if self._blocked_until.get(target["id"], -1) > now:
                continue
            checks += 1
            if self._clear(arena, origin, self._center(target)):
                return target
            if self.field_mode and target['kind']=='mech' and upper_checks < 2 and not self._expired():
                upper_checks += 1
                upper = dict(target, _aim_fraction=.85)
                if self._clear(arena, origin, self._center(upper)):
                    return upper
            # Spend at most one blind ballistic attempt and six direct rays.
            if mortar and target["kind"] == "mech" and blind_checks < 1:
                blind_checks += 1
                if self._plan(obs, target, mortar, arena) is not None:
                    return target
            self._blocked_until[target["id"]] = now + .3
            if checks >= 6:
                break
        if len(self._blocked_until) > 64:
            self._blocked_until = {k:v for k,v in self._blocked_until.items() if v > now}
        return None

    def _aligned(self, actual, desired, target, origin, multiplier=0.80):
        radius, height = self._shape(target)
        distance = max(1.0, math.dist(origin[:2], target["pos"][:2]))
        yaw_tol = max(0.002, math.atan2(radius * multiplier, distance))
        fraction = target.get('_aim_fraction', .5)
        pitch_tol = max(.002, math.atan2(height*min(.40, .8*min(fraction,1-fraction)), distance))
        return abs(angle_delta(actual[0], desired[0])) <= yaw_tol and abs(actual[1] - desired[1]) <= pitch_tol

    def _arc_clear(self, arena, origin, solution, speed, gravity):
        yaw, pitch, flight = solution
        direction = [math.cos(yaw) * math.cos(pitch), math.sin(yaw) * math.cos(pitch), math.sin(pitch)]
        previous = origin
        steps = max(2, math.ceil(flight / 0.08))
        for i in range(1, steps + 1):
            if i % 8 == 1 and self._expired():
                return False
            t = flight * i / steps
            point = [origin[j] + direction[j] * speed * t for j in range(3)]
            point[2] -= 0.5 * gravity * t * t
            if not self._clear(arena, previous, point):
                return False
            previous = point
        return True

    def _plan(self, obs, target, weapon, arena, delay=0.):
        if self._expired():
            return None
        key = (id(arena), target['id'], tuple(target['pos']), tuple(target.get('vel', (0,0,0))),
               target.get('cubes',0), target.get('_aim_fraction',.5), weapon['kind'], tuple(sorted(weapon.get('stats',{}).items())),
               tuple(obs['self']['pos']), tuple(obs['self']['aim']),tuple(obs['self']['vel']),delay)
        if key not in self._plan_cache:
            self._plan_cache[key] = self._compute_plan(obs, target, weapon, arena, delay)
        return self._plan_cache[key]

    def _compute_plan(self, obs, target, weapon, arena, delay=0.):
        origin = self._future_origin(obs["self"], weapon["kind"], arena,delay)
        center = self._center(target)
        velocity = target.get("vel", [0.0, 0.0, 0.0])
        omega=self.motion.rate(target) if self.motion else 0.
        center,velocity=turn_motion(center,velocity,omega,delay)
        stats = self._weapon_stats(weapon)
        kind = weapon["kind"]
        distance = math.dist(origin, center)
        if kind == "gun":
            speed = stats.get("speed", 252)
            lifetime=stats.get("range",230)/max(1e-9,speed)
            solution = curved_intercept(origin,center,velocity,omega,speed,lifetime) if omega else intercept(origin,center,velocity,speed,lifetime)
            if solution is None or not self._clear(arena, origin, solution[0]):
                return None
            yaw, pitch = _angles(origin, solution[0])
            return yaw, pitch, solution[1]
        if kind in ("laser", "lightning"):
            if distance > stats.get("range", 280 if kind == "laser" else 45) or not self._clear(arena, origin, center):
                return None
            return (*_angles(origin, center), 0.0)
        if kind == "mortar":
            splash = stats.get("splash_radius", 7)
            own_radius = self._mech_stats(obs["self"]).get("radius", 2.5)
            if distance < splash + own_radius + 7:
                return None
            mech_stats = self._mech_stats(obs["self"])
            speed, gravity = stats.get("speed", 72), stats.get("gravity", 22)
            solver=curved_ballistic if omega else ballistic_solutions
            args=(origin,center,velocity,omega,speed,gravity) if omega else (origin,center,velocity,speed,gravity)
            solutions = solver(*args, stats.get("ttl", 7),mech_stats.get("min_pitch", -0.7), mech_stats.get("max_pitch", 1.3))
            for solution in solutions:
                landing,_=turn_motion(center,velocity,omega,solution[2])
                if math.dist(origin[:2], landing[:2]) < splash + own_radius + 7:
                    continue
                if self._arc_clear(arena, origin, solution, speed, gravity):
                    return solution
        return None

    def _lightning_recipient_clear(self, obs, target, arena, origin, cone):
        """Whether the selected object is not displaced by a nearer arc recipient."""
        selected_distance = math.dist(origin, self._center(target))
        for other in self._all_targets(obs):
            if self._expired():
                return False
            if other['id'] == target['id']:
                continue
            center = self._center(other)
            if math.dist(origin, center) < selected_distance:
                yaw = _angles(origin, center)[0]
                if (abs(angle_delta(obs['self']['aim'][0], yaw)) <= cone
                        and self._clear(arena, origin, center)):
                    return False
        return True

    def _watch_contact(self, obs, arena, result, weapons):
        """Use missing contacts only to turn; only a currently listed foe can start a hidden charge."""
        me, now = obs['self'], obs['t']
        listed = [m for m in obs['mechs'] if m['kind']=='mech' and m['hp']>0
                  and (self.engagement_ids is None or m['id'] in self.engagement_ids)]
        previous = self.contacts.get(self._focus_id)
        current = None
        if listed:
            current = min(listed,key=lambda m: math.dist(m['pos'][:2],me['pos'][:2]))
        if current is None:
            if not previous or not 0<=now-previous[1]<=2.5:
                return
            actor = previous[0]
            if actor.get('hp',0)<=0:
                return
        else:
            actor = current
        if self._expired():
            return
        origin = self._origin(me,arena=arena)
        center = self._center(actor)
        result['aim'] = list(_angles(origin,center))
        self.watching = True
        if current is None or self.field_mode=='squad':
            return
        distance = math.dist(me['pos'],actor['pos'])
        engaged = (self.engagement_ids is not None or distance<=60
                   or (actor['id']==self._focus_id and now-self._focus_at<=2)
                   or (actor['id']==self._last_damage_by and now-self._last_damage_t<4))
        if not engaged:
            return
        self._last_threat_at = now
        for slot, weapon in enumerate(weapons):
            if not weapon or weapon['kind']!='laser' or weapon.get('cooldown',0)>0:
                continue
            ws = self._weapon_stats(weapon)
            charge = weapon.get('charge',0)
            # Leave enough time to turn upward and discharge before the engine's automatic release.
            turn = self._mech_stats(me)
            escape_time = max(0.,turn['max_pitch']-me['aim'][1])/max(.01,turn['pitch_rate']*ws.get('charge_turn_mult',1.))
            held = max(charge, now-self._charge_start) if self._charge_start is not None else charge
            if distance<=ws['range'] and held+escape_time+.3<ws['charge']+ws['hold_s']:
                # Previously blocked targets may have their selection rays cached for a few ticks.
                if (not self._clear(arena,origin,center) and not self._expired()
                        and not self._clear(arena,origin,self._center(dict(actor,_aim_fraction=.85)))):
                    result['fire'][slot] = True
                    self._laser_target = actor['id']
            return

    def _prepare_observation(self, obs, deadline):
        self._deadline = deadline
        if self.field_mode and self._prepared_obs is obs:
            return
        self._prepared_obs = obs if self.field_mode else None
        self._plan_cache = {}
        if self.motion:
            self.motion.update(obs.get('mechs',[]),obs['t'])
        for event in obs.get('events',[]):
            if event.get('type')=='damaged' and event.get('by') is not None:
                self._last_damage_by, self._last_damage_t = event['by'], obs.get('t',0)
                if self.field_mode:
                    self._attack_times[event['by']] = obs.get('t',0)
        if len(self._attack_times)>32:
            self._attack_times = {k:t for k,t in self._attack_times.items() if obs['t']-t<4}

    def preview_target(self, obs, arena, deadline=None):
        self._prepare_observation(obs, deadline)
        return self.select_target(obs, arena, mechs_only=True)

    def choose(self, obs, arena, allow_combat=True, preferred_target=None, deadline=None, defensive=False,
               target_assigned=False):
        self._prepare_observation(obs,deadline)
        self.watching = False
        me = obs["self"]
        actual = me.get("aim", [0.0, 0.0])
        result = {"aim": list(actual), "fire": [False, False], "reload": False}
        weapons = me.get("weapons", [None, None])
        arc_reserve = 0 if self.field_mode and not defensive else 12
        charging_slots = [i for i, w in enumerate(weapons) if w and w["kind"] == "laser" and w.get("charge", 0) > 0]
        if self.field_mode:
            if charging_slots and self._charge_start is None:
                self._charge_start = obs['t']-weapons[charging_slots[0]]['charge']
            elif not charging_slots:
                self._charge_start = None
        if defensive and charging_slots:
            allow_combat = False
        if self._expired():
            for i in charging_slots:
                result['fire'][i] = True
            return result
        preferred = preferred_target
        if preferred is not None and not isinstance(preferred, dict):
            preferred = next((t for t in self._all_targets(obs) if t["id"] == preferred), None)
        if (preferred is not None and preferred.get('kind')=='mech' and self.engagement_ids is not None
                and (preferred['id'] not in self.engagement_ids or not any(
                    m['id']==preferred['id'] and m['kind']=='mech' for m in obs['mechs']))):
            preferred = None
        target = preferred if allow_combat else None
        if target is None and not target_assigned:
            target = self.select_target(obs, arena, allow_combat, defensive=defensive)
        if defensive and target is not None and target.get('kind') != 'mech':
            target = None
        if target is not None and "kind" not in target:
            target = dict(target, kind="crate", vel=[0.0, 0.0, 0.0])
        self.target = target
        if self.field_mode and target is not None and target.get('kind')=='mech':
            self._focus_id, self._focus_at = target['id'], obs['t']
            self._last_threat_at = obs['t']
        if target is None:
            if self.field_mode and allow_combat and not defensive:
                self._watch_contact(obs, arena, result, weapons)
            precharging = self.watching and any(result['fire'])
            # A charged laser cannot be cancelled. Aim harmlessly skyward before
            # release, and never start another charge while healing/escaping.
            if charging_slots and not precharging:
                self.watching = False
                high = self._mech_stats(me).get("max_pitch", 1.3)
                result["aim"] = [actual[0], high]
                for i in charging_slots:
                    result["fire"][i] = actual[1] < high - 0.08
            for weapon in weapons:
                if weapon and weapon["kind"] == "gun" and not weapon.get("reload", 0):
                    ammo = weapon.get('ammo',0)
                    mag = self._weapon_stats(weapon).get('mag',12)
                    quiet = obs.get('t',0)-max(self._last_threat_at,self._last_damage_t)>3
                    result['reload'] = ammo<mag and (not self.field_mode or quiet or ammo<=mag*.6)
            if not precharging:
                self._laser_target = None
            return result

        origin = self._origin(me, arena=arena)
        def plan_for(weapon, delay=0.):
            if (not weapon or (defensive and weapon['kind'] not in ('gun','lightning'))
                    or (self.field_mode and target['kind']!='mech' and weapon['kind'] in ('laser','mortar'))):
                return None
            plan = self._plan(obs,target,weapon,arena,delay)
            # A recent hit already reset regeneration. Bound any additional
            # planned delay: no new charge/shell, and <=.35s solved gun flight.
            # A missed bullet can still hit something later in its live range.
            return None if defensive and plan and plan[2] > .35 else plan
        plans = [plan_for(w) for w in weapons]
        command_plans = [plan_for(w,self.command_delay) for w in weapons] if self.prospective else plans
        if any(plans[i] is None for i in charging_slots):
            high = self._mech_stats(me).get("max_pitch", 1.3)
            result["aim"] = [actual[0], high]
            for i in charging_slots:
                result["fire"][i] = actual[1] < high - 0.08
            return result
        # Reuse the actual-world recipient check for ownership and firing; an
        # unusable secondary must not divert the shared aim from a ready gun.
        lightning_recipients = {}
        def lightning_recipient_ready(slot):
            if slot not in lightning_recipients:
                stats = self._weapon_stats(weapons[slot])
                cone = math.radians(stats.get('cone_deg', 30)) * .5
                lightning_recipients[slot] = self._lightning_recipient_clear(obs,target,arena,origin,cone)
            return lightning_recipients[slot]
        # Charging laser owns the aim; otherwise ready secondary, then gun.
        owner = next((i for i in charging_slots if plans[i]), None)
        if owner is None:
            priority = {"laser": 4, "lightning": 3, "mortar": 2, "gun": 1}
            candidates = [i for i, w in enumerate(weapons) if w and plans[i] and w.get("cooldown", 0) <= 0.10
                          and (w['kind']!='lightning' or (me.get('energy',0)>=self._weapon_stats(w).get('energy',3)+arc_reserve
                               and lightning_recipient_ready(i)))]
            owner = max(candidates, key=lambda i: priority.get(weapons[i]["kind"], 0), default=None)
        if owner is None:
            owner = next((i for i, plan in enumerate(plans) if plan), None)
        if owner is None:
            result["aim"] = list(_angles(origin, self._center(target)))
            return result
        # Precise gun leading can also serve a lightning cone. Keep both shots
        # available instead of steering the gun away from its intercept.
        if weapons[owner]['kind'] == 'lightning':
            cone = math.radians(self._weapon_stats(weapons[owner]).get('cone_deg',30)) * .5
            limits = self._mech_stats(me)
            for slot, weapon in enumerate(weapons):
                if (not weapon or weapon['kind']!='gun' or weapon.get('cooldown',0)>.10
                        or weapon.get('reload',0)
                        or weapon.get('ammo',self._weapon_stats(weapon).get('mag',12))<=0
                        or plans[slot] is None or command_plans[slot] is None):
                    continue
                gun_command = (command_plans[slot] if self.prospective else plans[slot])[:2]
                if (limits.get('min_pitch',-.7)<=gun_command[1]<=limits.get('max_pitch',1.3)
                        and abs(angle_delta(gun_command[0],plans[owner][0]))<=cone):
                    owner = slot
                    break
        shared_laser_slot = None
        if self.field_mode and weapons[owner]['kind']=='laser':
            beam = weapons[owner]
            laser_stats = self._weapon_stats(beam)
            # Lead a ready gun early enough to turn back before a full beam is ready.
            if (beam.get('charge',0) < laser_stats['charge']*.4 and target['hp']>laser_stats['damage']
                    and angle_delta(plans[owner][0],actual[0])**2 < .12**2):
                for slot, w in enumerate(weapons):
                    if (w and w['kind']=='gun' and not w.get('reload') and w.get('ammo',0)>0
                            and w.get('cooldown',0)<=.10 and plans[slot] and command_plans[slot]
                            and abs(angle_delta(command_plans[slot][0],plans[owner][0]))<.20
                            and abs(command_plans[slot][1]-plans[owner][1])<.15):
                        # Charge acquisition is independent of the shared barrel's
                        # projectile lead. The release tick retains laser ownership.
                        shared_laser_slot = owner
                        owner = slot
                        break
        desired = (command_plans[owner] or plans[owner])[:2]
        stats_me = self._mech_stats(me)
        if not stats_me.get("min_pitch", -0.7) <= desired[1] <= stats_me.get("max_pitch", 1.3):
            return result
        result["aim"] = list(desired)
        for i, weapon in enumerate(weapons):
            if not weapon:
                continue
            kind, plan = weapon["kind"], plans[i]
            stats = self._weapon_stats(weapon)
            if kind == "gun":
                ammo = weapon.get("ammo", stats.get("mag", 12))
                reserve_reload = (not self.field_mode or target['kind']!='mech') and ammo<=3 and math.dist(me['pos'],target['pos'])>70
                result['reload'] = not weapon.get('reload',0) and (ammo<=0 or reserve_reload)
                if result["reload"] or weapon.get("reload", 0) or ammo <= 0:
                    continue
            if kind == "laser":
                charge = weapon.get("charge", 0)
                if charge > 0:
                    if not plan:
                        # No safe target/LOS: turn skyward while holding; next
                        # observation will release once this direction is safe.
                        high = stats_me.get("max_pitch", 1.3)
                        result["aim"] = [actual[0], high]
                        result["fire"][i] = actual[1] < high - 0.08
                    else:
                        laser_origin = self._origin(me, "laser", arena)
                        aligned = self._aligned(actual, plan, target, laser_origin)
                        if aligned:
                            distance = math.dist(laser_origin, self._center(target))
                            direction = [math.cos(actual[0]) * math.cos(actual[1]), math.sin(actual[0]) * math.cos(actual[1]), math.sin(actual[1])]
                            endpoint = [laser_origin[j] + distance * direction[j] for j in range(3)]
                            aligned = self._clear(arena, laser_origin, endpoint)
                        if aligned and self.prospective:
                            future_plan=command_plans[i]
                            future_origin=self._future_origin(me,'laser',arena,self.command_delay)
                            future_aim=self._slewed(me,desired,self.command_delay)
                            aligned=future_plan is not None and self._aligned(future_aim,future_plan,target,future_origin)
                            if aligned:
                                center=self._center(target)
                                rate=self.motion.rate(target) if self.motion else 0.
                                center,_=turn_motion(center,target.get('vel',[0,0,0]),rate,self.command_delay)
                                distance=math.dist(future_origin,center)
                                direction=[math.cos(future_aim[0])*math.cos(future_aim[1]),math.sin(future_aim[0])*math.cos(future_aim[1]),math.sin(future_aim[1])]
                                endpoint=[future_origin[j]+distance*direction[j] for j in range(3)]
                                aligned=self._clear(arena,future_origin,endpoint)
                        full = charge >= stats.get("charge", 0.75) - 1e-6
                        minimum = charge >= stats.get("min_charge", 0.15)
                        cube_mult = 1 + self.config.get("cubes", {}).get("damage_per_cube", 0.04) * min(me.get("cubes", 0), self.config.get("cubes", {}).get("stat_cap", 10))
                        fraction = stats.get("min_frac", 0.35) + (1 - stats.get("min_frac", 0.35)) * min(1, charge / max(1e-6, stats.get("charge", 0.75)))
                        cookoff = 1.
                        if self.field_mode and 'mortar' in target.get('weapons',[]):
                            cookoff += stats.get('cookoff',.6)
                        threshold = .70 if self.field_mode=='squad' else .85
                        lethal = (self.field_mode in (None,'squad') and target.get('hp',math.inf)
                                  <= stats.get('damage',315)*fraction*cube_mult*cookoff*threshold)
                        result["fire"][i] = not (aligned and (full or (minimum and lethal)))
                elif plan and weapon.get("cooldown", 0) <= 0 and i in (owner, shared_laser_slot):
                    # Do not halve movement just to rotate at a distant target.
                    close_aim = abs(angle_delta(actual[0], plan[0])) < 0.35 and abs(actual[1] - plan[1]) < 0.25
                    if self.field_mode and target['kind']=='mech':
                        turn = self._mech_stats(me)
                        acquire = max(abs(angle_delta(actual[0],plan[0]))/max(.01,turn['turn_rate']),
                                      abs(actual[1]-plan[1])/max(.01,turn['pitch_rate']))
                        close_aim |= acquire <= stats['charge']*.6*stats.get('charge_turn_mult',1.)
                    result["fire"][i] = close_aim
                    if close_aim:
                        self._laser_target = target["id"]
                continue
            if plan is None or weapon.get("cooldown", 0) > 0.10:
                continue
            weapon_origin = self._origin(me, kind, arena)
            fire_plan=plan
            fire_aim=actual
            fire_origin=weapon_origin
            if self.prospective and kind in ('gun','mortar'):
                fire_plan=command_plans[i]
                if fire_plan is None:
                    continue
                # Compare plans at one shared future time. The gate follows a
                # rate-limited torso, never a widened angular tolerance.
                fire_aim=self._slewed(me,desired,self.command_delay)
                fire_origin=self._future_origin(me,kind,arena,self.command_delay)
            compatible = self._aligned(desired, fire_plan, target, fire_origin)
            aligned = self._aligned(fire_aim, fire_plan, target, fire_origin)
            if kind == "lightning":
                # Use half the configured angle conservatively: the protocol
                # wording does not settle full-width versus half-angle naming.
                cone = math.radians(stats.get("cone_deg", 30)) * 0.5
                aligned = abs(angle_delta(actual[0], plan[0])) <= cone
                compatible = abs(angle_delta(desired[0], plan[0])) <= cone
                if me.get("energy", 0) < stats.get("energy", 3) + arc_reserve:
                    continue
                # A closer crate or drone may carry the arc through to the
                # intended mech. The field policy takes the in-cone shot while
                # leaving aim ownership with the gun when it needs a lead.
                if not self.field_mode and not lightning_recipient_ready(i):
                    continue
            elif aligned and compatible:
                # Check the trajectory that actually leaves the barrel, rather
                # than only the ideal intercept that lies near this direction.
                if kind == "mortar":
                    aligned = self._arc_clear(arena, fire_origin, (fire_aim[0], fire_aim[1], fire_plan[2]),
                                              stats.get("speed", 72), stats.get("gravity", 22))
                    if aligned and self.prospective:
                        aligned=self._arc_clear(arena,weapon_origin,(actual[0],actual[1],plan[2]),stats.get('speed',72),stats.get('gravity',22))
                else:
                    distance = stats.get("speed", 252) * fire_plan[2]
                    direction = [math.cos(fire_aim[0]) * math.cos(fire_aim[1]), math.sin(fire_aim[0]) * math.cos(fire_aim[1]), math.sin(fire_aim[1])]
                    endpoint = [fire_origin[j] + distance * direction[j] for j in range(3)]
                    aligned = self._clear(arena, fire_origin, endpoint)
                    # At a parapet, this tick's command can raise the barrel to
                    # the exposed upper body before the projectile is emitted.
                    upper_body_shot = self.field_mode and target.get('_aim_fraction', .5) > .5
                    if aligned and self.prospective and not upper_body_shot:
                        direction=[math.cos(actual[0])*math.cos(actual[1]),math.sin(actual[0])*math.cos(actual[1]),math.sin(actual[1])]
                        endpoint=[weapon_origin[j]+stats.get('speed',252)*plan[2]*direction[j] for j in range(3)]
                        aligned=self._clear(arena,weapon_origin,endpoint)
            result["fire"][i] = bool(aligned and compatible)
        if not charging_slots and not any(w and w["kind"] == "laser" and result["fire"][i] for i, w in enumerate(weapons)):
            self._laser_target = None
        return result
