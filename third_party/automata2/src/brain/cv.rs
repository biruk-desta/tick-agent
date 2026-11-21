use super::aim::FireOut;
use super::math::*;
use super::plan::MoveOut;
use super::strategy::zone_at;
use super::{Brain, Mode};
use crate::nav::{Nav, CELL};
use crate::proto::{ActorKind, Event, Obs, WeaponKind};
use crate::world::World;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum CvSt {
    Off,
    Go,
    Wait,
    Out,
    Back,
}

#[derive(Clone, Debug)]
pub(crate) struct Cv {
    pub st: CvSt,
    pub h: V3,
    pub f: V3,
    pub tid: i64,
    pub plan_t: f64,
    pub fail_t: f64,
    pub st_t: f64,
    pub wait_t: f64,
    pub exp_t0: f64,
    pub exp_on: bool,
    pub exp_act: bool,
    pub shot_t: f64,
    pub on_t: f64,
    pub idle_until: f64,
    pub regen: bool,
    pub kills: u32,
    pub k4_t: f64,
    pub dmg4: f64,
    pub dmg4_on: f64,
    pub on_s: f64,
    pub nofit_s: f64,
    pub lz_shots: u32,
    pub lz_hits: u32,
    pub lz_rel_t: f64,
    pub hist: [u32; 8],
    pub hist_act: [u32; 8],
    pub last_log: f64,
    pub last_t: f64,
    pub stats: bool,
    pub id: u64,
    pub ms_max: f64,
    pub slow: [u32; 2],
    pub why: u8,
    pub dmg_why: [f64; 10],
    pub exp_why: [u32; 10],
    pub long_why: [u32; 10],
    pub exp_st: u8,
}

impl Cv {
    pub fn new(id: u64) -> Cv {
        Cv {
            st: CvSt::Off,
            h: [0.0; 3],
            f: [0.0; 3],
            tid: -1,
            plan_t: -1e9,
            fail_t: -1e9,
            st_t: 0.0,
            wait_t: 0.0,
            exp_t0: 0.0,
            exp_on: false,
            exp_act: false,
            shot_t: -1e9,
            on_t: -1e9,
            idle_until: -1e9,
            regen: false,
            kills: 0,
            k4_t: -1.0,
            dmg4: 0.0,
            dmg4_on: 0.0,
            on_s: 0.0,
            nofit_s: 0.0,
            lz_shots: 0,
            lz_hits: 0,
            lz_rel_t: -1e9,
            hist: [0; 8],
            hist_act: [0; 8],
            last_log: -1e9,
            last_t: 0.0,
            stats: std::env::var("PK_STATS").is_ok(),
            id,
            ms_max: 0.0,
            slow: [0; 2],
            why: 0,
            dmg_why: [0.0; 10],
            exp_why: [0; 10],
            long_why: [0; 10],
            exp_st: 0,
        }
    }
}

struct Hos {
    id: i64,
    eye: V3,
    c: V3,
    d: f64,
    hp: f64,
    fresh: bool,
}

fn bin(x: f64) -> usize {
    let e = [0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0];
    e.iter().position(|v| x <= *v).unwrap_or(7)
}

impl Brain {
    fn cv_hos(&self, obs: &Obs) -> Vec<Hos> {
        let t = obs.t;
        let pos = obs.me.pos;
        let mut v = Vec::new();
        for tr in &self.mem.tracks {
            if tr.kind != ActorKind::Mech || t - tr.last_seen > 6.0 {
                continue;
            }
            let q = tr.pos_at(t);
            if !q.iter().all(|x| x.is_finite()) {
                continue;
            }
            let s = 1.0 + self.cfg.cubes.size_per_cube * tr.cubes.max(0.0);
            let d = dist(q, pos);
            if d > 215.0 {
                continue;
            }
            v.push(Hos { id: tr.id, eye: up(q, self.cfg.mech.eye_height * s), c: up(q, self.cfg.mech.height * s * 0.5), d, hp: tr.hp, fresh: t - tr.last_seen < 0.15 });
        }
        v.sort_by(|a, b| a.d.total_cmp(&b.d));
        v.truncate(7);
        v
    }

