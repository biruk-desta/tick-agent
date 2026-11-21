

package bot

import (
	"fmt"
	"math"
	"math/rand"
	"os"
	"strings"

	"apexbot/internal/proto"
	"apexbot/internal/world"
)


type Params struct {
	Name string

	EngageRatio   float64
	DisengageRat  float64
	RetreatHP     float64
	ReturnHP      float64
	LeadDamp      float64
	GunMaxRange   float64
	StrafeMin     float64
	StrafeMax     float64
	LootRadius    float64
	WantCubes     int
	DropGreed     float64
	Hunt          bool
	PracticeAware bool


	FFAEngage     float64
	FFADisengage  float64
	FFALootRadius float64
	FFAWantCubes  int
	FFAReturnFire float64
	Salt          int
	ForceFFA      bool
	SlotRule      bool
	CloseDisengage float64
	DuelDisengage  float64

	UseRoofs      bool
	RoofInSquad   bool
	RoofMaxClimb  float64
	RoofMinHeight float64
	RoofMinZone   float64
	ArmRadius     float64
	OpenSecs      float64
	CreditOpenS   float64
	DropRadius    float64
	LeaveTTD      float64
	PatientSecs   float64
	PatientCubes  int
	PatientRange  float64

	UseHideMap  bool
	HideSeenW   float64
	HideHitW    float64
	HideDistW   float64
	HideClimbW  float64
	HideStick   float64
	StealthFightRange float64
	QuietHoldS        float64
	LaserValue        float64
	LightningValue    float64
	ArmSwapMin        float64
	HitModel          int
	PlanV2            bool
	KiteNeedsLaser    bool
	ExchangeW         float64

	Brawl           bool
	BrawlEngage     float64
	BrawlDisengage  float64
	BrawlHunt       bool
	BrawlLootRadius float64
	BrawlWantCubes  int
	AvoidAdv        float64
	AvoidRange      float64
	AvoidCover      float64
	CoverFirst      bool
	CoverMinRange   float64
	EdgeHold        float64
	RunOnRange      float64
	RunOnGain       float64
	CoverMargin     float64
	ShySecs         float64
	ShyRange        float64
	ShyLaser        float64
	ShyMem          float64
	ShyBoost        float64
	ShyLootRadius   float64
	ShyExposure     float64
	RetreatRunMax   float64
	RetreatRunLaser float64
	LootHiddenBias  float64
	CoverEdgeAdv    float64
	HuntLaserEdge   bool
	Peek            bool
	PeekCover       float64
	PeekReach       float64
	PeekMinRange    float64
	OverlandEarly   float64
	RoofCoverHold   float64
	RoofStandCheck  bool
	DropStick       bool
	ClimbClearRange float64
	RoofCenterW     float64
	RoofLeaveQuiet  float64
	ZoneSlack       float64
	BrawlRoofs      bool
	BrawlRoofCubes  int
	BrawlRoofAfter  float64
	Jink            float64
	LeadPersist     bool
	LeadCum         bool
	LeadCumMin      float64
	LaserPreempt    bool
	AvoidCoverLaser float64
	HoldHideMap     bool
	LaserAimRange   float64
	PathFix         bool
	CreditFix       bool
	LootBoost       float64
	NoMortar        bool
	ProvokeRule     bool
	PlinkMaxDPS     float64
	HuntRange       float64
	HuntRangeLaser  float64
	KiteMin       float64
	KiteMax       float64
	RoofFirstSecs float64
	RoofFirstDist float64


	AllNoMortar      bool
	CookoffAware     bool
	AntiLightningW   float64
	AntiLightningPad float64
	LaserDodgeV2     bool
	LaserBeamW       float64
	SquadLaserCover  bool
	SmartFireV2      bool
	LaserEarlyRel    bool
	RearBonus        float64
	CookoffBonus     float64
	CautiousT        float64
	BeamFFA          bool
	FinalHold        bool
	SquadPeek        bool
	NanoBoost        float64
	RegenHoldHP      float64
	ThreatFocus      bool
	LightKiteBoost   bool


	CoverReload      bool
	UpV2             bool
	CubeSmart        bool
	LaserMechOnly    bool
	RearAvoidW       float64
	LaserCDTrack     bool
	KillFocus        float64
	Seek             float64
	SeekRange        float64
	SeekHP           float64
	SeekWeak         float64
	FinishHP         float64
	DropRun          float64
	EdgeBias         float64
	EdgeBand         float64
	PracticeRim      float64
	RetreatPest      bool
}

