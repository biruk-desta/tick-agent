package bot










type peekPlan struct {
	t    float64
	tgt  int
	roof int
	duck int
	fire int
	ok   bool
}



func (b *Bot) peekPlanFor(tgt *threat, ths []threat, roofID int) bool {
	if b.t-b.peek.t < 0.4 && b.peek.tgt == tgt.tr.ID && b.peek.roof == roofID {
		return b.peek.ok
	}
	prevFire := -1
	if b.peek.ok && b.peek.tgt == tgt.tr.ID && b.peek.roof == roofID {
		prevFire = b.peek.fire
	}
	b.peek = peekPlan{t: b.t, tgt: tgt.tr.ID, roof: roofID, duck: -1, fire: -1}
	tr := tgt.tr
	sc := tr.scale(b.sizePerCube)
	tx, ty, tz := tr.Pos[0], tr.Pos[1], tr.Pos[2]+4.5*sc
	duck := -1
	if roofID >= 0 {
		duck = b.roofCover(roofID, ths)
	} else {
		duck = b.findCover(ths, b.P.PeekCover)
	}
	if duck < 0 {
		return false
	}
	dx, dy := b.Nav.Pos(duck)
	best, bd := -1, 1e18
	consider := func(k int, z float64) {
		x, y := b.Nav.Pos(k)
		d := hyp(x-dx, y-dy)
		if d < 1.5 || d > b.P.PeekReach {
			return
		}
		if k == prevFire {
			d -= 2.5
		}
		if d >= bd {
			return
		}
		if !b.W.Visible(x, y, z+b.muzzleH, tx, ty, tz) {
			return
		}
		best, bd = k, d
	}
	if roofID >= 0 {
		roofs, roofOf := b.Nav.Roofs()
		dist := b.Nav.RoofDist()
		r := &roofs[roofID]
		for _, c := range r.Cells {
			k := int(c)
			if int(roofOf[k]) != roofID || dist[k] < 2 {
				continue
			}
			consider(k, r.Z)
		}
	} else {
		ci, cj := duck%b.Nav.NX, duck/b.Nav.NX
		rad := int(b.P.PeekReach/b.Nav.Cell) + 1
		for dj := -rad; dj <= rad; dj++ {
			for di := -rad; di <= rad; di++ {
				i, j := ci+di, cj+dj
				if i < 0 || j < 0 || i >= b.Nav.NX || j >= b.Nav.NY {
					continue
				}
				k := j*b.Nav.NX + i
				if !b.Nav.Walkable(k, b.radius+0.3, b.height) || !b.sameComp(k) {
					continue
				}
				x, y := b.Nav.Pos(k)
				if !b.Nav.WalkLine(dx, dy, x, y, b.radius+0.15, b.height) {
					continue
				}
				consider(k, float64(b.Nav.Z[k]))
			}
		}
	}
	if best < 0 {
		return false
	}
	b.peek.duck, b.peek.fire, b.peek.ok = duck, best, true
	return true
}



func (b *Bot) peekStep(ths []threat, li int, hpFrac float64) (cell int, charge bool) {
	sl := &b.slots[li]
	full := stat(sl.stats, "charge", 0.75)
	fx, fy := b.Nav.Pos(b.peek.fire)
	kx, ky := b.Nav.Pos(b.peek.duck)

	travel := hyp(fx-kx, fy-ky)/(b.walk*0.5) + 0.15
	atDuck := hyp(b.pos[0]-kx, b.pos[1]-ky) < 4
	atFire := hyp(b.pos[0]-fx, b.pos[1]-fy) < 4

	threatened := false
	for i := range ths {
		tr := ths[i].tr
		if tr.Laser && tr.Charging && tr.LOS && b.t-tr.AimAtMeT < 0.3 {
			threatened = true
		}
	}
	cell = b.peek.duck
	switch {
	case hpFrac < 0.2 || threatened:

	case sl.charge > 0 && sl.charge >= full-travel:
		cell = b.peek.fire
	case sl.charge <= 0 && sl.cooldown <= 0.1 && (atDuck || atFire):
		charge = true
	}
	return cell, charge
}
