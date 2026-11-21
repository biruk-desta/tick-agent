package bot


func Variants() map[string]func(p *Params) {
	return map[string]func(p *Params){

		"v05": func(p *Params) { v05(p) },

		"v05-hm": func(p *Params) { v05(p); p.UseHideMap = true; p.QuietHoldS = 3 },

		"fighter": func(p *Params) { v05(p); p.PracticeAware = false },

		"ghost": func(p *Params) { p.ForceFFA = true },

		"ghost-noloot": func(p *Params) { p.ForceFFA = true; p.FFALootRadius = 0 },

		"nohm":     func(p *Params) { p.UseHideMap = false },
		"hm-near":  func(p *Params) { p.HideDistW = 0.30 },
		"hm-far":   func(p *Params) { p.HideDistW = 0.08 },
		"hm-hit":   func(p *Params) { p.HideSeenW, p.HideHitW = 0.2, 1.3 },
		"hm-seen":  func(p *Params) { p.HideSeenW, p.HideHitW = 1.2, 0.4 },
		"hm-noroof": func(p *Params) { p.UseRoofs = false },
		"sfr70":    func(p *Params) { p.StealthFightRange = 70 },
		"sfr100":   func(p *Params) { p.StealthFightRange = 100 },
		"sfr200":   func(p *Params) { p.StealthFightRange = 200 },

		"patient60":  func(p *Params) { p.PatientSecs = 60 },
		"patient120": func(p *Params) { p.PatientSecs = 120 },
		"patient200": func(p *Params) { p.PatientSecs = 200; p.PatientCubes = 15 },

		"nokite":   func(p *Params) { p.KiteMin = 0 },
		"kite80":   func(p *Params) { p.KiteMin, p.KiteMax = 80, 130 },
		"kite140":  func(p *Params) { p.KiteMin, p.KiteMax = 140, 200 },

		"rooffirst":   func(p *Params) { p.RoofFirstSecs = 40; p.RoofFirstDist = 90 },
		"rooffirst60": func(p *Params) { p.RoofFirstSecs = 60; p.RoofFirstDist = 150 },

		"ttd6":  func(p *Params) { p.LeaveTTD = 6 },
		"ttd16": func(p *Params) { p.LeaveTTD = 16 },

		"duel0": func(p *Params) { p.UseRoofs = false; p.DuelDisengage = 0 },
		"duel25": func(p *Params) { p.UseRoofs = false; p.DuelDisengage = 0.25 },
		"duel75": func(p *Params) { p.UseRoofs = false; p.DuelDisengage = 0.75 },

		"noroof": func(p *Params) { p.UseRoofs = false },

		"roofsquad": func(p *Params) { p.RoofInSquad = true },

		"fighter-noroof": func(p *Params) { p.PracticeAware = false; p.UseRoofs = false },

		"ghost-greedy": func(p *Params) { p.ForceFFA = true; p.FFALootRadius = 260; p.FFAWantCubes = 20 },



		"f-hit": func(p *Params) { p.PracticeAware = false; p.HitModel = 1 },

		"f-plan": func(p *Params) { p.PracticeAware = false; p.HitModel = 1; p.PlanV2 = true },

		"f-nk": func(p *Params) { p.PracticeAware = false; p.HitModel = 1; p.PlanV2 = true; p.KiteNeedsLaser = true },

		"f-las": func(p *Params) { brawl(p) },
		"f-las4": func(p *Params) { brawl(p); p.LaserValue = 4 },
		"f-las8": func(p *Params) { brawl(p); p.LaserValue = 8; p.ArmSwapMin = 0.5 },

		"f-ex":  func(p *Params) { brawl(p); p.ExchangeW = 0.6 },
		"f-ex1": func(p *Params) { brawl(p); p.ExchangeW = 1.0 },

		"f-d35": func(p *Params) { brawl(p); p.DuelDisengage = 0.35 },
		"f-d70": func(p *Params) { brawl(p); p.DuelDisengage = 0.70 },
		"f-d90": func(p *Params) { brawl(p); p.DuelDisengage = 0.90 },

		"f-e10": func(p *Params) { brawl(p); p.EngageRatio = 1.0 },
		"f-e16": func(p *Params) { brawl(p); p.EngageRatio = 1.6 },
		"f-nohunt": func(p *Params) { brawl(p); p.Hunt = false },

		"hit1": func(p *Params) { p.HitModel = 1; p.PlanV2 = true },


		"brawl":    func(p *Params) { brawl2(p) },
		"b-stand":  func(p *Params) { brawl2(p); p.AvoidAdv = 0 },
		"b-av10":   func(p *Params) { brawl2(p); p.AvoidAdv = 1.0 },
		"b-av16":   func(p *Params) { brawl2(p); p.AvoidAdv = 1.6 },
		"b-avr60":  func(p *Params) { brawl2(p); p.AvoidRange = 60 },
		"b-avr120": func(p *Params) { brawl2(p); p.AvoidRange = 120 },
		"b-cov90":  func(p *Params) { brawl2(p); p.AvoidCover = 90 },
		"b-las3":   func(p *Params) { brawl2(p); p.LaserValue = 3 },
		"b-las10":  func(p *Params) { brawl2(p); p.LaserValue = 10; p.ArmSwapMin = 0.5 },
		"b-e10":    func(p *Params) { brawl2(p); p.BrawlEngage = 1.0 },
		"b-e18":    func(p *Params) { brawl2(p); p.BrawlEngage = 1.8 },
		"b-nohunt": func(p *Params) { brawl2(p); p.BrawlHunt = false },
		"b-hl200":  func(p *Params) { brawl2(p); p.HuntRangeLaser = 200 },
		"b-ex":     func(p *Params) { brawl2(p); p.ExchangeW = 0.7 },
		"b-c10":    func(p *Params) { brawl2(p); p.BrawlWantCubes = 10 },
		"b-c25":    func(p *Params) { brawl2(p); p.BrawlWantCubes = 25 },
		"b-lr120":  func(p *Params) { brawl2(p); p.BrawlLootRadius = 120 },
		"b-d35":    func(p *Params) { brawl2(p); p.DuelDisengage = 0.35 },
		"b-d75":    func(p *Params) { brawl2(p); p.DuelDisengage = 0.75 },
		"b-oldhit": func(p *Params) { brawl2(p); p.HitModel = 0 },

		"b-open45":  func(p *Params) { p.OpenSecs = 45 },
		"b-open90":  func(p *Params) { p.OpenSecs = 90 },
		"b-open999": func(p *Params) { p.OpenSecs = 9999 },

		"b-oldlead": func(p *Params) { oldLead(p) },
		"b-damp5":   func(p *Params) { oldLead(p); p.LeadDamp = 0.5 },
		"b-pers":    func(p *Params) { oldLead(p); p.LeadDamp = 0.5; p.LeadPersist = true },
		"b-cum":     func(p *Params) { oldLead(p); p.LeadDamp = 0.5; p.LeadCum = true },
		"b-perscum": func(p *Params) { oldLead(p); p.LeadDamp = 0.5; p.LeadPersist = true; p.LeadCum = true },
		"b-pc75":    func(p *Params) { p.LeadDamp = 0.75 },
		"b-pc100":   func(p *Params) { p.LeadDamp = 1.0 },

		"b-jit":   func(p *Params) { p.StrafeMin, p.StrafeMax = 0.25, 0.55 },
		"b-jit2":  func(p *Params) { p.StrafeMin, p.StrafeMax = 0.2, 0.42 },
		"b-jitj":  func(p *Params) { p.StrafeMin, p.StrafeMax = 0.25, 0.55; p.Jink = 0.6 },

		"v07":  func(p *Params) { v07(p) },
		"v071": func(p *Params) { v074(p); p.EdgeHold = 0; p.NoMortar = false; p.RunOnRange = 0; p.CoverMargin = 0 },
		"v072": func(p *Params) { v074(p); p.NoMortar = false; p.RunOnRange = 0; p.CoverMargin = 0 },
		"v073": func(p *Params) { v074(p); p.RunOnRange = 0; p.CoverMargin = 0 },
		"v074": func(p *Params) { v074(p) },
		"b-standrun": func(p *Params) { p.RetreatRunMax = 50 },

		"s1":         func(p *Params) { p.Salt = 1 },
		"s2":         func(p *Params) { p.Salt = 2 },
		"s3":         func(p *Params) { p.Salt = 3 },
		"s4":         func(p *Params) { p.Salt = 4 },
		"s5":         func(p *Params) { p.Salt = 5 },
		"s6":         func(p *Params) { p.Salt = 6 },
		"b-shy":      func(p *Params) { p.SlotRule = true; p.ShySecs = 25 },
		"b-slotonly": func(p *Params) { p.SlotRule = true },
		"b-ffa0":     func(p *Params) { p.ForceFFA = true },
		"b-shy40":    func(p *Params) { p.SlotRule = true; p.ShySecs = 40 },
		"b-shyb":     func(p *Params) { p.SlotRule = true; p.ShySecs = 25; p.ShyBoost = 40 },
		"b-shyr90":   func(p *Params) { p.SlotRule = true; p.ShySecs = 25; p.ShyLootRadius = 90 },
		"b-shyall":   func(p *Params) { p.SlotRule = true; p.ShySecs = 25; p.ShyBoost = 40; p.ShyLootRadius = 90; p.ShyExposure = 0.6 },
		"b-nocredit2": func(p *Params) { p.CreditOpenS = 0 },

		"b-rr35": func(p *Params) { p.RetreatRunMax = 35 },
		"b-rr70": func(p *Params) { p.RetreatRunMax = 70 },

		"b-run0":   func(p *Params) { p.RunOnRange = 0 },
		"b-cm0":    func(p *Params) { p.CoverMargin = 0 },
		"b-cm14":   func(p *Params) { p.CoverMargin = 14 },
		"b-run120": func(p *Params) { p.RunOnRange = 120 },

		"b-real":    func(p *Params) { p.CoverFirst = true; p.HuntLaserEdge = true },
		"b-realh":   func(p *Params) { p.CoverFirst = true; p.HuntLaserEdge = true; p.HuntRangeLaser = 200 },
		"b-realc":   func(p *Params) { p.CoverFirst = true },
		"b-realx":   func(p *Params) { p.HuntLaserEdge = true },
		"b-realb5":  func(p *Params) { p.CoverFirst = true; p.HuntLaserEdge = true; p.LootHiddenBias = 0.5 },
		"b-realb8":  func(p *Params) { p.CoverFirst = true; p.HuntLaserEdge = true; p.LootHiddenBias = 0.8 },
		"b-cf":      func(p *Params) { p.CoverFirst = true },
		"b-cf60":    func(p *Params) { p.CoverFirst = true; p.CoverMinRange = 60 },
		"b-cf90c":   func(p *Params) { p.CoverFirst = true; p.AvoidCover = 90 },
		"b-cf15":    func(p *Params) { p.CoverFirst = true; p.AvoidAdv = 1.5 },
		"b-cf20":    func(p *Params) { p.CoverFirst = true; p.AvoidAdv = 2.0 },
		"b-cf30":    func(p *Params) { p.CoverFirst = true; p.AvoidAdv = 3.0 },
		"b-cf99":    func(p *Params) { p.CoverFirst = true; p.AvoidAdv = 99 },
		"b-cf20h":   func(p *Params) { p.CoverFirst = true; p.AvoidAdv = 2.0; p.BrawlEngage = 2.0 },
		"b-cf99h":   func(p *Params) { p.CoverFirst = true; p.AvoidAdv = 99; p.BrawlHunt = false },
		"b-cfpeek":  func(p *Params) { p.CoverFirst = true; p.Peek = true },
		"b-peek":    func(p *Params) { p.Peek = true },
		"b-peek14":  func(p *Params) { p.Peek = true; p.PeekReach = 14; p.PeekCover = 40 },
		"b-peekh":   func(p *Params) { p.Peek = true; p.HuntRangeLaser = 200 },
		"b-noslack": func(p *Params) { p.ZoneSlack = 0 },
		"b-oe2":     func(p *Params) { p.OverlandEarly = 2.5 },
		"b-oe4":     func(p *Params) { p.OverlandEarly = 4 },
		"b-rc3":     func(p *Params) { p.RoofCenterW = 0.3 },
		"b-rc6":     func(p *Params) { p.RoofCenterW = 0.6 },
		"b-rlq":     func(p *Params) { p.RoofLeaveQuiet = 25 },
		"b-rc3lq":   func(p *Params) { p.RoofCenterW = 0.3; p.RoofLeaveQuiet = 25 },
		"b-noroof":  func(p *Params) { p.BrawlRoofs = false },
		"b-nopre":   func(p *Params) { p.LaserPreempt = false; p.LaserAimRange = 0; p.AvoidCoverLaser = 0 },
		"b-c15":     func(p *Params) { p.BrawlWantCubes = 15 },

		"b-roof":    func(p *Params) { p.BrawlRoofs = true },
		"b-roofpre": func(p *Params) { p.BrawlRoofs = true; p.LaserPreempt = true; p.LaserAimRange = 285 },
		"b-roof3":   func(p *Params) { p.BrawlRoofs = true; p.BrawlRoofCubes = 3; p.BrawlRoofAfter = 40 },
		"b-roof10":  func(p *Params) { p.BrawlRoofs = true; p.BrawlRoofCubes = 10; p.BrawlRoofAfter = 100 },

		"b-jink5": func(p *Params) { p.Jink = 0.5 },
		"b-jink8": func(p *Params) { p.Jink = 0.8 },

		"b-hm":     func(p *Params) { p.HoldHideMap = true },
		"b-las285": func(p *Params) { p.LaserAimRange = 285 },
		"b-hm285":  func(p *Params) { p.HoldHideMap = true; p.LaserAimRange = 285 },
		"b-pre":    func(p *Params) { p.LaserPreempt = true; p.LaserAimRange = 285 },
		"b-pre90":  func(p *Params) { p.LaserPreempt = true; p.LaserAimRange = 285; p.AvoidCoverLaser = 90 },
		"b-cov90l": func(p *Params) { p.AvoidCoverLaser = 90 },

		"b-noprov2":  func(p *Params) { p.ProvokeRule = false },
		"b-noplink2": func(p *Params) { p.PlinkMaxDPS = 0 },
		"b-nosprint": func(p *Params) { p.LootBoost = 0 },
		"b-nocredit": func(p *Params) { p.CreditFix = false },

		"v06":  func(p *Params) { v061(p); p.PathFix = false },
		"v061": func(p *Params) { v061(p) },

		"b-sprint":   func(p *Params) { brawl2(p); p.LootBoost = 30 },
		"b-sprint10": func(p *Params) { brawl2(p); p.LootBoost = 30; p.LaserValue = 10; p.ArmSwapMin = 0.5 },
		"b-nomortar": func(p *Params) { brawl2(p); p.NoMortar = true },

		"b-prov":      func(p *Params) { brawl2(p); p.ProvokeRule = true },
		"b-plink":     func(p *Params) { brawl2(p); p.PlinkMaxDPS = 60 },
		"b-provplink": func(p *Params) { brawl2(p); p.ProvokeRule = true; p.PlinkMaxDPS = 60 },
		"b-pps":       func(p *Params) { brawl2(p); p.ProvokeRule = true; p.PlinkMaxDPS = 60; p.LootBoost = 30 },
		"b-pp40":      func(p *Params) { brawl2(p); p.ProvokeRule = true; p.PlinkMaxDPS = 40 },
		"b-pp90":      func(p *Params) { brawl2(p); p.ProvokeRule = true; p.PlinkMaxDPS = 90 },
	}
}