func DefaultParams() Params {
	return Params{
		Name:          "apex-go",
		EngageRatio:   1.25,
		DisengageRat:  0.75,
		RetreatHP:     0.45,
		ReturnHP:      0.85,
		LeadDamp:      0.65,
		GunMaxRange:   224,
		StrafeMin:     0.35,
		StrafeMax:     1.1,
		LootRadius:    220,
		WantCubes:     15,
		DropGreed:     0.5,
		Hunt:          true,
		PracticeAware: true,
		Salt:          8,

		FFAEngage:     1.8,
		FFADisengage:  0.95,
		FFALootRadius: 140,
		FFAWantCubes:  10,
		FFAReturnFire: 230,
		CloseDisengage: 0.8,
		DuelDisengage:  0.5,
		UseRoofs:       true,
		RoofMaxClimb:   40,
		RoofMinHeight:  12,
		RoofMinZone:    60,
		ArmRadius:      110,
		OpenSecs:       24,
		CreditOpenS:    25,
		DropRadius:     300,
		LeaveTTD:       10,
		UseHideMap:     false,
		HideSeenW:      0.6,
		HideHitW:       0.9,
		HideDistW:      0.16,
		HideClimbW:     0.5,
		HideStick:      12,
		StealthFightRange: 140,
		QuietHoldS:        3,
		LaserValue:        6.0,
		LightningValue:    2.6,
		ArmSwapMin:        1.0,
		HitModel:          1,
		PlanV2:            true,
		KiteNeedsLaser:    true,
		Brawl:             true,
		AvoidAdv:          1.25,
		BrawlEngage:       1.3,
		BrawlDisengage:    0.75,
		BrawlHunt:         true,
		BrawlLootRadius:   220,
		BrawlWantCubes:    10,
		AvoidRange:        85,
		AvoidCover:        55,
		ZoneSlack:         10,
		CoverFirst:        true,
		NoMortar:          true,
		EdgeHold:          2.5,
		RunOnRange:        80,
		RunOnGain:         18,
		CoverMargin:       8,





		ShyRange:          220,
		ShyLaser:          60,
		ShyMem:            6,



		RetreatRunLaser:   90,
		HuntLaserEdge:     true,
		LootHiddenBias:    0.5,
		CoverMinRange:     40,
		CoverEdgeAdv:      3.0,
		PeekCover:         25,
		PeekReach:         9,
		PeekMinRange:      45,
		RoofCoverHold:     6,
		RoofStandCheck:    true,
		DropStick:         true,
		RoofLeaveQuiet:    25,
		ClimbClearRange:   150,
		BrawlRoofs:        true,
		LaserPreempt:      true,
		LaserAimRange:     285,
		AvoidCoverLaser:   90,
		BrawlRoofCubes:    6,
		BrawlRoofAfter:    60,
		LeadPersist:       true,
		LeadCum:           true,
		LeadCumMin:        8,
		PathFix:           true,
		CreditFix:         true,
		LootBoost:         30,
		ProvokeRule:       true,
		PlinkMaxDPS:       60,
		HuntRange:         130,
		HuntRangeLaser:    130,
		KiteMin:        130,
		KiteMax:        190,
		PatientCubes:   10,
		PatientRange:   70,

		AntiLightningW:   180,
		AntiLightningPad: 12,
		SmartFireV2:      true,
		LaserEarlyRel:    true,
		RearBonus:        0.25,
		CookoffBonus:     0.30,
		CautiousT:        265,
		BeamFFA:          true,
		FinalHold:        true,

		LaserCDTrack: true,
		RearAvoidW:   35,
		CoverReload:  true,
		RetreatPest:  true,
		PracticeRim:  0.6,
	}
}


type Track struct {
	ID       int
	NPC      bool
	Pos, Vel [3]float64
	Aim      [2]float64
	HP       float64
	MaxHP    float64
	Cubes    int
	Laser    bool
	Mortar   bool
	Light    bool
	Gun      bool
	Charging bool
	LastSeen float64
	Listed   bool
	LOS      bool
	LOST     float64
	HurtMeT  float64
	HurtMe   float64
	IHurtT   float64
	IHurt    float64
	AimAtMeT float64
	SeenT0   float64
	PhantomT float64
	WasListed bool
	ViewT    float64
	EngT     float64
	LaserFiredT float64


	hist            [trkHist]trkSample
	hn, hi          int
	leadN           float64
	missNone        float64
	missLead        float64
}

const trkHist = 40

type trkSample struct {
	t, x, y, vx, vy float64
	facing          bool
}

