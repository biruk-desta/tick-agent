package mech

import (
	"iter"
	"maps"
	"math"
	"os"
	"slices"
)

type decisionSwitches struct {
	ordered, strafeBoost, dodgeBoost, threatBoost bool
	chargeBoost, mobility, rear, sounds          bool
}

var startupSwitches = readSwitches(os.Getenv)

func readSwitches(getenv func(string) string) decisionSwitches {
	return decisionSwitches{
		ordered:     getenv("MB_D") == "1",
		strafeBoost: getenv("MB_1") == "1",
		dodgeBoost:  getenv("MB_2") == "1",
		threatBoost: getenv("MB_3") == "1",
		chargeBoost: getenv("MB_4") == "1",
		mobility:    getenv("MB_5") == "1",
		rear:        getenv("MB_6") == "1",
		sounds:      getenv("MB_7") == "1",
	}
}

func decisionValues[V any](values map[int]V, ordered bool) iter.Seq[V] {
	if !ordered {
		return maps.Values(values)
	}
	ids := slices.Sorted(maps.Keys(values))
	return func(yield func(V) bool) {
		for _, id := range ids {
			if !yield(values[id]) {
				return
			}
		}
	}
}

func mobilityRank(id string) int {
	switch id {
	case "plating":
		return 0
	case "armor":
		return 1
	case "servos":
		return 2
	case "jets":
		return 3
	case "reactor":
		return 4
	}
	return -1
}

func boostReady(wasReady bool, energy float64) bool {
	return energy >= 60 || (wasReady && energy > 30)
}

type combatMotion struct {
	charging, strafing, dodging, threatened, underFire, boostReady bool
}

func (s decisionSwitches) combatBoost(energy float64, m combatMotion) bool {
	if s.dodgeBoost && m.dodging && energy > 25 {
		return true
	}
	if s.threatBoost && m.threatened {
		return m.boostReady && (!m.charging || (s.chargeBoost && m.underFire))
	}
	if m.charging {
		return s.chargeBoost && m.underFire && energy > 30
	}
	return s.strafeBoost && m.strafing && energy > 40
}

func chargingLaser(me *Self, fire [2]bool) bool {
	for i, w := range me.Weapons {
		if i < len(fire) && w != nil && w.Kind == "laser" && (w.Charge > 0 || (fire[i] && w.Cooldown <= 0.05)) {
			return true
		}
	}
	return false
}

func strafing(me *Self, target *Track, mx, my float64) bool {
	dx, dy := target.Pos[0]-me.Pos[0], target.Pos[1]-me.Pos[1]
	return math.Abs(mx*dy-my*dx) > 0.5*hyp(mx, my)*hyp(dx, dy)
}

func (b *Brain) hasBoostReserve(me *Self, act *Action, slot int, light *WeaponState) bool {
	if light == nil {
		return true
	}
	interval := 0.1
	if b.Cfg.Match.TickHz > 0 && b.Cfg.Match.DecideEvery > 0 {
		interval = float64(b.Cfg.Match.DecideEvery) / b.Cfg.Match.TickHz
	}
	shots := 3.0
	if slot >= 0 && slot < len(act.Fire) && act.Fire[slot] && light.Cooldown < interval {
		shots++
	}
	return me.Energy-me.Stats.BoostDrain*interval >= shots*light.Stats.Energy
}

func rearMultiplier(st MechStats, aim, bearing float64) float64 {
	front := st.FrontArcDeg
	if front <= 0 {
		front = 180
	}
	if math.Abs(angDiff(bearing, aim)) <= front*math.Pi/360 {
		return 1
	}
	if st.RearMult <= 0 {
		return 1.5
	}
	return st.RearMult
}