func v05(p *Params) {
	p.Brawl = false
	p.HitModel = 0
	p.PlanV2 = false
	p.KiteNeedsLaser = false
	p.LaserValue = 3.0
	p.AvoidAdv = 0
	p.UseHideMap = false
	p.QuietHoldS = 0
	p.PathFix = false
	p.CreditFix = false
	p.LootBoost = 0
	p.ProvokeRule = false
	p.PlinkMaxDPS = 0
	p.ZoneSlack = 0
	p.DropStick = false
	p.RoofLeaveQuiet = 0
	p.RoofStandCheck = false
	p.RunOnRange = 0
	p.CoverMargin = 0
	p.RetreatRunMax = 0
	p.CreditOpenS = 0
	oldLead(p)
}


func v074(p *Params) {
	p.RetreatRunMax = 0
	p.CreditOpenS = 0
	p.ShySecs = 0
	p.SlotRule = false
}


func oldLead(p *Params) {
	p.LeadDamp = 0.75
	p.LeadPersist = false
	p.LeadCum = false
}


func v061(p *Params) {
	brawl2(p)
	p.LootBoost = 0
	p.ProvokeRule = false
	p.PlinkMaxDPS = 0
	p.CreditFix = false
	p.ZoneSlack = 0
	p.BrawlWantCubes = 15
	p.BrawlRoofs = false
	p.LaserPreempt = false
	p.LaserAimRange = 0
	p.AvoidCoverLaser = 0
	p.RoofLeaveQuiet = 0
	p.DropStick = false
	p.CoverFirst = false
	p.HuntLaserEdge = false
	p.LootHiddenBias = 0
	p.EdgeHold = 0
	p.NoMortar = false
	p.RunOnRange = 0
	p.CoverMargin = 0
	p.RetreatRunMax = 0
	p.CreditOpenS = 0
	oldLead(p)
}


func v07(p *Params) {
	p.CoverFirst = false
	p.HuntLaserEdge = false
	p.LootHiddenBias = 0
	p.EdgeHold = 0
	p.NoMortar = false
	p.RunOnRange = 0
	p.CoverMargin = 0
	p.RetreatRunMax = 0
	p.CreditOpenS = 0
}



func brawl2(p *Params) {
	p.Brawl = true
	p.HitModel = 1
	p.PlanV2 = true
	p.KiteNeedsLaser = true
	p.LaserValue = 6
	p.AvoidAdv = 1.25
}


func brawl(p *Params) {
	p.PracticeAware = false
	p.HitModel = 1
	p.PlanV2 = true
	p.KiteNeedsLaser = true
	p.LaserValue = 6
}