func (t *Track) scale(sizePerCube float64) float64 { return 1 + sizePerCube*float64(t.Cubes) }

type modeRec struct {
	t    float64
	mode string
}

type hitRec struct {
	t   float64
	amt float64
}

type dmgRec struct {
	t      float64
	by     int
	weapon string
	amt    float64
	d      float64
	seen   bool
}

type Item struct {
	ID       int
	Pos      [3]float64
	HP       float64
	Kind     string
	LastSeen float64
	Ground   bool
	Cell     int
}

type slot struct {
	ok       bool
	kind     string
	cooldown float64
	ammo     float64
	reload   float64
	charge   float64
	stats    map[string]float64
}

type Bot struct {
	P   Params
	H   *proto.Hello
	C   *proto.Config
	W   *world.World
	Nav *world.Nav
	rng *rand.Rand


	dt          float64
	decide      float64
	sizePerCube float64


	o       *proto.Obs
	t       float64
	pos     [3]float64
	vel     [3]float64
	aim     [2]float64
	hp      float64
	maxHP   float64
	energy  float64
	scale   float64
	radius  float64
	height  float64
	eyeH    float64
	muzzleH float64
	walk    float64
	boostV  float64
	turn    float64
	pitchR  float64
	armor   float64
	slots   [2]slot


	tracks  map[int]*Track
	crates  map[int]*Item
	cubes   map[int]*Item
	pickups map[int]*Item

	lastDamageT  float64
	lastWeaponDT float64
	lastEnemyLOST float64
	lastDealtT   float64
	recentDmg    float64
	lastDmgBear  float64
	lastDmgBy    int
	lastSoundT   float64
	lastSoundB   float64


	path       []int32
	pathBad    bool
	pathSet    bool
	pathGoal   [2]float64
	pathT      float64
	pathIdx    int
	strafeSign float64
	strafeT    float64
	stuckT     float64
	stuckPos   [3]float64
	stuckFor   float64
	unstickT   float64
	unstickDir [2]float64
	lastMove   [2]float64


	mode       string
	targetID   int
	retreating bool
	coverCell  int
	coverT     float64
	deepCell   int
	deepT      float64
	deepTryT   float64
	standT      float64
	creditAbsorbT float64
	nearCoverT  float64
	nearCoverOK bool
	lootID     int
	lootT      float64
	holdCell   int
	holdT      float64
	lastAimCmd [2]float64
	scanPhase  float64
	laserHold  bool
	takeT      float64
	ffaSeenT    float64
	ffaBeams    int
	kills       int
	killsSeen   int
	deadSeen    int
	unexplained int
	ffa         bool
	st          stance
	evadeCell   int
	evadeT      float64
	hideT       float64
	lastLabel   string
	modeLabel   string
	lastTraceT  float64
	lastNpcDT   float64
	seenT       []float32
	seenNX      int
	seenNY      int
	roamCell    int
	roamT       float64
	dmgLog      []dmgRec
	modeLog     []modeRec
	hitLog      []hitRec
	lowT        float64
	retreatT    float64
	corneredT   float64
	zgKey       [3]float64
	zgT         float64
	zgComp      int32
	zgGoal      [2]float64
	zgWalk      bool
	myComp      int32
	mainCompID  int32
	surf        []int32
	surfGoal    [2]float64
	surfT       float64
	surfIdx     int
	surfBan     map[int]float64
	surfWatchT  float64
	surfWatchPos [3]float64
	surfPushing bool
	banUntil    map[int]float64
	seekBan     map[int]float64
	roof        roofPlan
	roofCoverC  int
	roofCoverT  float64
	unquietT    float64
	peek        peekPlan
	roofCoverHoldT float64
	holdClimb   bool
	holdRoofMove bool
	jinkSign    float64
	jinkT       float64
	edgeOnT     float64
	slipCell    int
	slipT       float64
	slipOnT     float64
	hm          *hideMap
	hideCell    int
	hideOut     hideout
	hideOutOK   bool
	hideOutT    float64
	roofFirstOK bool
	roofFirstChecked bool

	roofSecs      float64
	dmgOnRoof     float64
	dmgOffRoof    float64
	dmgClimb      float64
	climbs        int
	prevRoofState int
	creditT     float64
	creditID    int

	scratch []cand
}


func Factory(h *proto.Hello, w *world.World, nav *world.Nav) *Bot {
	return New(h, w, nav, DefaultParams())
}

