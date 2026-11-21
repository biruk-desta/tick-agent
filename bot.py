"""Team Kanyaraasi's mechfight/1 scoring entrypoint; standard library only."""
from __future__ import annotations

import math
import os
import time

import mechfight as mf
from arena_model import Arena
from body_stats import effective_mech_stats
from combat import Combat
from match_policy import FlatArena, MatchState, choose_upgrade
from firstparty_movement import AdaptiveMovement
from navigation import Navigator, LocalController, circle_at, outside_distance, unit


class Bot:
    name = 'kanyaraasi-v1'

    def __init__(self, hello):
        self.config = hello['config']
        self.slot = hello['slot']
        self.match_policy = os.environ.get('KANYARAASI_MATCH_POLICY', 'baseline')
        self.arena = Arena(hello['map']['dir'])
        if not self.arena.available:
            mf.log('Map unavailable:', getattr(self.arena, 'error', 'unknown'))
            if self.match_policy == 'adaptive':
                self.arena = FlatArena(self.config['zone'])
        self.navigator = Navigator(self.arena)
        self.controller = LocalController(self.arena, self.config, self.slot, energy_hysteresis=os.environ.get('KANYARAASI_ENERGY_MODE','hysteresis')!='threshold',contact_repair=os.environ.get('KANYARAASI_CONTACT_REPAIR','off')=='on')
        self.combat = Combat(self.config, self.slot, prospective=os.environ.get('KANYARAASI_AIM_MODE','prospective')!='snapshot',motion_models=os.environ.get('KANYARAASI_MOTION_MODEL','cv')!='cv')
        self.recovery_trigger = .30 if os.environ.get('KANYARAASI_RECOVERY_MODE','standard')=='aggressive' else .58
        self.recovery_defense = os.environ.get('KANYARAASI_RECOVERY_DEFENSE','off') == 'recent_hit'
        self.last_weapon_damage = -100.0
        self.incoming_bearing = None
        self.incoming_bearing_at = -100.
        self.last_weapon_attackers = ()
        self.last_damage_observation_tick = -1
        self.recovering = False
        self.last_damage = -100.0
        self.last_combat = -100.0
        self.memory = {}
        self.goal_id = None
        self.last_goal = None
        self.mode = 'zone'
        self.scan_sweep = os.environ.get('KANYARAASI_SCAN_MODE','route') == 'sweep'
        self.healing_drops = os.environ.get('KANYARAASI_HEALING_DROPS','off') == 'on'
        self.region_goals = os.environ.get('KANYARAASI_REGION_GOALS','off') == 'on'
        self.loadout_engagement = os.environ.get('KANYARAASI_ENGAGEMENT_MODE','off') == 'loadout'
        self.ablation = os.environ.get('KANYARAASI_ABLATION', '')
        self.last_zone = None
        self.cover_choice = None
        self.cover_epoch = -1
        self.cover_cost = float('inf')
        self.controller.repair_when_stalled = self.match_policy in ('weapon', 'covered', 'farm', 'adaptive')
        self.pickup_plan = None
        self.match_state = MatchState()
        self.field_movement = AdaptiveMovement()
        self.field_mode = 'opening'
        self.contacts = {}
        self.seek_laser = os.environ.get('KANYARAASI_LASER_ROUTE') == 'on'
        self.plan_checked = -100.
        self.plan_context = None
        self.rejected_pickups = set()
        self.noise = []
        speed_add,speed_mul=0.,1.
        for upgrade in self.config.get('upgrades',[]):
            for effect in upgrade.get('effects',[]):
                if effect['path']=='mech.boost_speed':
                    speed_add+=max(0.,effect.get('add',0))*upgrade['max']
                    speed_mul*=max(1.,effect.get('mul',1))**upgrade['max']
        self.enemy_speed_bound=(self.config['mech']['boost_speed']+speed_add)*speed_mul

    def _stats(self, me):
        return effective_mech_stats(self.config, me)

    def _remember(self, obs):
        me, now = obs['self'], obs['t']
        self.noise = [region for region in self.noise if region[0] > now]
        for sound in obs.get('sounds', []):
            kind = sound['kind']
            if kind not in ('gun','mortar','laser','laser_charge','lightning','explosion'):
                continue
            expires = now - sound['age'] + 2.0
            if expires <= now:
                continue
            rules = self.config['sound']
            near, mid = rules['near'], rules['mid']
            low, high = {'near':(0.,near),'mid':(near,mid),'far':(mid,rules['range'].get(kind,mid))}[sound['dist']]
            sigma = max(.02, math.radians(rules['bearing_noise_deg']) * me['stats'].get('hearing',1))
            # Anonymous noisy bearing/range regions; never invent an actor ID.
            self.noise.append((expires,me['pos'][0],me['pos'][1],sound['bearing'],low,high,sigma))
        self.noise = self.noise[-12:]
        for kind in ('cubes', 'pickups', 'crates'):
            for item in obs[kind]:
                self.memory[item['id']] = (kind, item, now)
        present = {item['id'] for kind in ('cubes', 'pickups', 'crates') for item in obs[kind]}
        for ident, (kind, item, seen) in list(self.memory.items()):
            nearby = math.dist(item['pos'][:2], me['pos'][:2]) < 8 and abs(item['pos'][2]-me['pos'][2]) < 4
            if self.match_policy=='adaptive':
                nearby = False
                if ident not in present and now-seen > .35 and math.dist(me['pos'][:2],item['pos'][:2]) < 40:
                    eye = (*me['pos'][:2],me['pos'][2]+me['stats']['eye_height'])
                    point = (*item['pos'][:2],item['pos'][2]+1.5)
                    nearby = self.arena.line_clear(eye,point)
            expired = self.match_policy != 'adaptive' and now-seen > (12 if kind=='cubes' else 60)
            if expired or (ident not in present and nearby):
                del self.memory[ident]
        fresh_damage = obs['tick'] > self.last_damage_observation_tick
        visible_hostiles = {e['id'] for e in obs['mechs'] if e['kind']=='mech' and e['id']!=me['id']}
        fresh_hitters = set()
        for event in obs['events']:
            if event['type'] == 'damaged':
                self.last_damage = now
                self.last_combat = now
                bearing = event.get('bearing')
                if (fresh_damage and bearing is not None and
                        event.get('weapon') in ('gun', 'laser', 'lightning', 'mortar')):
                    self.incoming_bearing, self.incoming_bearing_at = bearing, now
                if (fresh_damage and event.get('by') in visible_hostiles
                    and event.get('weapon') in ('gun','mortar','laser','lightning','npc')
                    ):
                    fresh_hitters.add(event['by'])
            elif event['type'] == 'hit':
                self.last_combat = now
            elif event['type'] == 'took':
                self.memory.pop(event['id'], None)
        if fresh_hitters:
            self.last_weapon_damage = now
            self.last_weapon_attackers = tuple(sorted(fresh_hitters))
        self.last_damage_observation_tick = max(self.last_damage_observation_tick,obs['tick'])

    def _zone_goal(self, obs, stats):
        pos, zone, now = obs['self']['pos'], obs['zone'], obs['t']
        # Plan against the circle at a conservative travel ETA rather than chasing its center.
        distance_to_next = max(0., math.dist(pos[:2], zone['next_center']) - zone['next_radius'] + 15)
        eta = distance_to_next / max(1, stats['walk_speed'] * .7)
        horizon = max(6., min(50., eta + 8.))
        center, radius = circle_at(zone, now, horizon)
        margin = min(24., max(stats['radius'] + 3, radius * .12))
        safe_radius = max(0., radius - margin)
        ux, uy = unit(pos[0]-center[0], pos[1]-center[1])
        d = math.dist(pos[:2], center)
        if d > safe_radius:
            goal = (center[0]+ux*safe_radius, center[1]+uy*safe_radius)
        else:
            # Favor a quiet interior flank, avoiding convergence at one central point.
            goal = pos[:2]
        # Late phases require an interior anchor before radius reaches zero.
        if radius < 35:
            goal = center
        return tuple(goal), center, radius

    def _safe_objective(self, pos, obs, stats):
        distance = math.dist(pos[:2], obs['self']['pos'][:2])
        eta = distance / max(1, stats['walk_speed'] * .7) + 4
        center, radius = circle_at(obs['zone'], obs['t'], eta)
        return outside_distance(pos, center, max(0., radius-stats['radius']-3)) <= .1

    def _inside_playable(self, pos):
        if not self.arena.available:
            return True
        margin = self.config['match'].get('arena_margin', 0.)
        return self.arena.in_bounds(pos[0], pos[1], margin)

    def _playable_destination(self, pos, obs, stats):
        return self._inside_playable(pos) and self._safe_objective(pos, obs, stats)

    def _noise_risk(self, pos):
        risk = 0.
        for expires,x,y,bearing,low,high,sigma in self.noise:
            dx,dy = pos[0]-x,pos[1]-y
            distance = math.hypot(dx,dy)
            if not max(2.,low-8) <= distance <= high+8:
                continue
            delta = (math.atan2(dy,dx)-bearing+math.pi)%math.tau-math.pi
            if abs(delta) <= sigma*3:
                risk += math.exp(-.5*(delta/sigma)**2)
        return min(3.,risk)

    def _exposure(self, pos, enemies, stats):
        danger = 0.0
        for enemy in enemies[:2]:
            distance = math.dist(pos[:2], enemy['pos'][:2])
            if distance > 230:
                continue
            scale = 1 + self.config['cubes'].get('size_per_cube', .05) * enemy.get('cubes', 0)
            enemy_muzzle = (enemy['pos'][0], enemy['pos'][1], enemy['pos'][2]+self.config['mech']['muzzle_height']*scale)
            center = (pos[0], pos[1], pos[2]+stats['height']*.5)
            exposed = not self.arena.available or self.arena.line_clear(enemy_muzzle, center)
            danger += (1.0 if exposed else .08) * max(0., 240-distance) / 120
        return danger

    def _healing_drop(self,obs,stats,enemies):
        me,now=obs['self'],obs['t']
        if not me['grounded']:
            return None
        remaining_delay=max(0.,stats['regen_delay']-(now-self.last_combat))
        regen_eta=remaining_delay+max(0.,me['max_hp']*.92-me['hp'])/max(1.,stats['regen_per_s'])
        options=[]
        for drop in obs.get('drops',[]):
            if drop.get('holder') not in (None,me['id']):
                continue
            pos=drop['pos'];distance=math.dist(pos[:2],me['pos'][:2])
            if distance>100 or self._noise_risk(pos)>.7:
                continue
            arrival=max(0.,distance-max(1.,drop['radius']-2))/max(1.,stats['walk_speed']*.7)
            capture=drop['capture_s']-(drop.get('progress',0) if drop.get('holder')==me['id'] else 0.)
            eta=max(arrival,drop['lands_in'])+max(0.,capture)
            if eta+2>=regen_eta:
                continue
            center,radius=circle_at(obs['zone'],now,eta+1)
            if outside_distance(pos,center,max(0.,radius-stats['radius']-3))>0:
                continue
            # Straight-line rival arrival is an optimistic lower bound for them.
            if any(max(0.,math.dist(e['pos'][:2],pos[:2])-drop['radius'])/max(self.enemy_speed_bound,math.hypot(*e.get('vel',[0,0,0])[:2]))<=eta+1 for e in enemies if e['id']!=me['id']):
                continue
            if not self.arena.point_clear(pos,stats['radius'],stats['height']):
                continue
            # Only take a healing detour with a confirmed direct ground route;
            # an unmeasured long wall/roof detour can invalidate the ETA.
            if not self.arena.move_clear(me['pos'],pos,stats['radius'],stats['height'],stats['step_up'],stats['max_slope_deg'],grounded=me['grounded']):
                continue
            options.append((eta,drop))
        return min(options,key=lambda item:item[0])[1] if options else None

    def _crate_standoff(self, crate, obs, stats):
        """A bounded, shootable gun position, rather than the crate's feet."""
        me=obs['self'];pos=me['pos'];target=crate['pos']
        gun=next((w for w in me['weapons'] if w and w['kind']=='gun'),None)
        if gun is None:
            return None
        weapon_stats={**self.config['weapons']['gun'],**gun.get('stats',{})}
        center=(target[0],target[1],target[2]+self.config['crates']['height']*.5)
        reach=stats['radius']+.5
        pitch_margin=min(.03,max(0.,stats['max_pitch']-stats['min_pitch'])*.1)
        low,high=stats['min_pitch']+pitch_margin,stats['max_pitch']-pitch_margin
        def shootable(point):
            dx,dy=center[0]-point[0],center[1]-point[1]
            horizontal=math.hypot(dx,dy)
            dz=center[2]-point[2]-stats['muzzle_height']
            pitch=math.atan2(dz,horizontal)
            distance=math.hypot(horizontal,dz)
            if not low<=pitch<=high or distance<=reach+1 or distance-reach>weapon_stats['range']:
                return False
            base=(point[0],point[1],point[2]+stats['muzzle_height'])
            tip=tuple(base[i]+(center[i]-base[i])*reach/distance for i in range(3))
            return (self._playable_destination(point,obs,stats)
                    and self.arena.point_clear(point,stats['radius'],stats['height'])
                    and self.arena.line_clear(base,tip) and self.arena.line_clear(tip,center))
        ux,uy=unit(pos[0]-target[0],pos[1]-target[1])
        if ux==uy==0:
            ux,uy=-math.cos(me['aim'][0]),-math.sin(me['aim'][0])
        # Account for the muzzle extension conservatively, then update against
        # terrain at each candidate. Three attempts are a work bound, not a
        # promise that every crate has a reachable firing position.
        distance=max(reach+self.config['crates']['radius']+2,reach+2)
        height=pos[2]
        previous=None
        for _ in range(3):
            delta=center[2]-height-stats['muzzle_height']
            limit=-low if delta<0 else high
            if limit<=0:
                return None
            distance=max(distance,reach+abs(delta)/max(.001,math.tan(min(1.5,limit)))+2)
            if math.dist(pos[:2],target[:2])<=distance+2 and shootable(pos):
                return tuple(pos)
            x,y=target[0]+ux*distance,target[1]+uy*distance
            height=self.arena.surface_height(x,y,pos[2],stats['step_up'],stats['height'])
            point=(x,y,height)
            if point==previous:
                break
            previous=point
            if shootable(point):
                return point
        return None

    def _engagement_goal(self, obs, stats, enemies):
        """Experimental lightning engagement; priorities and local safety remain outside."""
        me=obs['self'];pos=me['pos']
        if len(enemies)!=1 or self.recovering or me['hp']<me['max_hp']*.5:
            return None
        enemy=enemies[0]
        if (math.dist(pos[:2],enemy['pos'][:2])>=100
                or any(kind in enemy.get('weapons',[]) for kind in ('mortar','lightning'))):
            return None
        shown_hp=enemy.get('hp')
        if shown_hp is not None and me['hp']<shown_hp*.65:
            return None
        lightning=next((w for w in me['weapons'] if w and w['kind']=='lightning'),None)
        if lightning is None:
            return None
        weapon={**self.config['weapons']['lightning'],**lightning.get('stats',{})}
        capacity=max(1.,me['max_energy'])
        continuing=self.mode=='engage'
        if (me['energy']<weapon['energy']+12
                or (continuing and me['energy']<=capacity*.3)
                or (not continuing and me['energy']<capacity*.7)):
            return None
        scale=1+self.config['cubes'].get('size_per_cube',.05)*enemy.get('cubes',0)
        enemy_radius=self.config['mech']['radius']*scale
        center=(enemy['pos'][0],enemy['pos'][1],enemy['pos'][2]+self.config['mech']['height']*scale*.5)
        radius=max(weapon['range']*.65,stats['radius']+enemy_radius+2)
        if radius>=weapon['range']*.95:
            return None
        reach=stats['radius']+.5
        yaw,pitch=me['aim']
        muzzle_offset=(reach*math.cos(pitch)*math.cos(yaw),reach*math.cos(pitch)*math.sin(yaw),
                       stats['muzzle_height']+reach*math.sin(pitch))
        origin=tuple(pos[i]+muzzle_offset[i] for i in range(3))
        if not self.arena.line_clear(origin,center):
            return None
        ux,uy=unit(pos[0]-enemy['pos'][0],pos[1]-enemy['pos'][1])
        if ux==uy==0:
            return None
        for strafe in (self.controller.side*.35,-self.controller.side*.35,0.):
            dx,dy=unit(ux-uy*strafe,uy+ux*strafe)
            x,y=enemy['pos'][0]+dx*radius,enemy['pos'][1]+dy*radius
            point=(x,y,self.arena.surface_height(x,y,pos[2],stats['step_up'],stats['height']))
            muzzle=tuple(point[i]+muzzle_offset[i] for i in range(3))
            if (self._safe_objective(point,obs,stats)
                    and self.arena.point_clear(point,stats['radius'],stats['height'])
                    and math.dist(muzzle,center)<=weapon['range']
                    and self.arena.line_clear(muzzle,center)):
                return point
        return None

    def _covered_from(self, point, stats, threats):
        for enemy in threats:
            x, y, z = enemy['pos']
            scale = 1 + self.config['cubes']['size_per_cube'] * enemy['cubes']
            muzzle = (x, y, z + self.config['mech']['muzzle_height'] * scale)
            for fraction in (.5, .9):
                if self.arena.line_clear(muzzle, (*point[:2], point[2] + stats['height'] * fraction)):
                    return False
        return True

    def _resource_plan(self, obs, stats, enemies):
        """Compare opening routes and, for exposed pickups, a reachable exit."""
        me, now = obs['self'], obs['t']
        pos = me['pos']
        equipped = {w['kind'] for w in me['weapons'] if w}
        visible_crates = {c['id'] for c in obs['crates']}
        threat = enemies[0] if enemies else None
        if threat and math.dist(threat['pos'][:2], pos[:2]) > 160:
            threat = None
        if self.pickup_plan:
            ident, kind, goal, exit_point, when = self.pickup_plan
            took_weapon = kind == 'pickups' and any(
                event.get('type') == 'took' and event.get('id') == ident for event in obs['events'])
            if took_weapon and exit_point and threat:
                self.pickup_plan = None, 'exit', exit_point, None, now
                ident, kind, goal, exit_point, when = self.pickup_plan
            if kind == 'exit' and threat and now-when < 2.5 and math.dist(pos[:2], goal[:2]) > 3 and self._playable_destination(goal, obs, stats):
                self.goal_id, self.mode = None, 'pickup_exit'
                return goal
        seek_upgrade = (self.seek_laser and len(equipped) == 2 and 'laser' not in equipped
                        and me['hp'] >= .75 * me['max_hp'] and now - self.last_weapon_damage > 3
                        and (not threat or math.dist(threat['pos'][:2], pos[:2]) >= 85))
        context = (frozenset(equipped), threat['id'] if threat else None, me['cubes'], seek_upgrade)
        if context == self.plan_context and now-self.plan_checked < .6:
            if self.pickup_plan:
                ident, kind, goal, _, _ = self.pickup_plan
                entry = self.memory.get(ident)
                if (entry and kind == 'crates' and ident not in visible_crates and
                        now-entry[2] > 1 and math.dist(pos[:2], goal[:2]) < 2):
                    self.memory.pop(ident)
                    entry = None
                if entry and self._safe_objective(goal, obs, stats):
                    self.goal_id, self.mode = ident, kind
                    return goal
            return None
        self.plan_context, self.plan_checked = context, now
        self.pickup_plan = None
        self.rejected_pickups.clear()
        choices = []
        for ident, (kind, item, seen) in self.memory.items():
            point = item['pos']
            distance = math.dist(point[:2], pos[:2])
            if distance > 155 or not self._safe_objective(point, obs, stats):
                continue
            if abs(point[2]-self.arena.terrain_height(*point[:2])) > 3 and abs(pos[2]-point[2]) > 3:
                continue
            if kind == 'pickups' and len(equipped) == 1 and item['kind'] not in equipped:
                value = 105 if self.match_policy == 'farm' else 155
                value += {'lightning': 14, 'laser': 20, 'mortar': 0}.get(item['kind'], 0)
            elif (seek_upgrade and kind == 'pickups' and item['kind'] == 'laser'
                  and now - seen <= 8 and distance <= 100):
                value = 115
            elif kind == 'cubes' and me['cubes'] < self.config['cubes']['stat_cap']:
                value = 130 if self.match_policy == 'farm' else 55
            elif kind == 'crates' and self.match_policy == 'farm' and not threat and distance < 55:
                value = 72 if me['cubes'] < self.config['cubes']['stat_cap'] else 0
            else:
                continue
            score = value - distance - (now-seen)*.7
            if threat:
                score -= max(0., distance - math.dist(point[:2], threat['pos'][:2])) * 1.5
            if score > 0:
                choices.append((score, ident, kind, item))
        best = 0
        for score, ident, kind, item in sorted(choices, key=lambda c: -c[0])[:3]:
            if score <= best:
                break
            goal = self._crate_standoff(item, obs, stats) if kind == 'crates' else item['pos']
            if goal is None or not self.arena.point_clear(goal, stats['radius'], stats['height']):
                continue
            if (kind == 'crates' and ident not in visible_crates and now-self.memory[ident][2] > 1
                    and math.dist(pos[:2], goal[:2]) < 2):
                self.memory.pop(ident)
                continue
            exit_point = None
            if threat and self.match_policy == 'covered':
                if kind == 'pickups':
                    self.rejected_pickups.add(ident)
                score -= 35 * self._exposure(goal, [threat], stats)
                if score <= best:
                    continue
                dx, dy = unit(goal[0]-threat['pos'][0], goal[1]-threat['pos'][1])
                for ux, uy in ((-dy,dx),(dy,-dx),(dx,dy)):
                    x, y = goal[0]+ux*14, goal[1]+uy*14
                    end = (x,y,self.arena.surface_height(x,y,goal[2],stats['step_up'],stats['height']))
                    if (self._playable_destination(end, obs, stats)
                        and self.arena.move_clear(goal,end,stats['radius'],stats['height'],stats['step_up'],stats['max_slope_deg'])
                        and self._covered_from(end, stats, enemies[:2])):
                        exit_point = end
                        break
                if exit_point is None:
                    score -= 35
            if score > best:
                best = score
                self.pickup_plan = ident, kind, goal, exit_point, now
        if self.pickup_plan:
            self.goal_id, self.mode, goal, _, _ = self.pickup_plan
            self.rejected_pickups.discard(self.goal_id)
            return goal
        return None

    def _goal(self, obs, stats):
        me, now = obs['self'], obs['t']
        pos = me['pos']
        zone_goal, center, radius = self._zone_goal(obs, stats)
        enemies = sorted((e for e in obs['mechs'] if e['kind']=='mech'), key=lambda e: math.dist(e['pos'][:2], pos[:2]))
        if self.match_policy == 'adaptive':
            self.goal_id = None
            self.mode = 'explore'
            if me['in_zone']:
                resource = self.match_state.choose_loot(self, obs, stats, enemies)
                if resource is not None:
                    return resource
            return (*zone_goal, self.arena.terrain_height(*zone_goal))
        nearest = math.dist(enemies[0]['pos'][:2], pos[:2]) if enemies else float('inf')
        fraction = me['hp'] / max(1., me['max_hp'])
        if fraction < self.recovery_trigger:
            self.recovering = True
        if (self.match_policy in ('weapon', 'covered', 'farm') and fraction < .68
                and now-self.last_weapon_damage < 1.5 and enemies
                and enemies[0].get('hp', 0) > me['hp'] * 1.15):
            self.recovering = True
        if fraction > .92 or (obs['alive'] <= 2 and nearest < 45):
            self.recovering = False
        if not me['in_zone'] or math.dist(zone_goal, pos[:2]) > 4:
            self.pickup_plan = None
            self.plan_context = None
            self.mode = 'zone'
            self.goal_id = None
            return (*zone_goal, self.arena.terrain_height(*zone_goal))
        if self.recovering and self.healing_drops:
            healing=self._healing_drop(obs,stats,enemies)
            if healing:
                self.mode,self.goal_id='heal_drop',healing['id']
                return healing['pos']
        if self.recovering or (len(enemies) >= 2 and nearest < 95):
            self.pickup_plan = None
            self.plan_context = None
            self.mode = 'recover' if self.recovering else 'disengage'
            self.goal_id = None
            # Search a bounded ring of cover/escape positions, respecting future zone.
            # Evaluate a rotating subset each decision: never an unbounded ray fan.
            epoch = int(now * 2)
            if epoch != self.cover_epoch:
                self.cover_epoch = epoch
                self.cover_cost = float('inf')
                self.cover_choice = None
            choices = [tuple(pos)]
            phase = int(obs['tick'] / self.config['match']['decide_every']) % 6
            for i in (phase, phase + 6):
                distance = 32.
                a = i * math.tau / 12 + self.slot * .17
                x, y = pos[0]+distance*math.cos(a), pos[1]+distance*math.sin(a)
                p = (x, y, self.arena.surface_height(x,y,pos[2],stats['step_up'],stats['height']))
                if self._playable_destination(p, obs, stats):
                    choices.append(p)
            def cover_cost(p):
                travel = math.dist(p[:2], pos[:2])
                dist = min((math.dist(p[:2], e['pos'][:2]) for e in enemies), default=200.)
                exposure = self._exposure(p, enemies, stats)
                return exposure * 25 + max(0., 110-dist) * .3 + travel * .04 + self._noise_risk(p)*3
            # Reject impossible stand points before committing to cover.
            if self.arena.available:
                choices = [p for p in choices if self.arena.point_clear(p, stats['radius'], stats['height'])] or [tuple(pos)]
            for p in choices:
                cost = cover_cost(p)
                if cost < self.cover_cost:
                    self.cover_choice, self.cover_cost = p, cost
            return self.cover_choice or tuple(pos)
        held = {w['kind'] for w in me['weapons'] if w}
        empty_slot = any(w is None for w in me['weapons'])
        if self.match_policy in ('weapon', 'covered', 'farm') and now < 75:
            planned = self._resource_plan(obs, stats, enemies)
            if planned is not None:
                return planned
        candidates = []
        for ident, (kind, item, seen) in self.memory.items():
            p = item['pos']
            if self.match_policy == 'covered' and now < 75 and ident in self.rejected_pickups:
                continue
            distance = math.dist(pos[:2], p[:2])
            if distance > 150 or not self._safe_objective(p, obs, stats):
                continue
            # Ground routing deliberately avoids expensive roof expeditions for loot.
            ground = self.arena.terrain_height(p[0],p[1])
            if abs(p[2]-ground) > stats['step_up']+2 and abs(p[2]-pos[2]) > 3:
                continue
            if kind == 'cubes':
                value = 65 if me['cubes'] < self.config['cubes'].get('stat_cap',10) else 16
            elif kind == 'pickups':
                if item['kind'] in held or item['kind']=='gun':
                    continue
                rank = {'laser':75, 'mortar':60, 'lightning':50}.get(item['kind'],0)
                if not empty_slot:
                    if item['kind']!='laser' or 'laser' in held:
                        continue
                    rank *= .3
                value = rank
            elif kind == 'crates':
                if nearest < 100 or me['cubes'] >= self.config['cubes'].get('stat_cap',10):
                    continue
                value = 35
            else:
                continue
            danger = sum(max(0., 100-math.dist(p[:2], e['pos'][:2]))*.5 for e in enemies[:6])
            score = value - distance*.55 - danger - (now-seen)*.12 - self._noise_risk(p)*3
            if ident == self.goal_id:
                score += 6  # objective hysteresis
            if score > 0:
                candidates.append((score, ident, kind, p))
        for drop in obs.get('drops',[]):
            p = drop['pos']
            distance = math.dist(pos[:2], p[:2])
            rivals = sum(math.dist(p[:2],e['pos'][:2]) < 75 for e in enemies)
            if rivals or not self._safe_objective(p,obs,stats):
                continue
            eta = distance/max(1.,stats['walk_speed'])
            if drop['lands_in'] > eta+10 or distance > 220:
                continue
            value = 105 + (1-fraction)*70 - distance*.6 - max(0.,drop['lands_in']-eta)*2
            if value > 0:
                candidates.append((value,drop['id'],'drop',p))
        if candidates:
            crate_checks=0
            visible_crates={item['id'] for item in obs['crates']}
            for _, ident, kind, goal in sorted(candidates, key=lambda c:c[0],reverse=True):
                if kind=='crates':
                    if crate_checks>=3:
                        continue
                    crate_checks+=1
                    entry=self.memory[ident]
                    goal=self._crate_standoff(entry[1],obs,stats)
                    if goal is None:
                        continue
                    # Once at a firing position, do not camp an obsolete or
                    # currently unobservable crate memory indefinitely.
                    if ident not in visible_crates and now-entry[2]>1 and math.dist(pos[:2],goal[:2])<2:
                        self.memory.pop(ident,None)
                        continue
                if self.arena.available and not self.arena.point_clear(goal,stats['radius'],stats['height']):
                    continue
                self.goal_id, self.mode = ident, kind
                return goal
        self.goal_id = None
        if self.loadout_engagement:
            engagement=self._engagement_goal(obs,stats,enemies)
            if engagement is not None:
                self.mode='engage'
                return engagement
        # Kite immediate pursuers, preserving range instead of running into them.
        if enemies and nearest < 100:
            enemy = enemies[0]
            ux,uy = unit(pos[0]-enemy['pos'][0],pos[1]-enemy['pos'][1])
            side = self.controller.side
            p = (pos[0]+ux*24-uy*side*12, pos[1]+uy*24+ux*side*12)
            # At the playable boundary, continue along it if the retreat is blocked.
            if self._inside_playable(p):
                choices = [p]
            else:
                choices = [(pos[0]-uy*sign*24, pos[1]+ux*sign*24) for sign in (side, -side)]
            for p in choices:
                if self._playable_destination(p, obs, stats):
                    self.mode = 'kite'
                    return (*p, self.arena.terrain_height(*p))
        self.mode='explore'
        # Short exploratory arcs reveal loot; retain a goal long enough to make progress.
        if self.last_goal and math.dist(self.last_goal[:2],pos[:2])>8 and self._playable_destination(self.last_goal,obs,stats):
            return self.last_goal
        a=now*.025+self.slot*2.399963229728653
        directions = []
        for offset in (0,math.pi/2,-math.pi/2,math.pi):
            x,y=pos[0]+45*math.cos(a+offset),pos[1]+45*math.sin(a+offset)
            p=(x,y,self.arena.terrain_height(x,y))
            if self._playable_destination(p,obs,stats):
                directions.append(p)
        if directions:
            return min(directions,key=self._noise_risk)
        return (*zone_goal,self.arena.terrain_height(*zone_goal))

    def _mortar_cookoff_threat(self, obs):
        me = obs['self']
        defense = self._stats(me)
        for enemy in obs['mechs']:
            if enemy['kind']!='mech' or not enemy.get('charging') or 'laser' not in enemy.get('weapons',[]):
                continue
            damage = self.config['weapons']['laser']['damage'] * (1+self.config['weapons']['laser'].get('cookoff',.6))
            damage *= 1+self.config['cubes'].get('damage_per_cube',.04)*min(enemy.get('cubes',0),self.config['cubes'].get('stat_cap',10))
            # Conservative full-charge estimate, not an exact armored
            # damage prediction: enemy upgrades are not observable.
            source_bearing=math.atan2(enemy['pos'][1]-me['pos'][1],enemy['pos'][0]-me['pos'][0])
            relative=abs((source_bearing-me['aim'][0]+math.pi)%math.tau-math.pi)
            if relative>math.radians(defense.get('front_arc_deg',180))*.5:
                damage*=defense.get('rear_mult',1.5)
            if me['hp'] > damage*.9 or math.dist(me['pos'],enemy['pos']) > self.config['weapons']['laser']['range']:
                continue
            yaw=math.atan2(me['pos'][1]-enemy['pos'][1],me['pos'][0]-enemy['pos'][0])
            if abs((yaw-enemy['aim'][0]+math.pi)%math.tau-math.pi)>.3:
                continue
            scale=1+self.config['cubes'].get('size_per_cube',.05)*enemy.get('cubes',0)
            start=(enemy['pos'][0],enemy['pos'][1],enemy['pos'][2]+self.config['mech']['muzzle_height']*scale)
            end=(me['pos'][0],me['pos'][1],me['pos'][2]+defense['height']*.5)
            if self.arena.line_clear(start,end):
                return True
        return False

    def _take_and_upgrade(self, obs, action):
        me=obs['self']
        held={w['kind'] for w in me['weapons'] if w}
        rank={'gun':0,'lightning':1,'mortar':2,'laser':3}
        reach=self.config['loot']['pickup_radius']
        available=[p for p in obs['pickups'] if p['kind'] not in held and math.dist(p['pos'][:2],me['pos'][:2])<=reach and abs(p['pos'][2]-me['pos'][2])<=4]
        if self.match_policy == 'adaptive':
            available = [p for p in available if p['kind'] != 'mortar']
        dangerous = (self.recovering and ('mortar' in held or any(p['kind']=='mortar' for p in available))
                     and self._mortar_cookoff_threat(obs))
        if dangerous:
            # Each drop spawns a fresh item ID. Re-evaluate the hazard on each observation.
            available = [p for p in available if p['kind'] != 'mortar']
        if dangerous and 'mortar' in held and 'take' not in action:
            action['drop'] = next(i for i, w in enumerate(me['weapons']) if w and w['kind']=='mortar')
            if available:
                action['take'] = max(available, key=lambda p: rank[p['kind']])['id']
        elif available:
            pickup=max(available,key=lambda p:rank[p['kind']])
            if any(w is None for w in me['weapons']):
                action['take']=pickup['id']
            else:
                slot=min(range(2),key=lambda i:rank[me['weapons'][i]['kind']])
                weapon=me['weapons'][slot]
                # Keep the gun's reliable damage until a complementary second weapon exists.
                if weapon['kind']=='gun':
                    slot=1-slot
                    weapon=me['weapons'][slot]
                if rank[pickup['kind']]>rank[weapon['kind']] and not weapon.get('charge',0):
                    action.update(take=pickup['id'],drop=slot)
        offer=obs.get('offer')
        if offer and self.match_policy == 'adaptive' and offer['choices']:
            action['pick'] = choose_upgrade(offer,self.field_mode)
        elif offer and offer['choices']:
            # Inference from mechanics; these priorities still require match validation.
            weights={'servos':10,'nanites':9 if self.recovering else 7,'armor':8,'plating':7,'gun_damage':6,'gun_rate':6,'gun_mag':6,'gun_velocity':5.5,'reactor':6,'jets':5,'capacitor':4,'gyros':4,'sensors':3,'laser_damage':7,'laser_charge':7,'laser_pierce':3,'mortar_splash':5,'mortar_reload':5,'mortar_velocity':4,'lightning_range':5,'lightning_efficiency':4,'lightning_chain':3}
            action['pick']=max(range(len(offer['choices'])),key=lambda i:weights.get(offer['choices'][i]['id'],1))

    def _idle_scan(self, obs, stats, waypoint):
        me=obs['self']
        if self.match_policy == 'adaptive':
            recent_drone = self.match_state.last_drone_hit
            if recent_drone and recent_drone[2] is not None and obs['t']-recent_drone[0] < 2.5:
                return [recent_drone[2], 0.]
            if self.incoming_bearing is not None and obs['t']-self.incoming_bearing_at < 2.5:
                return [self.incoming_bearing, 0.]
            dx, dy = waypoint[0]-me['pos'][0], waypoint[1]-me['pos'][1]
            yaw = math.atan2(dy,dx)+1.15*math.sin(obs['t']*1.3) if math.hypot(dx,dy)>.1 else me['aim'][0]+.35
            return [math.remainder(yaw,math.tau), 0.]
        if (self.match_policy in ('weapon', 'covered', 'farm', 'adaptive') and self.incoming_bearing is not None
                and 0 <= obs['t']-self.incoming_bearing_at < 1.5):
            return [self.incoming_bearing, 0.]
        if self.scan_sweep and obs['t']-self.last_damage>1.:
            # A continuous sweep also observes the rear beyond proximity range.
            # Resume from actual aim after combat, respecting live slew speed.
            interval=self.config['match']['decide_every']/self.config['match']['tick_hz']
            yaw=me['aim'][0]+stats['turn_rate']*.5*interval
            return [(yaw+math.pi)%math.tau-math.pi,0.]
        yaw=math.atan2(waypoint[1]-me['pos'][1],waypoint[0]-me['pos'][0])
        return [yaw+math.sin(obs['t']*.8+self.slot)*.8,0.]

    def act(self, obs):
        deadline = time.perf_counter() + self.config['bot']['tick_budget_ms'] * .00056
        if not self.arena.available:
            # Explicit degraded behavior without inventing a terrain model.
            me=obs['self']
            center,_=circle_at(obs['zone'],obs['t'],8.)
            dx,dy=unit(center[0]-me['pos'][0],center[1]-me['pos'][1])
            return {'tick':obs['tick'],'move':[dx,dy],'boost':not me['in_zone'] and me['energy']>10,
                    'aim':[math.atan2(dy,dx),0.], 'fire':[False,False]}
        self._remember(obs)
        adaptive = self.match_policy == 'adaptive'
        selected = None
        defending_drone = None
        if adaptive:
            self.match_state.observe(obs)
            self.field_mode = self.match_state.mode
            self.contacts = self.match_state.contacts
            self.combat.field_mode = self.field_mode
            self.combat.contacts = self.contacts
            self.combat.engagement_ids = self.match_state.eligible_opponents(obs)
            selected = self.combat.preview_target(obs, self.arena, deadline-.016)
            if selected is None or selected['kind'] != 'mech':
                defending_drone = self.match_state.attacking_drone(self, obs)
        me=obs['self']
        stats=self._stats(me)
        if adaptive:
            self.mode, self.goal_id = 'explore', None
            goal = self.field_movement.goal(self, obs, stats, None, deadline-.011, target=selected)
        else:
            goal = self._goal(obs,stats)
        self.last_goal=goal
        region=None
        if self.region_goals and self.mode=='zone':
            _,center,radius=self._zone_goal(obs,stats)
            if radius>=35:
                margin=min(24.,max(stats['radius']+3,radius*.12))
                region=(center,max(0.,radius-margin))
        waypoint=self.navigator.waypoint(me['pos'],goal,stats,obs['t'],goal_region=region)
        action=self.controller.choose(obs,waypoint,goal,recovering=self.recovering,allow_dodge=self.ablation!='no_dodge',deadline=deadline-.010)
        if adaptive:
            self.field_movement.motion(self, obs, action)
        enemies=[e for e in obs['mechs'] if e['kind']=='mech']
        immediate=any(math.dist(e['pos'][:2],me['pos'][:2])<38 for e in enemies)
        defensive = (self.recovery_defense and self.recovering and not immediate
                     and 0 <= obs['t']-self.last_weapon_damage <= .2
                     and any(e['id'] in self.last_weapon_attackers for e in enemies))
        # Preserve recovery even while the five-second delay is still counting.
        allow_combat=not self.recovering or immediate or defensive
        preferred = self.goal_id if self.mode == 'crates' and not self.recovering and not any(math.dist(e['pos'][:2],me['pos'][:2])<100 for e in enemies) else None
        if adaptive:
            preferred = selected
            if selected is None and self.mode in ('crates', 'npc'):
                farm_range = 50 if self.mode == 'crates' else 75
                entities = obs['crates'] if self.mode == 'crates' else obs['mechs']
                farm = next((e for e in entities if e['id'] == self.goal_id), None)
                if farm and math.dist(me['pos'][:2], farm['pos'][:2]) < farm_range:
                    center = self.combat._center(dict(farm, kind='crate') if self.mode == 'crates' else farm)
                    if self.arena.line_clear(self.combat._origin(me, arena=self.arena), center):
                        preferred = self.goal_id
            if defending_drone is not None:
                preferred = defending_drone
            # Retain defensive fire when retreating from a tracked attacker.
            allow_combat = not self.recovering or defending_drone is not None or (selected is not None and selected['kind']=='mech')
            defensive = False
        action.update(self.combat.choose(obs,self.arena,allow_combat=allow_combat,preferred_target=preferred,
                                         deadline=deadline,defensive=defensive,target_assigned=adaptive))
        charging = any(w and w['kind']=='laser' and w.get('charge',0)>0 for w in me['weapons'])
        if (adaptive or not enemies) and not getattr(self.combat,'target',None) and not charging and not getattr(self.combat,'watching',False):
            action['aim']=self._idle_scan(obs,stats,waypoint)
        self._take_and_upgrade(obs,action)
        action['tick']=obs['tick']
        mf.draw.label(f'{self.mode} hp {me["hp"]:.0f} E {me["energy"]:.0f}')
        return action


if __name__ == '__main__':
    os.environ.setdefault('KANYARAASI_MATCH_POLICY', 'adaptive')
    mf.run(Bot)
