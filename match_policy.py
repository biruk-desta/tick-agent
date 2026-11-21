"""Match interpretation and resource choices for the adaptive controller."""
import math


from arena_model import Arena
from firstparty_movement import _component


class FlatArena(Arena):
    """Open, level fallback when the organizer's map cannot be read."""
    def __init__(self, zone):
        x,y = zone['start_center']
        radius = max(100.,zone['start_radius'])
        self.bounds = {'minX':x-radius,'maxX':x+radius,'minY':y-radius,'maxY':y+radius}
        self.available = True
        self.error = None
        self.prisms = []
        self._grid = {}

    def terrain_height(self, x, y):
        return 0.


class MatchState:
    def __init__(self):
        self.initial_alive = None
        self.eliminations = set()
        self.unexplained_observations = 0
        self.last_tick = -1
        self.mode = 'squad'
        self.hits_from = {}
        self.last_drone_hit = None
        self.contacts = {}
        self.ignore_until = {}
        self.objective = None
        self.objective_since = 0.

    def observe(self, obs):
        now = obs['t']
        if self.initial_alive is None:
            self.initial_alive = obs['alive']
        self.contacts.update((actor['id'], (actor, now)) for actor in obs['mechs'])
        for event in obs['events']:
            if event['type'] == 'damaged' and event.get('by') is not None:
                self.hits_from[event['by']] = now
            if event['type'] == 'damaged' and event.get('weapon')=='npc':
                self.last_drone_hit = (now,event.get('by'),event.get('bearing'))
            if event['type'] == 'kill':
                self.eliminations.add(event['target'])
                self.contacts.pop(event['target'], None)
        self.contacts = {k: (actor, seen) for k, (actor, seen) in self.contacts.items()
                         if now-seen <= (120 if actor['kind'] == 'npc' else 20)}
        # Count delivered decisions. A dropped input batch must not imply several
        # independent confirmations of a death before its kill event arrives.
        if self.mode != 'ffa' and obs['tick'] > self.last_tick:
            unexplained = self.initial_alive - obs['alive'] > len(self.eliminations)
            self.unexplained_observations = self.unexplained_observations + 1 if unexplained else 0
            if self.unexplained_observations >= 5:
                self.mode = 'ffa'
            elif now > 20:
                self.mode = 'squad'
        self.last_tick = max(self.last_tick, obs['tick'])
        self.ignore_until = {k:t for k,t in self.ignore_until.items() if t > now}

    def eligible_opponents(self, obs):
        me, now = obs['self'], obs['t']
        squad = self.mode == 'squad'
        in_endgame = obs['alive'] <= 3 or obs['zone']['next_radius'] <= 70
        result = set()
        for foe in obs['mechs']:
            if foe['kind'] != 'mech':
                continue
            dx,dy = me['pos'][0]-foe['pos'][0],me['pos'][1]-foe['pos'][1]
            distance = math.hypot(dx,dy)
            if distance > (240 if squad else 215):
                continue
            aim_error = abs(math.remainder(math.atan2(dy,dx)-foe['aim'][0], math.tau))
            since_hit = now-self.hits_from.get(foe['id'],-math.inf)
            if squad:
                closing = ((foe['vel'][0]-me['vel'][0])*dx + (foe['vel'][1]-me['vel'][1])*dy)/max(1., distance)
                engaged = (in_endgame or distance<60 or since_hit<6 or (closing>3 and distance<180)
                           or (foe['hp']<.4*foe['max_hp'] and distance<160)
                           or (aim_error<.22 and distance<190))
            else:
                engaged = (obs['alive'] <= 2 or distance<60 or since_hit<4
                           or (distance<120 and (foe['hp']<350 or (foe.get('charging') and aim_error<.22))))
            if engaged:
                result.add(foe['id'])
        return result

    def attacking_drone(self, bot, obs):
        if self.last_drone_hit is None:
            return None
        when, source, bearing = self.last_drone_hit
        if obs['t']-when >= 3:
            return None
        me = obs['self']
        muzzle = bot.combat._origin(me, arena=bot.arena)
        choices = []
        for actor in obs['mechs']:
            if actor['kind']!='npc' or math.dist(me['pos'][:2],actor['pos'][:2])>150:
                continue
            direction = math.atan2(actor['pos'][1]-me['pos'][1], actor['pos'][0]-me['pos'][0])
            error = abs(math.remainder(direction-bearing,math.tau)) if bearing is not None else math.inf
            if (actor['id']==source or error<.7) and bot.arena.line_clear(muzzle,bot.combat._center(actor)):
                choices.append((actor['id']!=source,error,actor['id'],actor))
        return min(choices)[-1] if choices else None

    def choose_loot(self, bot, obs, stats, enemies):
        me, now = obs['self'], obs['t']
        pos = me['pos']
        squad = self.mode == 'squad'
        held = {w['kind'] for w in me['weapons'] if w}
        health = me['hp']/max(1., me['max_hp'])
        engaged = bot.combat.engagement_ids or set()
        danger = any(m['id'] in engaged or now-self.hits_from.get(m['id'], -math.inf)<4
                     for m in enemies)
        farming = not danger and health > (.5 if squad else .7) and (squad or now < 150)
        below_cap = me['cubes'] < bot.config['cubes']['stat_cap']
        sources = list(bot.memory.items())
        if farming and below_cap:
            sources.extend((ident, ('npc',actor,seen)) for ident,(actor,seen) in self.contacts.items()
                           if actor['kind']=='npc' and now-seen < 12)
        # Mark a repeatedly pursued target unavailable for long enough to find another route.
        if self.objective is not None and now-self.objective_since > 30:
            self.ignore_until[self.objective] = now+60
            self.objective = None

        candidates = []
        for ident,(kind,item,seen) in sources:
            if ident in self.ignore_until:
                continue
            point = item['pos']
            distance = math.dist(pos[:2],point[:2])
            limit = 150 if squad else 90
            if kind == 'pickups':
                weapon = item['kind']
                if (weapon in held or weapon == 'mortar'
                        or (weapon == 'gun' and me['weapons'][0] is not None)
                        or (weapon != 'gun' and 'laser' in held)):
                    continue
                value = 130 if me['weapons'][1] is None else 60
                if squad and weapon == 'laser':
                    limit = 240
                    value = 150
            elif kind == 'cubes':
                limit = 105 if squad else 63
                value = 75 if below_cap else 25
            elif kind == 'crates' and farming:
                value = 45 if below_cap else 15
            elif kind == 'npc' and farming:
                value = 85
            else:
                continue
            if distance>=limit or not bot._playable_destination(point,obs,stats):
                continue
            if point[2]-bot.arena.terrain_height(*point[:2]) > 3.2:
                continue
            if _component(bot,stats,point)=='isolated':
                continue
            priority = value/(distance+18) * (1.35 if ident==self.objective else 1.)
            candidates.append((priority,ident,kind,item))
        for _,ident,kind,item in sorted(candidates,key=lambda row:-row[0])[:4]:
            point = item['pos']
            if kind=='crates':
                distance = math.dist(pos[:2], point[:2])
                center = bot.combat._center(dict(item, kind='crate'))
                if distance < 50 and bot.arena.line_clear(bot.combat._origin(me, arena=bot.arena), center):
                    if distance < 12:
                        away = math.atan2(pos[1]-point[1],pos[0]-point[0]) if distance else me['aim'][0]+math.pi
                        x, y = point[0]+math.cos(away)*14, point[1]+math.sin(away)*14
                        point = (x, y, bot.arena.surface_height(x,y,pos[2],stats['step_up'],stats['height']))
                        if not bot._playable_destination(point,obs,stats):
                            point = bot._crate_standoff(item,obs,stats)
                    else:
                        point = pos
                else:
                    point = bot._crate_standoff(item,obs,stats)
                if point is None:
                    continue
            elif kind=='npc' and math.dist(pos[:2],point[:2]) < 70:
                # Let the arm gun farm the drone while keeping space for an exit.
                dx,dy = pos[0]-point[0],pos[1]-point[1]
                length = max(1.,math.hypot(dx,dy))
                x,y = point[0]+dx/length*52,point[1]+dy/length*52
                stand = (x,y,bot.arena.surface_height(x,y,pos[2],stats['step_up'],stats['height']))
                if bot._playable_destination(stand,obs,stats):
                    point = stand
            if _component(bot,stats,point)=='isolated' or not bot.arena.point_clear(point,stats['radius'],stats['height']):
                continue
            if ident!=self.objective:
                self.objective, self.objective_since = ident, now
            bot.goal_id,bot.mode = ident,kind
            return point
        self.objective = None
        return None


def choose_upgrade(offer, mode):
    # Prefer lasting damage resistance and weapon power. On a squad field the
    # next enemy survives the previous fight, so laser uptime has higher value.
    utility = {'plating':100,'armor':95,'gun_damage':78,'nanites':75,'gun_rate':70,
               'lightning_efficiency':66,'lightning_range':65,'laser_damage':62,'servos':60,
               'laser_charge':55,'gun_mag':50,'gun_velocity':48,'gyros':45,'lightning_chain':40,
               'reactor':38,'capacitor':36,'mortar_reload':29,'mortar_splash':27,
               'mortar_velocity':25,'sensors':20,'jets':15,'laser_pierce':10}
    if mode=='squad':
        utility.update(laser_damage=90,laser_charge=88,nanites=84)
    return max(range(len(offer['choices'])),key=lambda index:utility.get(offer['choices'][index]['id'],0))