func New(h *proto.Hello, w *world.World, nav *world.Nav, p Params) *Bot {
	b := &Bot{P: p, H: h, C: &h.Config, W: w, Nav: nav}


	b.rng = rand.New(rand.NewSource(h.Seed*7919 + int64(h.Slot) + 1 + int64(p.Salt)*104729))
	hz := stat(h.Config.Match, "tick_hz", 20)
	if hz <= 0 {
		hz = 20
	}
	b.dt = 1 / hz
	b.decide = stat(h.Config.Match, "decide_every", 2) * b.dt
	b.sizePerCube = h.Config.Cubes.SizePerCube
	b.tracks = map[int]*Track{}
	b.crates = map[int]*Item{}
	b.cubes = map[int]*Item{}
	b.pickups = map[int]*Item{}
	b.strafeSign = 1
	b.targetID = -1
	b.lootID = -1
	b.coverCell = -1
	b.deepCell, b.deepT, b.deepTryT = -1, -100, -100
	b.nearCoverT = -100
	b.standT = -100
	b.creditAbsorbT = -100
	b.holdCell = -1
	b.evadeCell = -1
	b.lastDamageT = -100
	b.lastWeaponDT = -100
	b.lastEnemyLOST = -100
	b.lastDealtT = -100
	b.lastSoundT = -100
	b.ffaSeenT = -100
	b.lastDmgBy = -1
	b.lastNpcDT = -100
	b.roamCell = -1
	b.creditT = -100
	b.lowT = -100
	b.corneredT = -100
	b.mode = "init"
	b.roof.id = -1
	b.roof.want, b.roof.spot = -1, -1
	b.roofCoverC = -1
	b.hideCell = -1
	b.hideOutT = -100
	b.unquietT = -100
	b.slipCell, b.slipT, b.slipOnT = -1, -100, -100
	b.edgeOnT = -100
	b.jinkSign, b.jinkT = 1, -100
	b.roofCoverHoldT = -100
	b.peek = peekPlan{t: -100, tgt: -1, roof: -1, duck: -1, fire: -1}
	if p.UseHideMap || p.HoldHideMap {
		b.hm = getHideMap(nav)
	}
	b.roofFirstOK = true
	b.banUntil = map[int]float64{}
	b.coverT = -100
	b.evadeT = -100
	b.roofCoverT = -100

	nav.Exposure()
	nav.Components()
	nav.Roofs()
	nav.Tops()
	b.surfT = -100
	return b
}


var Trace = os.Getenv("MECH_TRACE") != ""


var Stats = os.Getenv("MECH_STATS") != ""

func (b *Bot) trace(act *proto.Action) {
	if b.modeLabel == b.lastLabel && b.t-b.lastTraceT < 5 {
		return
	}
	b.lastLabel, b.lastTraceT = b.modeLabel, b.t
	tg := ""
	if tr := b.tracks[b.targetID]; tr != nil {
		tg = fmt.Sprintf(" tgt=%d d=%.0f los=%v hp=%.0f", tr.ID, dist3(b.pos, tr.Pos), tr.LOS, tr.HP)
	}
	w := ""
	for i := 0; i < 2; i++ {
		if b.slots[i].ok {
			w += b.slots[i].kind[:3] + " "
		}
	}
	fmt.Fprintf(os.Stderr, "[%d] t=%6.1f alive=%2d hp=%4.0f/%4.0f en=%3.0f cubes=%2d pos=(%.0f,%.0f,%.0f) %-18s w=%s proj=%d mv=(%+.1f,%+.1f)%s%s\n",
		b.H.Slot, b.t, b.o.Alive, b.hp, b.maxHP, b.energy, b.o.Self.Cubes, b.pos[0], b.pos[1], b.pos[2], b.modeLabel, w, len(b.o.Projectiles), act.Move[0], act.Move[1], map[bool]string{true: " BOOST", false: ""}[act.Boost], tg)
	if strings.Contains(b.modeLabel, "zone") {
		z := &b.o.Zone
		fmt.Fprintf(os.Stderr, "      zone cur=(%.0f,%.0f r%.0f) dcur=%.0f next=(%.0f,%.0f r%.0f) dnext=%.0f shrink=%.0f..%.0f inzone=%v goal=(%.0f,%.0f) walk=%v comp=%d ground=%v jump=%v\n",
			z.Center[0], z.Center[1], z.Radius, hyp(b.pos[0]-z.Center[0], b.pos[1]-z.Center[1]), z.NextCenter[0], z.NextCenter[1], z.NextRadius,
			hyp(b.pos[0]-z.NextCenter[0], b.pos[1]-z.NextCenter[1]), z.ShrinkStart, z.ShrinkEnd, b.o.Self.InZone, b.zgGoal[0], b.zgGoal[1], b.zgWalk, b.myComp, b.onGroundLevel(), act.Jump)
	}
}


