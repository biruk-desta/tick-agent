package mech

import (
	"math"
	"os"
)

type optSet struct {
	A, B, C, D, E, F, G bool
	H, I, J, K, L, M    bool
}

const (
	optLeadK = 0.8
	optLateT = 265.0
)

func readOpts() optSet {
	on := func(name string) bool { return os.Getenv(name) == "1" }
	return optSet{
		A: on("MECHBOT_OPT_A"), B: on("MECHBOT_OPT_B"), C: on("MECHBOT_OPT_C"), D: on("MECHBOT_OPT_D"),
		E: on("MECHBOT_OPT_E"), F: on("MECHBOT_OPT_F"), G: on("MECHBOT_OPT_G"),
		H: on("MECHBOT_OPT_H"), I: on("MECHBOT_OPT_I"), J: on("MECHBOT_OPT_J"), K: on("MECHBOT_OPT_K"),
		L: on("MECHBOT_OPT_L"), M: on("MECHBOT_OPT_M"),
	}
}

func (b *Brain) squad(base Params) Params {
	p := squadParams(base)
	if b.opt.A {
		p.FightBoost, p.DodgeBoost, p.ThreatBoost, p.SpeedUp = 40, 25, 30, true
	}
	if b.opt.B {
		p.Backstab = 50
	}
	return p
}

func (b *Brain) leadScaled(muzzle, tp, tv Vec3, speed float64, grounded bool, k float64) (float64, float64) {
	if speed <= 0 {
		speed = 252
	}
	t := 0.0
	var px, py, pz float64
	for it := 0; it < 4; it++ {
		tt := k * (lat + t)
		px, py, pz = tp[0]+tv[0]*tt, tp[1]+tv[1]*tt, tp[2]
		if !grounded {
			pz += tv[2] * tt * 0.5
		}
		d := math.Sqrt((px-muzzle[0])*(px-muzzle[0]) + (py-muzzle[1])*(py-muzzle[1]) + (pz-muzzle[2])*(pz-muzzle[2]))
		t = math.Max(0, d-3) / speed
	}
	return math.Atan2(py-muzzle[1], px-muzzle[0]), math.Atan2(pz-muzzle[2], hyp(px-muzzle[0], py-muzzle[1]))
}