    fn cv_seen(world: &World, hs: &[Hos], q: V3, h: f64, skip: i64) -> u32 {
        let mut n = 0;
        for o in hs {
            if o.id == skip {
                continue;
            }
            if world.ray(o.eye, up(q, h * 0.5)).is_none() || world.ray(o.eye, up(q, h * 0.95)).is_none() {
                n += 1;
            }
        }
        n
    }

    fn cv_hidden(world: &World, hs: &[Hos], q: V3, h: f64) -> bool {
        for o in hs {
            if world.ray(o.eye, up(q, h * 0.5)).is_none() || world.ray(o.eye, up(q, h * 0.95)).is_none() {
                return false;
            }
        }
        true
    }

    fn cv_plan(&self, obs: &Obs, world: &World, nav: &Nav, hs: &[Hos], tid: i64) -> Option<(V3, V3)> {
        let p = &self.p;
        let pos = obs.me.pos;
        let t = obs.t;
        let h = self.cfg.mech.height;
        let mh = obs.me.stats.muzzle_height;
        let tg = hs.iter().find(|o| o.id == tid)?;
        let tc = tg.c;
        let z = &obs.zone;
        let (zc, zr) = zone_at(z, t, t + p.pk_zone_s, false);
        let (cnx, cny, o) = nav.grid();
        let r = p.pk_r.max(6.0);
        let i0 = (((pos[0] - r - o[0]) / CELL).floor().max(0.0)) as usize;
        let j0 = (((pos[1] - r - o[1]) / CELL).floor().max(0.0)) as usize;
        let i1 = ((((pos[0] + r - o[0]) / CELL).ceil()).max(0.0) as usize).min(cnx.saturating_sub(1));
        let j1 = ((((pos[1] + r - o[1]) / CELL).ceil()).max(0.0) as usize).min(cny.saturating_sub(1));
        let mut qs: Vec<V3> = Vec::new();
        for cj in j0..=j1 {
            for ci in i0..=i1 {
                for nd in nav.cell_node_ids(ci, cj) {
                    let q = nav.node_pos(nd);
                    if (q[2] - pos[2]).abs() > 3.5 || dist(q, pos) > r {
                        continue;
                    }
                    if zr > 0.0 && dist2v(q, zc) > zr - 3.0 {
                        continue;
                    }
                    qs.push(q);
                }
            }
        }
        if qs.len() > 1200 {
            return None;
        }
        let n = qs.len();
        let mut hid = vec![false; n];
        let mut shot = vec![0u8; n];
        let mut order: Vec<usize> = (0..n).collect();
        order.sort_by(|a, b| dist(qs[*a], pos).total_cmp(&dist(qs[*b], pos)));
        for &i in &order {
            if self.spent_ms() > p.pk_ms {
                break;
            }
            hid[i] = Self::cv_hidden(world, hs, qs[i], h);
        }
        let mut best: Option<(f64, V3, V3)> = None;
        let mut tested = 0;
        for &hi in &order {
            if !hid[hi] {
                continue;
            }
            let hq = qs[hi];
            let dh = dist(hq, pos);
            let base = dh * p.pk_w_move - if self.cv.st != CvSt::Off && dist(hq, self.cv.h) < 1.5 { p.pk_keep } else { 0.0 };
            if let Some(b) = best {
                if base - 30.0 > b.0 {
                    break;
                }
            }
            if self.spent_ms() > p.pk_ms + 4.0 {
                break;
            }
            for fi in 0..n {
                let s = dist(qs[fi], hq);
                if s < p.pk_hmin || s > p.pk_hmax || hid[fi] {
                    continue;
                }
                if shot[fi] == 0 {
                    shot[fi] = if world.ray(up(qs[fi], mh), tc).is_none() { 2 } else { 1 };
                }
                if shot[fi] != 2 {
                    continue;
                }
                let others = Self::cv_seen(world, hs, qs[fi], h, tid) as f64;
                let mut sc = base + s * p.pk_w_step + others * p.pk_w_seen;
                if let Some(b) = best {
                    if sc - p.pk_w_wall - p.pk_w_zone > b.0 {
                        continue;
                    }
                }
                tested += 1;
                if !(dh < 1.0 || nav.clear(pos, hq)) || !nav.clear(hq, qs[fi]) {
                    continue;
                }
                let away = sub(hq, tc);
                let l = (away[0].hypot(away[1])).max(1e-6);
                let back = [hq[0] + away[0] / l * 4.0, hq[1] + away[1] / l * 4.0, hq[2]];
                if world.ray(up(hq, h * 0.5), up(back, h * 0.5)).is_some() {
                    sc -= p.pk_w_wall;
                }
                if dist2v(hq, z.next_center) < z.next_radius - 5.0 {
                    sc -= p.pk_w_zone;
                }
                if dh > 3.0 {
                    let mid = [(pos[0] + hq[0]) * 0.5, (pos[1] + hq[1]) * 0.5, (pos[2] + hq[2]) * 0.5];
                    sc += Self::cv_seen(world, hs, mid, h, -1) as f64 * p.pk_w_path;
                }
                if best.map_or(true, |b| sc < b.0) {
                    best = Some((sc, hq, qs[fi]));
                }
                if tested > 300 {
                    break;
                }
            }
        }
        if self.cv.stats && std::env::var("PK_DBG").is_ok() {
            eprintln!("PKP t={:.1} n={} hid={} hs={} best={} ms={:.1}", t, n, hid.iter().filter(|x| **x).count(), hs.len(), best.is_some(), self.spent_ms());
        }
        if best.is_none() {
            for &hi in &order {
                if hid[hi] && (dist(qs[hi], pos) < 1.0 || nav.clear(pos, qs[hi])) {
                    return Some((qs[hi], qs[hi]));
                }
                if self.spent_ms() > p.pk_ms + 6.0 {
                    break;
                }
            }
        }
        if best.is_none() && p.pk_r2 > r {
            let r2 = p.pk_r2;
            let i0 = (((pos[0] - r2 - o[0]) / CELL).floor().max(0.0)) as usize;
            let j0 = (((pos[1] - r2 - o[1]) / CELL).floor().max(0.0)) as usize;
            let i1 = ((((pos[0] + r2 - o[0]) / CELL).ceil()).max(0.0) as usize).min(cnx.saturating_sub(1));
            let j1 = ((((pos[1] + r2 - o[1]) / CELL).ceil()).max(0.0) as usize).min(cny.saturating_sub(1));
            let mut far: Vec<(f64, V3)> = Vec::new();
            let mut cj = j0;
            while cj <= j1 {
                let mut ci = i0;
                while ci <= i1 {
                    for nd in nav.cell_node_ids(ci, cj) {
                        let q = nav.node_pos(nd);
                        let dq = dist(q, pos);
                        if dq <= r || dq > r2 || (q[2] - pos[2]).abs() > 6.0 {
                            continue;
                        }
                        if zr > 0.0 && dist2v(q, zc) > zr - 3.0 {
                            continue;
                        }
                        far.push((dq, q));
                    }
                    ci += 2;
                }
                cj += 2;
            }
            far.sort_by(|a, b| a.0.total_cmp(&b.0));
            for (_, q) in far {
                if self.spent_ms() > p.pk_ms + 6.0 {
                    break;
                }
                if Self::cv_hidden(world, hs, q, h) && nav.clear(pos, q) {
                    return Some((q, q));
                }
            }
        }
        best.map(|b| (b.1, b.2))
    }