func (b *Bot) Act(o *proto.Obs) proto.Action {
	act := proto.NewAction(o.Tick)
	b.observe(o)
	b.think(&act)
	if Trace {
		b.trace(&act)
	}
	if Stats && o.Tick > 0 && o.Tick%600 == 0 {
		w := ""
		for i := 0; i < 2; i++ {
			if b.slots[i].ok {
				w += b.slots[i].kind + "+"
			}
		}
		fmt.Fprintf(os.Stderr, "[stat] t=%d stance=%s weapons=%s cubes=%d hp=%.0f alive=%d\n", int(b.t), b.st.name, w, o.Self.Cubes, b.hp, o.Alive)
		fmt.Fprintf(os.Stderr, "[roof] t=%d onroof_s=%.0f offroof_s=%.0f dmg_on=%.0f dmg_off=%.0f dmg_climb=%.0f climbs=%d\n", int(b.t), b.roofSecs, b.t-b.roofSecs, b.dmgOnRoof, b.dmgOffRoof, b.dmgClimb, b.climbs)
	}
	if Stats {
		on := b.onRoof() >= 0 && o.Self.Grounded
		if on {
			b.roofSecs += b.decide
		}
		for i := range o.Events {
			e := &o.Events[i]
			if e.Type == "damaged" && e.Weapon != "zone" {
				switch {
				case on:
					b.dmgOnRoof += e.Amount
				case b.roof.state == roofClimb:
					b.dmgClimb += e.Amount
				default:
					b.dmgOffRoof += e.Amount
				}
			}
		}
		if b.roof.state == roofClimb && b.prevRoofState != roofClimb {
			b.climbs++
		}
		b.prevRoofState = b.roof.state
	}
	if Stats && b.hp < 220 && b.t-b.lowT > 15 && len(b.dmgLog) > 0 {

		b.lowT = b.t
		type agg struct {
			dmg, d float64
			n, seen int
			w       string
		}
		by := map[int]*agg{}
		first := b.t
		total := 0.0
		for _, r := range b.dmgLog {
			if b.t-r.t > 12 {
				continue
			}
			a := by[r.by]
			if a == nil {
				a = &agg{}
				by[r.by] = a
			}
			a.dmg += r.amt
			a.n++
			a.w = r.weapon
			if r.d >= 0 {
				a.d = r.d
			}
			if r.seen {
				a.seen++
			}
			if r.t < first {
				first = r.t
			}
			total += r.amt
		}
		s := ""
		for id, a := range by {
			s += fmt.Sprintf(" %d:%s:%.0fdmg:%.0fm:seen%d/%d", id, a.w, a.dmg, a.d, a.seen, a.n)
		}
		w := ""
		for i := 0; i < 2; i++ {
			if b.slots[i].ok {
				w += b.slots[i].kind + "+"
			}
		}

		modes := map[string]int{}
		nm := 0
		for _, mr := range b.modeLog {
			if mr.t >= first-0.5 {
				modes[mr.mode]++
				nm++
			}
		}
		top, topN := "", 0
		for m, c := range modes {
			if c > topN {
				top, topN = m, c
			}
		}
		dealt := 0.0
		for _, hr := range b.hitLog {
			if hr.t >= first-0.5 {
				dealt += hr.amt
			}
		}
		fmt.Fprintf(os.Stderr, "[low] t=%.1f stance=%s mode=%s weapons=%s cubes=%d attackers=%d over=%.1fs total=%.0f dealt=%.0f fightfrac=%.2f |%s\n", b.t, b.st.name, top, w, o.Self.Cubes, len(by), b.t-first, total, dealt, float64(modes["fight"]+modes["fight+cube"])/float64(max(nm, 1)), s)
	}
	if Stats {
		b.modeLog = append(b.modeLog, modeRec{b.t, b.mode})
		if len(b.modeLog) > 400 {
			b.modeLog = b.modeLog[200:]
		}
	}

	if math.IsNaN(act.Move[0]) || math.IsNaN(act.Move[1]) {
		act.Move = [2]float64{0, 0}
	}
	if math.IsNaN(act.Aim[0]) || math.IsNaN(act.Aim[1]) {
		act.HasAim = false
	}
	b.lastMove = act.Move
	if act.HasAim {
		b.lastAimCmd = act.Aim
	}
	return act
}

func (b *Bot) mech(key string, def float64) float64 { return stat(b.C.Mech, key, def) }


