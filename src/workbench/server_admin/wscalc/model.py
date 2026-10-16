"""(Ported from the standalone ws_model.py analysis.) DSP physical weapon skill model: analytical expected damage + Monte Carlo port of doPhysicalWeaponskill.
Modes: 'dsp' (as coded) and 'retail' (wsdist-style differences: fSTR/4, weapon pDIF cap, no level correction, +100 first-hit acc, DEX crit table)."""
import random, json

def alpha(l):
    for lim, a in [(5,1),(11,.99),(17,.98),(23,.97),(29,.96),(35,.95),(41,.94),(47,.93),(53,.92),(59,.91),(61,.90),(63,.89),(65,.88),(67,.87),(69,.86),(71,.85),(73,.84),(75,.83)]:
        if l <= lim: return a
    return .85 if l < 99 else 1.0

def ftp(tp, a, b, c):
    tp = max(tp, 1000)
    return a + (b-a)/1000*(tp-1000) if tp < 2000 else b + (c-b)/1000*(tp-2000)

def fstr_dsp(dstr, base):
    for lim, add in [(12,4),(6,6),(1,7),(-2,8),(-7,9),(-15,10),(-21,12)]:
        if dstr >= lim: f = (dstr+add)/2; break
    else: f = (dstr+13)/2
    return max(-base/9, min(base/9+8, f))

def fstr_retail(dstr, base):
    for lim, add in [(-22,13),(-16,12),(-8,10),(-3,9),(0,8),(5,7),(11,6)]:
        if dstr <= lim: f = (dstr+add)/4; break
    else: f = (dstr+4)/4
    return max(-base/9, min(base/9+8, f))

def qlims(c):
    up = c+.5 if c<.5 else 1 if c<.7 else c+.3 if c<1.2 else c*1.25 if c<1.5 else c+.375 if c<2.625 else 3
    lo = 0 if c<.38 else c*1176/1024-448/1024 if c<1.25 else 1 if c<1.51 else c*1176/1024-775/1024 if c<2.44 else c-.375
    return lo, up

def cratio_dsp(att, df, atkmulti, alvl, tlvl, ignored=0, critbonus=0):
    c = max(0, min(2.25, att*atkmulti/(df-ignored)))
    c = max(0, c - (0.05*(tlvl-alvl) if alvl < tlvl else 0))
    lo, up = qlims(c)
    cc = max(0, min(3, c+1)); clo, cup = qlims(cc)
    k = 1 + min(max(critbonus,0),100)/100
    return (lo, up), (clo*k, cup*k)

PDIF_CAP = {'Katana':3.25,'Dagger':3.25,'Sword':3.25,'Axe':3.25,'Club':3.25,'Great Katana':3.5,'Hand-to-Hand':3.5,
            'Great Sword':3.75,'Staff':3.75,'Great Axe':3.75,'Polearm':3.75,'Scythe':4.0}

def cratio_retail(att, df, atkmulti, weapon, pdl=0.0):
    cap = PDIF_CAP.get(weapon, 3.25)*(1+pdl)
    c = att*atkmulti/df
    def rng(w):
        lo, up = qlims(w); return min(lo, cap), min(up, cap)
    return rng(c), tuple(x+1 for x in rng(c+1))  # crit adds 1.0 after cap (wsdist)

def dex_crit_retail(d):
    if d <= 6: return 0
    if d <= 13: return .01
    if d <= 19: return .02
    if d <= 29: return .03
    if d <= 39: return .04
    return min(.15, (d-35)/100)

def hitrate(acc, eva, alvl, tlvl, mode, bonus=0, first=False):
    a = acc + bonus
    if mode == 'dsp': a += 4*(alvl-tlvl)
    elif first: a += 100
    return max(.2, min(.95, (75 + (a-eva)/2)/100))