    fn cv_count(&mut self, obs: &Obs, exposed: bool, active: bool) {
        let t = obs.t;
        let code = if active { 4 + self.cv.st as usize } else { self.cv.why as usize };
        let dt = (t - self.cv.last_t).clamp(0.0, 0.5);
        self.cv.last_t = t;
        for e in &obs.events {
            match e {
                Event::Kill(_) => {
                    self.cv.kills += 1;
                    if self.cv.kills == 4 {
                        self.cv.k4_t = t;
                    }
                }
                Event::Damaged(d) => {
                    if self.cv.kills >= 4 {
                        self.cv.dmg_why[code.min(9)] += d.amount.max(0.0);
                        self.cv.dmg4 += d.amount.max(0.0);
                        if active {
                            self.cv.dmg4_on += d.amount.max(0.0);
                        }
                    }
                }
                Event::Hit(h) => {
                    if h.weapon == "laser" && t - self.cv.lz_rel_t < 0.35 {
                        self.cv.lz_hits += 1;
                        self.cv.lz_rel_t = -1e9;
                    }
                }
                _ => {}
            }
        }
        if active {
            self.cv.on_s += dt;
        }
        if exposed && (self.cv.exp_act || active) {
            self.cv.exp_why[code.min(9)] += 1;
        }
        if exposed && !self.cv.exp_on {
            self.cv.exp_on = true;
            self.cv.exp_t0 = t;
            self.cv.exp_act = active;
            self.cv.exp_st = code as u8;
        } else if !exposed && self.cv.exp_on {
            self.cv.exp_on = false;
            let d = t - self.cv.exp_t0;
            if d > 1.25 && (self.cv.exp_act || active) {
                self.cv.long_why[(self.cv.exp_st as usize).min(9)] += 1;
            }
            if self.cv.kills >= 4 {
                self.cv.hist[bin(d)] += 1;
            }
            if self.cv.exp_act || active {
                self.cv.hist_act[bin(d)] += 1;
            }
        }
        if self.cv.stats && t - self.cv.last_log >= 1.0 {
            self.cv.last_log = t;
            eprintln!(
                "PKS {} t={:.1} k={} k4={:.1} d4={:.0} d4on={:.0} on={:.1} nofit={:.1} ls={} lh={} ms={:.1} slow={:?} dw={:.0?} ew={:?} lw={:?} h={:?} ha={:?}",
                self.cv.id, t, self.cv.kills, self.cv.k4_t, self.cv.dmg4, self.cv.dmg4_on, self.cv.on_s, self.cv.nofit_s, self.cv.lz_shots, self.cv.lz_hits, self.cv.ms_max, self.cv.slow, self.cv.dmg_why, self.cv.exp_why, self.cv.long_why, self.cv.hist, self.cv.hist_act
            );
        }
    }