func (b *Bot) observe(o *proto.Obs) {
	b.o = o
	b.t = o.T
	s := &o.Self
	b.pos, b.vel, b.aim = s.Pos, s.Vel, s.Aim
	b.hp, b.maxHP, b.energy = s.HP, s.MaxHP, s.Energy
	if b.maxHP <= 0 {
		b.maxHP = 1
	}
	st := s.Stats
	baseMuzzle := b.mech("muzzle_height", 7)
	b.scale = 1 + b.sizePerCube*float64(s.Cubes)
	b.muzzleH = stat(st, "muzzle_height", baseMuzzle*b.scale)
	b.eyeH = stat(st, "eye_height", b.mech("eye_height", 8)*b.scale)

	if b.muzzleH < baseMuzzle*b.scale-1e-6 {
		b.muzzleH = baseMuzzle * b.scale
	}
	if e := b.mech("eye_height", 8) * b.scale; b.eyeH < e-1e-6 {
		b.eyeH = e
	}
	b.radius = math.Max(stat(st, "radius", 0), b.mech("radius", 2.5)*b.scale)
	b.height = math.Max(stat(st, "height", 0), b.mech("height", 9)*b.scale)
	b.walk = stat(st, "walk_speed", b.mech("walk_speed", 11.7))
	b.boostV = stat(st, "boost_speed", b.mech("boost_speed", 19.5))
	b.turn = stat(st, "turn_rate", b.mech("turn_rate", 4))
	b.pitchR = stat(st, "pitch_rate", b.mech("pitch_rate", 3))
	b.armor = stat(st, "armor", 0)
	for i := 0; i < 2; i++ {
		b.slots[i] = slot{}
		if i < len(s.Weapons) && s.Weapons[i] != nil {
			w := s.Weapons[i]
			b.slots[i] = slot{ok: true, kind: w.Kind, cooldown: w.Cooldown, ammo: w.Ammo, reload: w.Reload, charge: w.Charge, stats: w.Stats}
			if b.slots[i].stats == nil {
				b.slots[i].stats = b.C.Weapons[w.Kind]
			}
		}
	}


	b.recentDmg *= math.Exp(-b.decide / 3.0)
	for _, tr := range b.tracks {
		tr.WasListed = tr.Listed
		tr.Listed = false
		tr.LOS = false
		tr.HurtMe *= math.Exp(-b.decide / 4.0)
		tr.IHurt *= math.Exp(-b.decide / 4.0)
	}

	if c := b.Nav.Nearest(b.pos[0], b.pos[1], 2.9, 9, 4); c >= 0 && b.onGroundLevel() {
		b.myComp = b.Nav.Components()[c]
	}

	eye := [3]float64{b.pos[0], b.pos[1], b.pos[2] + b.eyeH}
	fovHalf := b.C.Vision.FovDeg * math.Pi / 360
	if fovHalf <= 0 {
		fovHalf = math.Pi / 3
	}
	visRange := b.C.Vision.Range + stat(s.Stats, "vision_bonus", 0)
	nearRange := b.C.Vision.NearRange + stat(s.Stats, "near_range_bonus", 0)
	for i := range o.Mechs {
		m := &o.Mechs[i]
		tr := b.tracks[m.ID]
		if tr == nil {
			tr = &Track{ID: m.ID, NPC: m.Kind == "npc", HurtMeT: -100, IHurtT: -100, AimAtMeT: -100, LOST: -100, SeenT0: b.t, PhantomT: -100, ViewT: -100, EngT: -100}
			b.tracks[m.ID] = tr
		}
		if b.t-tr.LastSeen > 6 {
			tr.SeenT0 = b.t
		}
		tr.Pos, tr.Vel, tr.Aim = m.Pos, m.Vel, m.Aim
		if m.MaxHP > 0 {
			tr.HP, tr.MaxHP = m.HP, m.MaxHP
		} else if tr.MaxHP == 0 {
			tr.HP, tr.MaxHP = 1400, 1400
		}
		tr.Cubes = m.Cubes
		tr.Charging = m.Charging
		tr.LastSeen = b.t
		tr.Listed = true
		if !tr.NPC {
			tr.Gun, tr.Laser, tr.Mortar, tr.Light = false, false, false, false
			for _, w := range m.Weapons {
				switch w {
				case "gun":
					tr.Gun = true
				case "laser":
					tr.Laser = true
				case "mortar":
					tr.Mortar = true
				case "lightning":
					tr.Light = true
				}
			}
		}
		sc := 1.0
		if !tr.NPC {
			sc = tr.scale(b.sizePerCube)
		}
		ch := 4.5 * sc
		if tr.NPC {
			ch = stat(b.C.Npc, "height", 3.5) * 0.5
		}

		tr.LOS = b.W.Visible(eye[0], eye[1], eye[2], m.Pos[0], m.Pos[1], m.Pos[2]+ch) ||
			b.W.Visible(eye[0], eye[1], eye[2], m.Pos[0], m.Pos[1], m.Pos[2]+ch*1.9)
		if tr.LOS {
			tr.LOST = b.t
			if !tr.NPC {
				b.lastEnemyLOST = b.t
			}

			d3 := dist3(eye, [3]float64{m.Pos[0], m.Pos[1], m.Pos[2] + ch})
			if d3 < nearRange-1 || (d3 < visRange-2 && math.Abs(angDiff(math.Atan2(m.Pos[1]-b.pos[1], m.Pos[0]-b.pos[0]), b.aim[0])) < fovHalf-0.05) {
				tr.ViewT = b.t
			}
		}
		if !tr.NPC && tr.LOS {

			bear := math.Atan2(b.pos[1]-m.Pos[1], b.pos[0]-m.Pos[0])
			d := dist2(b.pos, m.Pos)
			tol := 0.12 + math.Atan2(b.radius*1.5, math.Max(d, 1))
			off := math.Abs(angDiff(m.Aim[0], bear))
			if off < tol {
				tr.AimAtMeT = b.t
			}
			if b.P.LeadPersist || b.P.LeadCum {
				b.leadRecord(tr, off < 0.35)
			}
		}
	}

	mem := b.C.Vision.MemoryS
	if mem <= 0 {
		mem = 5
	}
	for id, tr := range b.tracks {
		if b.t-tr.LastSeen > 45 && b.t-tr.HurtMeT > 45 {
			delete(b.tracks, id)
			continue
		}


		if tr.WasListed && !tr.Listed && b.t-tr.ViewT < mem-1.5 {
			delete(b.tracks, id)
			if b.targetID == id {
				b.targetID = -1
			}
		}
	}


	for i := range o.Events {
		e := &o.Events[i]
		switch e.Type {
		case "damaged":
			b.lastDamageT = b.t
			if e.Weapon == "npc" {

				b.lastNpcDT = b.t
				if e.Bearing != nil {
					b.lastDmgBear = *e.Bearing
				}
				if e.By != nil {
					if tr := b.tracks[*e.By]; tr != nil {
						tr.HurtMeT = b.t
					}
				}
			} else if e.Weapon != "zone" {
				b.lastWeaponDT = b.t
				b.recentDmg += e.Amount
				if e.Bearing != nil {
					b.lastDmgBear = *e.Bearing
				}
				if e.By != nil && *e.By != s.ID {
					b.lastDmgBy = *e.By
					tr := b.tracks[*e.By]
					if tr == nil {
						tr = &Track{ID: *e.By, NPC: *e.By >= 100, HurtMeT: -100, IHurtT: -100, AimAtMeT: -100, LOST: -100, SeenT0: b.t, LastSeen: -100, HP: 1400, MaxHP: 1400, PhantomT: -100, ViewT: -100, EngT: -100}
						b.tracks[*e.By] = tr
					}
					if !tr.Listed && b.t-tr.LastSeen > 2 && e.Bearing != nil {


						guess := 115.0
						switch e.Weapon {
						case "laser":
							guess = 150
						case "lightning":
							guess = 35
						}
						tr.Pos = [3]float64{b.pos[0] + math.Cos(*e.Bearing)*guess, b.pos[1] + math.Sin(*e.Bearing)*guess, b.pos[2]}
						tr.Vel = [3]float64{}
						tr.PhantomT = b.t
					}
					tr.HurtMeT = b.t
					tr.HurtMe += e.Amount
					if Stats {
						d := -1.0
						if tr.Listed {
							d = dist2(b.pos, tr.Pos)
						}
						b.dmgLog = append(b.dmgLog, dmgRec{b.t, *e.By, e.Weapon, e.Amount, d, tr.Listed && tr.LOS})
					}
					switch e.Weapon {
					case "laser":
						tr.Laser = true
					case "mortar":
						tr.Mortar = true
					case "lightning":
						tr.Light = true
					}
				}
			}
		case "hit":
			b.lastDealtT = b.t
			if e.Target < 100 {
				b.creditT = b.t
				b.creditID = e.Target
				if Stats {
					b.hitLog = append(b.hitLog, hitRec{b.t, e.Amount})
				}
			}
			if tr := b.tracks[e.Target]; tr != nil {
				tr.IHurtT = b.t
				tr.IHurt += e.Amount
			}
		case "kill":
			b.kills++
			delete(b.tracks, e.Target)
			if b.targetID == e.Target {
				b.targetID = -1
			}
		case "took":
			delete(b.pickups, e.ID.Num)
		case "take_failed":
			if e.Reason == "gone" || e.Reason == "have" {
				delete(b.pickups, e.ID.Num)
			}
		}
	}


	b.foldItems(o.Crates, b.crates, "crate")
	b.foldItems(o.Cubes, b.cubes, "cube")
	seen := map[int]bool{}
	for i := range o.Pickups {
		p := &o.Pickups[i]
		seen[p.ID] = true
		it := b.pickups[p.ID]
		if it == nil {
			it = &Item{ID: p.ID}
			b.pickups[p.ID] = it
		}
		it.Pos, it.Kind, it.LastSeen = p.Pos, p.Kind, b.t
		b.groundCheck(it)
	}
	b.expireUnseen(b.pickups, seen, eye)


	for i := range o.Sounds {
		sd := &o.Sounds[i]
		switch sd.Kind {
		case "gun", "laser", "lightning", "mortar", "laser_charge", "boost", "step", "jet", "reload":
			if sd.Dist != "far" {
				b.lastSoundT = b.t - sd.Age
				b.lastSoundB = sd.Bearing
			}
		}
	}

	sawFFABeam := false
	for i := range o.Beams {
		bm := &o.Beams[i]
		if bm.By == s.ID {
			continue
		}
		if b.P.LaserCDTrack && bm.Kind == "laser" {
			if tr := b.tracks[bm.By]; tr != nil {
				tr.LaserFiredT = b.t - bm.Age
			}
		}
		if len(bm.Path) >= 2 {
			p0 := bm.Path[0]
			end := bm.Path[len(bm.Path)-1]
			segD, _ := segPointDist2D(b.pos[0], b.pos[1], p0[0], p0[1], end[0], end[1])
			if dist2(end, b.pos) > 25 && segD > 22 {
				b.ffaSeenT = b.t
				sawFFABeam = true
			}
		}
	}
	if sawFFABeam {
		b.ffaBeams++
	}
}