def compute(ws, s, mode='dsp', tp=3000):
    """ws: dict from ws_data.json (params). s: dict of player/target stats. Returns expected total damage (analytic) + parts."""
    p = ws['params']; D = ws
    g = lambda k, d=0: p.get(k, d) if not isinstance(p.get(k,d), str) else d
    a = alpha(s['lvl']) if mode == 'dsp' else 1.0
    wsc = sum(s[k]*g(k+'_wsc') for k in ['str','dex','vit','agi','int','mnd','chr'])
    dstr = s['str'] - s['t_vit']
    fs = fstr_dsp(dstr, s['wdmg_rank']) if mode == 'dsp' else fstr_retail(dstr, s['wdmg_rank'])
    base = s['wdmg'] + fs + wsc*a
    f = ftp(tp, g('ftp100',1), g('ftp200',1), g('ftp300',1))
    atkm = g('atkmulti', 1) or 1
    if mode == 'dsp':
        pd, pc = cratio_dsp(s['att'], s['t_def'], atkm, s['lvl'], s['t_lvl'], critbonus=s.get('crit_dmg',0))
    else:
        pd, pc = cratio_retail(s['att'], s['t_def'], atkm, D.get('weapon'), s.get('pdl',0))
    mp = lambda r: (r[0]+r[1])/2*1.025   # mean pDIF incl 1.00-1.05 spread
    hr1 = hitrate(s['acc'], s['t_eva'], s['lvl'], s['t_lvl'], mode, first=True)
    hrn = hitrate(s['acc'], s['t_eva'], s['lvl'], s['t_lvl'], mode)
    cr_native = max(.05, min(.2, (s['dex']-s['t_agi'])*.005)) if mode=='dsp' else dex_crit_retail(s['dex']-s['t_agi'])
    cr_native += s.get('crit_rate',0)/100
    can = bool(p.get('canCrit'))
    cr1 = (ftp(tp, g('crit100'), g('crit200'), g('crit300')) + cr_native) if can else 0
    crn = cr_native if can else 0
    cr1, crn = min(cr1,1), min(crn,1)
    hit = lambda hr, cr, dmg: hr*((1-cr)*dmg*mp(pd) + cr*dmg*mp(pc))
    multi = bool(p.get('multiHitfTP'))
    first = hit(hr1, cr1, base*f)
    nhit = int(g('numHits', 1))
    # DA/TA/QA bonus hits (first-hit proc only, main weapon; H2H/dual-wield get two chances)
    da, ta, qa = s.get('da',0)/100, s.get('ta',0)/100, s.get('qa',0)/100
    chances = 2 if (s.get('offhand') or D.get('weapon') == 'Hand-to-Hand') else 1
    exp_bonus = chances*(3*qa + 2*ta*(1-qa)*0 + 0)  # placeholder replaced below
    exp_bonus = chances*(qa*3 + ta*2 + da*1)  # rates treated as exclusive tiers (qa+ta+da<=1)
    extra = max(0, min(8, nhit) - 1) + exp_bonus
    offhand = hit(hrn, crn, base*(f if multi else 1)) if (s.get('offhand') or D.get('weapon')=='Hand-to-Hand') else 0
    # cap at 8 hits total is applied per-roll in MC; analytic ignores cap
    later = extra*hit(hrn, crn, base*(f if multi else 1))
    wsd = (100 + s.get('wsd',0))/100
    total = (first + offhand + later)*wsd
    return {'total': total, 'base': base, 'fstr': fs, 'ftp': f, 'hit1': hr1, 'hitn': hrn, 'crit1': cr1, 'critn': crn,
            'pdif': pd, 'pdif_crit': pc, 'alpha': a, 'hits_expected': hr1 + (1 if offhand else 0)*hrn + later/max(1e-9, hit(hrn,crn,base*(f if multi else 1)))*hrn if later else hr1}

