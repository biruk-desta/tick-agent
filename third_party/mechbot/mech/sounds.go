package mech

import "math"

const soundMaxAge = 0.35

type soundCue struct {
	kind    string
	dist    string
	bearing float64
	until   float64
}

func soundPriority(kind string) int {
	switch kind {
	case "laser_charge":
		return 3
	case "gun", "mortar", "laser", "lightning":
		return 2
	case "step", "boost", "jet", "reload":
		return 1
	}
	return 0
}

func soundDistanceRank(dist string) int {
	switch dist {
	case "near":
		return 2
	case "mid":
		return 1
	}
	return 0
}

func soundDistanceMatches(dist string, actual float64) bool {
	switch dist {
	case "near":
		return actual < 70
	case "mid":
		return actual >= 50 && actual < 170
	case "far":
		return actual >= 150
	}
	return true
}

func (cue soundCue) explainedBy(o *Obs) bool {
	weapon := soundPriority(cue.kind) == 2
	for _, m := range o.Mechs {
		if m.Kind != "mech" {
			continue
		}
		if cue.kind == "laser_charge" && !m.Charging {
			continue
		}
		if weapon && len(m.Weapons) > 0 && !holds(m.Weapons, cue.kind) {
			continue
		}
		dx, dy := m.Pos[0]-o.Self.Pos[0], m.Pos[1]-o.Self.Pos[1]
		if math.Abs(angDiff(cue.bearing, math.Atan2(dy, dx))) <= math.Pi/9 && soundDistanceMatches(cue.dist, hyp(dx, dy)) {
			return true
		}
	}
	return false
}

func (b *Brain) unseenCue(o *Obs, seen []*Track) soundCue {
	cue := b.heard
	if cue.kind != "" && (o.T >= cue.until || cue.explainedBy(o)) {
		cue = soundCue{}
	}
	best := 0.0
	for _, s := range o.Sounds {
		priority := soundPriority(s.Kind)
		if priority == 0 || s.Age > soundMaxAge || priority < soundPriority(cue.kind) {
			continue
		}
		score := float64(3*priority+soundDistanceRank(s.Dist)) - s.Age
		if score <= best {
			continue
		}
		candidate := soundCue{kind: s.Kind, bearing: s.Bearing, dist: s.Dist, until: o.T - s.Age + 0.8}
		if !candidate.explainedBy(o) {
			cue, best = candidate, score
		}
	}
	b.heard = cue
	if cue.kind == "laser_charge" {
		return cue
	}
	var charging *Track
	for _, t := range seen {
		if age := o.T - t.Seen; age <= 0 || age > 0.5 || !t.Charging {
			continue
		}
		toMe := math.Atan2(o.Self.Pos[1]-t.Pos[1], o.Self.Pos[0]-t.Pos[0])
		if math.Abs(angDiff(t.Aim[0], toMe)) > 0.15 {
			continue
		}
		if charging == nil || t.Seen > charging.Seen || (t.Seen == charging.Seen && t.ID < charging.ID) {
			charging = t
		}
	}
	if charging != nil {
		return soundCue{kind: "laser_charge", bearing: math.Atan2(charging.Pos[1]-o.Self.Pos[1], charging.Pos[0]-o.Self.Pos[0])}
	}
	return cue
}

func (b *Brain) soundSidestep(me *Self, bearing float64) (float64, float64) {
	x, y := me.Pos[0], me.Pos[1]
	dx, dy := math.Sin(bearing), -math.Cos(bearing)
	if dx*me.Vel[0]+dy*me.Vel[1] < 0 {
		dx, dy = -dx, -dy
	}
	for range 2 {
		nx, ny := x+4*dx, y+4*dy
		if b.W.InBounds(nx, ny) && b.W.LineWalkable(x, y, nx, ny) && b.W.Free(nx, ny) {
			return dx, dy
		}
		dx, dy = -dx, -dy
	}
	return 0, 0
}