func (b *Bot) foldItems(list []proto.ItemObs, m map[int]*Item, kind string) {
	eye := [3]float64{b.pos[0], b.pos[1], b.pos[2] + b.eyeH}
	seen := map[int]bool{}
	for i := range list {
		p := &list[i]
		seen[p.ID] = true
		it := m[p.ID]
		if it == nil {
			it = &Item{ID: p.ID, Kind: kind}
			m[p.ID] = it
		}
		it.Pos, it.HP, it.LastSeen = p.Pos, p.HP, b.t
		b.groundCheck(it)
	}
	b.expireUnseen(m, seen, eye)
}


func (b *Bot) expireUnseen(m map[int]*Item, seen map[int]bool, eye [3]float64) {
	near := b.C.Vision.NearRange * 0.85
	for id, it := range m {
		if seen[id] {
			continue
		}
		if b.t-it.LastSeen > 240 {
			delete(m, id)
			continue
		}
		d := dist3(it.Pos, eye)
		if d < near && b.W.Visible(eye[0], eye[1], eye[2], it.Pos[0], it.Pos[1], it.Pos[2]+0.8) {
			delete(m, id)
		}
	}
}


func (b *Bot) groundCheck(it *Item) {
	k := b.Nav.Index(it.Pos[0], it.Pos[1])
	it.Cell = k
	it.Ground = false
	if !b.Nav.Solid[k] && math.Abs(float64(b.Nav.Z[k])-it.Pos[2]) < 3.0 {
		it.Ground = true
		return
	}

	if c := b.Nav.Nearest(it.Pos[0], it.Pos[1], b.radius, b.height, 2); c >= 0 && math.Abs(float64(b.Nav.Z[c])-it.Pos[2]) < 3.0 {
		it.Cell = c
		it.Ground = true
	}
}

func (b *Bot) has(kind string) int {
	for i := 0; i < 2; i++ {
		if b.slots[i].ok && b.slots[i].kind == kind {
			return i
		}
	}
	return -1
}

func (b *Bot) cubeDamageMul(cubes int) float64 {
	capc := b.C.Cubes.StatCap
	c := float64(cubes)
	if c > capc {
		c = capc
	}
	return 1 + b.C.Cubes.DamagePerCube*c
}