    pub(crate) fn cv_post(&mut self, obs: &Obs, world: &World, nav: &Nav, fc: &mut FireOut, mv: &mut MoveOut) {
        let p = self.p.clone();
        let pos = obs.me.pos;
        let h = self.cfg.mech.height;
        let hs = if self.cv.stats || p.pk_on > 0.5 { self.cv_hos(obs) } else { Vec::new() };
        let exposed = hs.iter().any(|o| o.fresh && o.d < 205.0 && (world.ray(o.eye, up(pos, h * 0.5)).is_none() || world.ray(o.eye, up(pos, h * 0.95)).is_none()));
        let active = p.pk_on > 0.5 && self.cv_step(obs, world, nav, &hs, exposed, fc, mv);
        if !active {
            self.cv.st = CvSt::Off;
        }
        self.cv_count(obs, exposed, active);
        let ms = self.spent_ms();
        if obs.t > 2.0 {
            if ms > 25.0 {
                self.cv.slow[0] += 1;
            }
            if ms > 40.0 {
                self.cv.slow[1] += 1;
            }
        }
        if ms > self.cv.ms_max && obs.t > 2.0 {
            self.cv.ms_max = ms;
        }
    }

    fn cv_step(&mut self, obs: &Obs, world: &World, nav: &Nav, hs: &[Hos], exposed: bool, fc: &mut FireOut, mv: &mut MoveOut) -> bool {
        let p = self.p.clone();
        let t = obs.t;
        let me = &obs.me;
        let pos = me.pos;
        let h = self.cfg.mech.height;
        self.cv.why = 1;
        if matches!(self.mode, Mode::Zone) || !me.in_zone || t < self.cv.idle_until {
            return false;
        }
        self.cv.why = 2;
        let fresh: Vec<&Hos> = hs.iter().filter(|o| o.fresh && o.d < p.pk_range).collect();
        if fresh.is_empty() {
            return false;
        }
        let k_on = p.pk_kills <= 0.0 || self.cv.kills as f64 >= p.pk_kills;
        if !(k_on || fresh.len() as f64 >= p.pk_n) {
            return false;
        }
        self.cv.why = 3;
        if fresh.len() == 1 {
            if let Some(tr) = self.mem.tracks.iter().find(|x| x.id == fresh[0].id) {
                let hf = frac(me.hp, me.max_hp);
                if !self.sf_not_harmless(tr) && !tr.has(WeaponKind::Laser) && frac(tr.hp, tr.max_hp) < hf - 0.1 && tr.dmg_to_us < 150.0 {
                    return false;
                }
            }
        }
        self.cv.why = 0;
        let eye = up(pos, me.stats.eye_height);
        for o in &fresh {
            if o.d < p.pk_close && world.ray(eye, o.c).is_none() {
                return false;
            }
        }
        if self.cv.st == CvSt::Off {
            self.cv.on_t = t;
            self.cv.plan_t = -1e9;
        }
        let seen_any = fresh.iter().any(|o| world.sight(eye, o.c));
        self.cv.why = 1;
        if t - self.cv.shot_t.max(self.cv.on_t) > p.pk_idle_max && !seen_any {
            self.cv.idle_until = t + 5.0;
            return false;
        }
        self.cv.why = 9;
        let mut tid = self.cv.tid;
        let cur = fresh.iter().find(|o| o.id == tid).map(|o| o.hp);
        let wk = fresh.iter().min_by(|a, b| a.hp.total_cmp(&b.hp)).map(|o| (o.id, o.hp));
        if let Some((wid, whp)) = wk {
            if cur.map_or(true, |c| whp < c * p.pk_stick) {
                tid = wid;
            }
        }
        if tid != self.cv.tid {
            self.cv.tid = tid;
            self.cv.plan_t = -1e9;
        }
        let h_exposed = self.cv.st != CvSt::Off && Self::cv_seen(world, hs, self.cv.h, h, -1) > 0;
        let (zc, zr) = zone_at(&obs.zone, t, t + p.pk_zone_s, false);
        let h_zone = self.cv.st != CvSt::Off && zr > 0.0 && dist2v(self.cv.h, zc) > zr - 2.0;
        let f_ok = self.cv.st != CvSt::Off && dist(self.cv.f, self.cv.h) > 0.5 && self.mem.tracks.iter().find(|x| x.id == tid).map_or(false, |tr| world.ray(up(self.cv.f, me.stats.muzzle_height), up(tr.pos_at(t), h * 0.5)).is_none());
        let due = t - self.cv.plan_t >= p.pk_replan && (self.cv.st == CvSt::Off || (self.cv.st == CvSt::Wait && !f_ok));
        if (due || h_exposed || h_zone) && self.cv.st != CvSt::Out && t - self.cv.fail_t > 0.3 {
            self.cv.plan_t = t;
            let mut got = self.cv_plan(obs, world, nav, hs, tid);
            if got.is_none() {
                let mut ids: Vec<(f64, i64)> = fresh.iter().filter(|o| o.id != tid).map(|o| (o.hp, o.id)).collect();
                ids.sort_by(|a, b| a.0.total_cmp(&b.0));
                for (_, id) in ids.into_iter().take(2) {
                    if self.spent_ms() > p.pk_ms {
                        break;
                    }
                    if let Some(x) = self.cv_plan(obs, world, nav, hs, id) {
                        self.cv.tid = id;
                        got = Some(x);
                        break;
                    }
                }
            }
            match got {
                Some((hq, fq)) => {
                    let moved = dist(hq, self.cv.h) > 1.0;
                    self.cv.h = hq;
                    self.cv.f = fq;
                    if self.cv.st == CvSt::Off || (moved && self.cv.st == CvSt::Wait) {
                        self.cv.st = CvSt::Go;
                        self.cv.st_t = t;
                    }
                }
                None => {
                    self.cv.fail_t = t;
                    if self.cv.st == CvSt::Off || h_exposed || h_zone {
                        self.cv.nofit_s += 0.1;
                        self.cv.st = CvSt::Off;
                        return false;
                    }
                }
            }
        }
        if self.cv.st == CvSt::Off {
            return false;
        }
        let tid = self.cv.tid;
        let Some(tr) = self.mem.tracks.iter().find(|x| x.id == tid).cloned() else { return false };
        let tp = tr.pos_at(t);
        let at = self.aim_target(&tr);
        let c = up(tp, at.height * 0.5);
        let muzzle = up(pos, me.stats.muzzle_height);
        let line = world.ray(muzzle, c).is_none();
        let direct = dir_to_aim(sub(c, muzzle));
        let ls = me.weapons.iter().position(|w| w.as_ref().map_or(false, |w| w.kind == WeaponKind::Laser));
        let gs = me.weapons.iter().position(|w| w.as_ref().map_or(false, |w| w.kind == WeaponKind::Gun));
        let pred = slew(me.aim, direct, me.stats.turn_rate * 0.05, me.stats.pitch_rate * 0.05);
        let dd = len(sub(c, muzzle)).max(1.0);
        let aligned = adiff(pred[0], direct[0]).abs() <= (at.radius * 0.8).atan2(dd) && (pred[1] - direct[1]).abs() <= (at.height * 0.4).atan2(dd);
        let mut aim = direct;
        let mut gun_ok = false;
        if let Some(g) = gs.and_then(|i| me.weapons[i].as_ref()) {
            let sp = if g.stats.speed > 1.0 { g.stats.speed } else { self.cfg.weapons.gun.speed };
            if let Some((pt, _)) = lead(sub(c, muzzle), tr.vel, [0.0; 3], sp, 0.05, 0.0, 0.0) {
                let ga = dir_to_aim(pt);
                if ga[0].is_finite() && ga[1].is_finite() {
                    let gp = slew(me.aim, ga, me.stats.turn_rate * 0.05, me.stats.pitch_rate * 0.05);
                    gun_ok = adiff(gp[0], ga[0]).abs() <= (at.radius * 1.2).atan2(dd) && g.ammo > 0.0 && g.reload <= 0.0;
                    if ls.map_or(true, |i| me.weapons[i].as_ref().map_or(true, |w| w.charge <= 0.0 && w.cooldown > 0.3)) {
                        aim = ga;
                    }
                }
            }
        }
        let lw = ls.and_then(|i| me.weapons[i].clone());
        let full = lw.as_ref().map_or(0.75, |w| w.stats.charge.max(0.05));
        let charge = lw.as_ref().map_or(0.0, |w| w.charge);
        let charging = charge > 0.0;
        let cool = lw.as_ref().map_or(9.0, |w| w.cooldown);
        let mut fire = [false, false];
        let to = |a: V3, b: V3| -> (V2, f64) {
            let dx = b[0] - a[0];
            let dy = b[1] - a[1];
            let l = dx.hypot(dy);
            if l < 1e-6 {
                ([0.0, 0.0], 0.0)
            } else {
                ([dx / l, dy / l], l)
            }
        };
        let hf = frac(me.hp, me.max_hp);
        if self.cv.regen && (hf >= p.pk_regen_to || h_exposed) {
            self.cv.regen = false;
        }
        let exp_s = if exposed { t - self.cv.exp_t0 } else { 0.0 };
        let boost_ok = me.energy > 12.0;
        mv.jump = false;
        mv.boost = false;
        let (dirh, dh) = to(pos, self.cv.h);
        match self.cv.st {
            CvSt::Go => {
                mv.dir = if dh > 0.5 { dirh } else { [0.0, 0.0] };
                mv.boost = (exposed || dh > 8.0) && boost_ok && !charging;
                if let Some(i) = ls {
                    if charging {
                        if line && aligned && charge >= full - 0.05 {
                            fire[i] = false;
                            self.cv.shot_t = t;
                            self.cv.lz_shots += 1;
                            self.cv.lz_rel_t = t;
                        } else {
                            fire[i] = !exposed || charge >= full - 0.2;
                        }
                    } else {
                        fire[i] = !exposed && dh < 3.0 && cool <= 0.05 && !self.cv.regen;
                    }
                }
                if dh < 0.9 {
                    self.cv.st = CvSt::Wait;
                    self.cv.st_t = t;
                    self.cv.wait_t = t;
                }
                if exposed && line && gun_ok {
                    if let Some(g) = gs {
                        fire[g] = true;
                    }
                }
            }
            CvSt::Wait => {
                mv.dir = if dh > 0.4 { dirh } else { [0.0, 0.0] };
                if hf < p.pk_regen_hp && !h_exposed {
                    self.cv.regen = true;
                }
                if let Some(g) = gs.and_then(|i| me.weapons[i].as_ref()) {
                    if g.ammo <= 0.0 && g.reload <= 0.0 {
                        fc.reload = true;
                    }
                }
                let ready = if self.cv.regen {
                    false
                } else if let Some(i) = ls {
                    if charging {
                        fire[i] = true;
                        charge >= full - 0.1
                    } else {
                        fire[i] = cool <= 0.05;
                        false
                    }
                } else {
                    t - self.cv.wait_t >= p.pk_gun_wait && gs.and_then(|i| me.weapons[i].as_ref()).map_or(false, |g| g.ammo > 0.0 && g.reload <= 0.0)
                };
                if ready && dist(self.cv.f, self.cv.h) > 0.5 {
                    self.cv.st = CvSt::Out;
                    self.cv.st_t = t;
                }
            }
            CvSt::Out => {
                let (dirf, df) = to(pos, self.cv.f);
                mv.dir = if df > 0.3 { dirf } else { [0.0, 0.0] };
                let mut back = false;
                if let Some(i) = ls {
                    if charging {
                        if line && aligned {
                            fire[i] = false;
                            self.cv.shot_t = t;
                            self.cv.lz_shots += 1;
                            self.cv.lz_rel_t = t;
                            back = true;
                        } else {
                            fire[i] = true;
                        }
                    } else if lw.is_some() && cool > 0.05 && t - self.cv.st_t > 0.15 {
                        back = true;
                    }
                }
                if line && gun_ok {
                    if let Some(g) = gs {
                        fire[g] = true;
                        if ls.is_none() || !charging {
                            self.cv.shot_t = t;
                        }
                    }
                }
                let ret = (dist(pos, self.cv.h) * 0.6 / me.stats.boost_speed.max(1.0)).max(0.1);
                if exposed && exp_s + ret + 0.1 >= p.pk_max_exp {
                    back = true;
                }
                if !exposed && t - self.cv.st_t > p.pk_max_exp + 0.6 {
                    back = true;
                    self.cv.plan_t = -1e9;
                }
                if back {
                    self.cv.st = CvSt::Back;
                    self.cv.st_t = t;
                }
            }
            CvSt::Back => {
                mv.dir = if dh > 0.4 { dirh } else { [0.0, 0.0] };
                mv.boost = dh > 1.0 && boost_ok;
                if let Some(i) = ls {
                    fire[i] = false;
                }
                if exposed && line && gun_ok {
                    if let Some(g) = gs {
                        fire[g] = true;
                    }
                }
                if dh < 0.9 || t - self.cv.st_t > 1.5 {
                    self.cv.st = CvSt::Wait;
                    self.cv.st_t = t;
                    self.cv.wait_t = t;
                    self.cv.plan_t = self.cv.plan_t.min(t - p.pk_replan + 0.2);
                }
            }
            CvSt::Off => {}
        }
        if let Some(i) = ls {
            if self.cv.regen && !charging {
                fire[i] = false;
            }
        }
        if self.cv.stats && std::env::var("PK_DBG").is_ok() {
            eprintln!("PKD t={:.1} st={:?} pos={:.1?} h={:.1?} f={:.1?} dh={:.1} exp={} hexp={} tid={} line={} ch={:.2} cool={:.2} v={:.1} hp={:.0}", t, self.cv.st, pos, self.cv.h, self.cv.f, dh, exposed, h_exposed, tid, line, charge, cool, me.vel[0].hypot(me.vel[1]), me.hp);
        }
        fc.aim = aim;
        fc.fire = fire;
        fc.charging = ls.map_or(false, |i| fire[i]);
        true
    }
}
