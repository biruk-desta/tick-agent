package bot

import (
	"math"
	"sort"
)


type stance struct {
	name        string
	engageRatio float64
	disengage   float64
	hunt        bool
	stealth     bool
	avoid       bool
	lootRadius  float64
	wantCubes   int
}



func (b *Bot) brawlStance(name string) stance {
	return stance{name: name, engageRatio: b.P.BrawlEngage, disengage: b.P.BrawlDisengage, hunt: b.P.BrawlHunt,
		avoid: b.P.AvoidAdv > 0, lootRadius: b.P.BrawlLootRadius, wantCubes: b.P.BrawlWantCubes}
}



func (b *Bot) realModel() bool {
	if b.P.HitModel < 1 {
		return false
	}
	return !b.P.PracticeAware || b.ffa || b.openPhase()
}





func (b *Bot) openPhase() bool {
	return b.t < b.P.OpenSecs || (b.P.CreditOpenS > 0 && b.t-b.creditAbsorbT < b.P.CreditOpenS)
}


func (b *Bot) belief() stance {



	total := int(stat(b.C.Match, "mechs", 16))
	dead := total - b.o.Alive
	if dead > b.deadSeen {
		n := dead - b.deadSeen
		b.deadSeen = dead
		if b.kills > b.killsSeen {
			n -= b.kills - b.killsSeen
			b.killsSeen = b.kills
		} else if b.t-b.creditT < 6 {



			mine := true
			if b.P.CreditFix {
				if tr := b.tracks[b.creditID]; tr != nil && tr.Listed && tr.HP > 0 {
					mine = false
				}
			}
			if mine {
				n--
				b.creditAbsorbT = b.t
			}
		}
		if n > 0 {
			b.unexplained += n
		}
		if (b.unexplained >= 1 && b.t < 35) || (b.unexplained >= 2 && b.t < 110) || b.unexplained >= 3 {
			b.ffa = true
		}
	}
	alive := b.o.Alive
	if b.P.ForceFFA {
		b.ffa = true
	}
	if b.P.BeamFFA && b.ffaBeams >= 2 {
		b.ffa = true
	}




	if b.P.SlotRule && b.H.Slot != 0 {
		b.ffa = true
	}
	switch {
	case alive <= 2:

		return stance{name: "duel", engageRatio: 0.0, disengage: 0.45, hunt: true, lootRadius: 150, wantCubes: 40}
	case b.ffa && b.P.PracticeAware:
		if b.P.Brawl {
			return b.brawlStance("ffa")
		}
		return stance{name: "ffa", engageRatio: b.P.FFAEngage, disengage: b.P.FFADisengage, hunt: false, stealth: true, lootRadius: b.P.FFALootRadius, wantCubes: b.P.FFAWantCubes}
	case b.openPhase() && b.P.PracticeAware:
		if b.P.Brawl {
			return b.brawlStance("open")
		}

		return stance{name: "open", engageRatio: 1.5, disengage: 0.9, hunt: false, stealth: true, lootRadius: 110, wantCubes: b.P.WantCubes}
	case b.P.CautiousT > 0 && b.P.PracticeAware && (b.t >= b.P.CautiousT || (b.o.Zone.NextRadius > 0 && b.o.Zone.NextRadius <= 72 && b.t >= 180)):
		return b.brawlStance("late")
	}
	return stance{name: "squad", engageRatio: b.P.EngageRatio, disengage: b.P.DisengageRat, hunt: b.P.Hunt, lootRadius: b.P.LootRadius, wantCubes: b.P.WantCubes}
}

type hideCand struct {
	cell  int
	score float64
}


func (b *Bot) chooseHide(zi zoneInfo) int {
	z := &b.o.Zone
	exp := b.Nav.Exposure()
	comp := b.Nav.Components()
	myComp := int32(0)
	if c := b.Nav.Nearest(b.pos[0], b.pos[1], 2.9, 9, 6); c >= 0 {
		myComp = comp[c]
	}


	margin := math.Min(14, z.NextRadius*0.25)
	var cands []hideCand
	for j := 0; j < exp.NY; j++ {
		for i := 0; i < exp.NX; i++ {
			e := exp.V[j*exp.NX+i]
			if e > 1.5 {
				continue
			}
			k := exp.Cell(i, j)
			if myComp != 0 && comp[k] != myComp {
				continue
			}
			x, y := b.Nav.Pos(k)
			dn := hyp(x-z.NextCenter[0], y-z.NextCenter[1])
			if dn > z.NextRadius-margin {
				continue
			}
			if !b.Nav.Walkable(k, b.radius+0.4, b.height) {
				continue
			}
			d := hyp(x-b.pos[0], y-b.pos[1])
			if d > 320 {
				continue
			}

			s := float64(e)*100 + d*b.hideDistW()

			if z.NextRadius > 60 && dn < z.NextRadius*0.35 {
				s += 10
			}

			if b.ffa && b.P.EdgeBias > 0 && z.NextRadius > 60 {
				s -= b.P.EdgeBias * 30 * dn / z.NextRadius
				if b.P.EdgeBand > 0 && dn < z.NextRadius*b.P.EdgeBand {
					s += 60
				}
			}

			if !b.ffa && b.P.PracticeRim > 0 && z.NextRadius >= 180 {
				wantR := z.NextRadius * 0.88
				s += math.Abs(dn-wantR) * b.P.PracticeRim
			}

			s += float64(b.Nav.Clear[k]) * 0.8
			if k == b.holdCell {
				s -= 9
			}
			cands = append(cands, hideCand{k, s})
		}
	}
	if len(cands) == 0 {
		return -1
	}
	sort.Slice(cands, func(a, c int) bool { return cands[a].score < cands[c].score })
	if len(cands) > 60 {
		cands = cands[:60]
	}

	best, bs := -1, 1e18
	for _, c := range cands {
		x, y := b.Nav.Pos(c.cell)
		gz := float64(b.Nav.Z[c.cell])
		s := c.score
		for _, tr := range b.tracks {
			if tr.NPC || b.t-tr.LastSeen > 25 {
				continue
			}
			d := hyp(tr.Pos[0]-x, tr.Pos[1]-y)
			if d < 90 {
				s += (90 - d) * 0.35
			}
			if d < 260 && b.t-tr.LastSeen < 8 {
				sc := tr.scale(b.sizePerCube)
				if b.W.Visible(tr.Pos[0], tr.Pos[1], tr.Pos[2]+8*sc, x, y, gz+b.height*0.6) {
					s += 30
				}
			}
		}
		for i := range b.o.Drops {
			if hyp(b.o.Drops[i].Pos[0]-x, b.o.Drops[i].Pos[1]-y) < 70 {
				s += 15
			}
		}
		if s < bs {
			best, bs = c.cell, s
		}
	}
	return best
}

func (b *Bot) hideDistW() float64 {
	if b.st.stealth {
		return 0.16
	}
	return 0.07
}


func (b *Bot) seenBy(ths []threat, maxD float64) []*threat {
	var out []*threat
	for i := range ths {
		if ths[i].tr.LOS && ths[i].tr.Listed && ths[i].d < maxD {
			out = append(out, &ths[i])
		}
	}
	return out
}