def montecarlo_dsp(ws, s, tp=3000, n=200000, seed=1):
    """Literal port of the doPhysicalWeaponskill RNG flow (DSP as coded), for verification."""
    random.seed(seed)
    p = ws['params']; g = lambda k, d=0: p.get(k, d) if isinstance(p.get(k, d), (int, float)) else d
    a = alpha(s['lvl'])
    wsc = sum(s[k]*g(k+'_wsc') for k in ['str','dex','vit','agi','int','mnd','chr'])
    fs = fstr_dsp(s['str']-s['t_vit'], s['wdmg_rank'])
    base = s['wdmg'] + fs + wsc*a
    f = ftp(tp, g('ftp100',1), g('ftp200',1), g('ftp300',1))
    atkm = g('atkmulti',1) or 1
    pd, pc = cratio_dsp(s['att'], s['t_def'], atkm, s['lvl'], s['t_lvl'], critbonus=s.get('crit_dmg',0))
    hr = hitrate(s['acc'], s['t_eva'], s['lvl'], s['t_lvl'], 'dsp')
    nat = max(.05, min(.2, (s['dex']-s['t_agi'])*.005)) + s.get('crit_rate',0)/100
    can = bool(p.get('canCrit'))
    critrate = (ftp(tp, g('crit100'), g('crit200'), g('crit300')) + nat) if can else 0
    multi = bool(p.get('multiHitfTP'))
    gp = lambda r, melee=True: random.randint(int(r[0]*1000), int(r[1]*1000))/1000*(random.randint(100,105)/100)
    dmg = base*f; tot = 0.0
    off = s.get('offhand') or ws.get('weapon') == 'Hand-to-Hand'
    da, ta, qa = s.get('da',0)/100, s.get('ta',0)/100, s.get('qa',0)/100
    for _ in range(n):
        d = 0.0
        if random.random() <= hr:
            if can and random.random() <= critrate: d = dmg*gp(pc)
            else: d = dmg*gp(pd)
        dm = dmg if multi else base
        if off and random.random() <= hr:
            d += dm*(gp(pc) if can and random.random() <= nat else gp(pd))
        bonus = 0
        for _i in range(2 if off else 1):
            c = random.random()
            if c < qa: bonus += 3
            elif c < ta+qa: bonus += 2
            elif c < da+ta+qa: bonus += 1
        nh = min(8, int(g('numHits',1)) + bonus)
        for _h in range(1, nh):
            if random.random() <= hr:
                d += dm*(gp(pc) if can and random.random() <= nat else gp(pd))
        tot += d*(100+s.get('wsd',0))/100
    return tot/n



def resist_ev(p):
    """Expected resist multiplier from magic hit rate p (percent), mirroring getMagicResist thresholds."""
    q = 1 - p / 100
    return (q**4 * .0625 + (q**3 - q**4) * .125 + (q**2 - q**3) * .25 + (q - q**2) * .5 + (1 - q))


def compute_magic(ws, s, tp=3000):
    """Expected damage of doMagicWeaponskill as coded in DSP (affinity/obi/day RNG ignored; day_wx is a flat % bonus input)."""
    p = ws['params']
    g = lambda k, d=0: p.get(k, d) if isinstance(p.get(k, d), (int, float)) and not isinstance(p.get(k, d), bool) else d
    fint = max(-32, min(32, 8 + s['int'] - s.get('t_int', 100)))
    wsc = sum(s[k] * g(k + '_wsc') for k in ['str', 'dex', 'vit', 'agi', 'int', 'mnd', 'chr'])
    base = s['lvl'] + 2 + wsc + fint
    f = ftp(tp, g('ftp100', 1), g('ftp200', 1), g('ftp300', 1))
    dmg = base * f
    dmg *= min(1.4, 1 + s.get('day_wx', 0) / 100)
    mab = max(0, (100 + s.get('matt', 0)) / (100 + s.get('mdef', 0)))
    dmg *= mab
    hit = max(5, min(95, 70 - 0.5 * (s.get('meva', 0) - s.get('macc', 0)) + 3 * max(-5, min(5, s['lvl'] - s['t_lvl']))))
    res = resist_ev(hit)
    total = dmg * res * (100 + s.get('wsd', 0)) / 100
    return {'total': total, 'base': base, 'fint': fint, 'ftp': f, 'mab': mab, 'magic_hit': hit, 'resist_ev': res}


def compute_ranged(ws, s, tp=3000):
    """Expected damage of doRangedWeaponskill as coded in DSP. pDIF is uniform (no melee 1.00-1.05 spread); crit applies to the
    first hit only (canCrit is a nil global in the extra-hit loop); no DA/TA/QA; ALL_WSDMG_FIRST_HIT is not modeled."""
    p = ws['params']
    g = lambda k, d=0: p.get(k, d) if isinstance(p.get(k, d), (int, float)) and not isinstance(p.get(k, d), bool) else d
    wsc = sum(s[k] * g(k + '_wsc') for k in ['str', 'dex', 'vit', 'agi', 'int', 'mnd', 'chr'])
    fs = fstr_dsp(s['str'] - s['t_vit'], s['rdmg_rank'])
    a = alpha(s['lvl'])
    base = s['rdmg'] + fs + wsc * a
    f = ftp(tp, g('ftp100', 1), g('ftp200', 1), g('ftp300', 1))
    lvlcor = 0.025 * (s['t_lvl'] - s['lvl']) if s['lvl'] < s['t_lvl'] else 0
    c = s['ratt'] / s['t_def'] - lvlcor
    c = c * (g('atkmulti', 1) or 1)
    c = max(0, min(3 - lvlcor, c))
    hi = c * 10 / 9 if c < 0.9 else 1 if c < 1.1 else c
    lo = c if c < 0.9 else 1 if c < 1.1 else c * 20 / 19 - 3 / 19
    pd, pc = (lo, hi), (lo * 1.25, hi * 1.25)
    mean = lambda r: (r[0] + r[1]) / 2
    acc = s['racc'] + 4 * (s['lvl'] - s['t_lvl'])
    raw = (75 + (acc - s['t_eva']) / 2) / 100
    hr = max(.2, min(.95, raw))
    if g('acc100'):
        lost = s['racc'] - s['racc'] * ftp(tp, g('acc100'), g('acc200'), g('acc300'))
        hr = max(.2, min(.95, raw - 0.005 * lost))
    can = bool(p.get('canCrit'))
    nat = max(.05, min(.2, (s['dex'] - s['t_agi']) * .005)) + s.get('crit_rate', 0) / 100
    cr = min(1, ftp(tp, g('crit100'), g('crit200'), g('crit300')) + nat) if can else 0
    first = hr * ((1 - cr) * mean(pd) + cr * mean(pc)) * base * f
    multi = bool(p.get('multiHitfTP'))
    later = max(0, int(g('numHits', 1)) - 1) * hr * mean(pd) * base * (f if multi else 1)
    total = (first + later) * (100 + s.get('wsd', 0)) / 100
    return {'total': total, 'base': base, 'fstr': fs, 'ftp': f, 'alpha': a, 'pdif': pd, 'pdif_crit': pc, 'hit': hr, 'crit': cr}


def compute_special(name, s, tp=3000, adoulin=False):
    """Scripts with bespoke formulas (no params). Returns amount + unit; generic WS damage mods do not apply."""
    import math
    fl = math.floor
    hp, mhp, mmp, club = s['hp'], s['max_hp'], s['max_mp'], s['club_skill']
    if name == 'spirits_within':
        if adoulin:
            w = hp if tp >= 3000 else fl(hp * .5) if tp >= 2000 else fl(hp * .125) if tp >= 1000 else 0
        elif tp >= 3000:
            w = fl(hp * 120 / 256)
        elif tp >= 2000:
            w = fl(hp * (fl(0.072 * tp) - 96) / 256)
        else:
            w = fl(hp * (fl(0.016 * tp) + 16) / 256) if tp >= 1000 else 0
        return {'total': w, 'unit': 'damage', 'parts': [('Current HP', hp)], 'note': 'Before breath-damage-taken and WS-specific mods (not modeled).'}
    if name == 'moonlight':
        return {'total': (club / 9 - 1) * ((50 + tp * 0.05) / 100), 'unit': 'MP restored (party)', 'parts': [('Club skill', club)]}
    if name == 'starlight':
        return {'total': (club - 10) / 9 * (tp / 1000), 'unit': 'MP restored (party)', 'parts': [('Club skill', club)]}
    if name == 'myrkr':
        f = ftp(tp, .2, .4, .6)
        return {'total': f * mmp, 'unit': 'MP restored', 'parts': [('fTP', f), ('Max MP', mmp)]}
    if name == 'dagan':
        fh, fm = ftp(tp, .22, .34, .52), ftp(tp, .15, .25, .35)
        return {'total': fm * mmp, 'unit': 'MP restored', 'parts': [('HP restored', fh * mhp), ('fTP HP', fh), ('fTP MP', fm), ('Max MP', mmp)]}
    return {'total': 65, 'unit': 'MP drained (fixed, TP-independent)', 'parts': []}
