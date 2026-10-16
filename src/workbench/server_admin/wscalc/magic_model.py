"""Port of the DSP elemental / ninjutsu nuke calculators (magic-wsc-analysis/build_calc.py, build_nin.py).
Every step is floored like the engine. Expected value over the resist roll; day/weather procs are obi (always) or averaged."""
from __future__ import annotations

import json
from pathlib import Path

E8 = ['fire', 'ice', 'wind', 'earth', 'lightning', 'water', 'light', 'dark']
OPP = {'fire': 'water', 'ice': 'fire', 'wind': 'ice', 'earth': 'wind', 'lightning': 'earth', 'water': 'lightning',
       'light': 'dark', 'dark': 'light'}
NIN = [('katon', 'fire'), ('hyoton', 'ice'), ('huton', 'wind'), ('doton', 'earth'), ('raiton', 'lightning'), ('suiton', 'water')]
TIER = [('ichi', 28, 0.5, 50), ('ni', 69, 1, 125), ('san', 134, 1.5, 275)]
NIN_SPELLS = [dict(name=f'{n}_{t}', element=e, dmg=d, mult=mu, offset=off, tier=t) for n, e in NIN for t, d, mu, off in TIER]

_data = json.loads((Path(__file__).parent / 'magic_data.json').read_text(encoding='utf-8'))
NUKES = {s['name']: s for s in _data['nuke']}
NINS = {s['name']: s for s in NIN_SPELLS}
MOBS = {m['family']: m for m in _data['mobs']}

DEFAULTS = dict(
    int=390, matt=30, macc=300, lvl=90, t_lvl=90, int_pp=8, matt_pp=8, macc_pp=8, mdmg_pp=15, aff_pp=5, burst_pp=4,
    skill_pp=7, aff_cap=20, enforce_cap=True, nm=False, nm_mult=1.5, meva=328, mdef=0, burst_step=3, resist_factor=0.4,
    C=0, F=4, G=12, t_int=None, nin_main=True, nin_skill=400, futae=False, extra_mab=0, engine='As coded',
    day='fire', weather='fire', wx_strength='Double', proc='Obi', irid=False, day_bonus=0, aff_el='Any', macc_per_aff=1,
    prev='None', mdmg_flat=0, burst_flat=0, skill_flat=0, aff_gear={}, aff_flat=0, nin_mab_gear=0, nin_macc_gear=0)


def _wx(el, c):
    P = 1.0 if c['proc'] == 'Obi' else 0.33
    IR = 0.1 if c['irid'] else 0.0
    w = 0.0
    amt = {'Single': 0.1, 'Double': 0.25}.get(c['wx_strength'])
    if amt:
        if c['weather'] == el:
            w = P * (amt + IR)
        elif c['weather'] == OPP[el]:
            w = -amt * P
    d = 0.0
    if c['day'] == el:
        d = c['day_bonus'] / 100 + P * 0.1
    elif c['day'] == OPP[el]:
        d = -0.1 * P
    return min(1.4, 1 + w + d)


def _resist_ev(h):
    q = 1 - h
    return h + 0.5 * (q - q**2) + 0.25 * (q**2 - q**3) + 0.125 * (q**3 - q**4) + 0.0625 * q**4


def _common(c, mix, el, mob):
    Cn, Fn, Gn = mix
    N = Cn + Fn + Gn
    aff_raw = Fn * c['aff_pp'] + c['aff_gear'].get(el, 0) * 5
    aff = (min(aff_raw, c['aff_cap']) if c['enforce_cap'] else aff_raw) * (1 if c['aff_el'] in ('Any', el) else 0)
    t_int = c['t_int'] if c['t_int'] is not None else (mob['int'] if mob else 0)
    if c['nm']:
        t_int *= c['nm_mult']
    fam = (mob['res'][E8.index(el)] if mob else 1.0)
    res = (fam - 1) * -100
    return dict(N=N, aff=aff, t_int=t_int, res=res, INT=c['int'] + c['int_pp'] * N, matt=c['matt'] + c['matt_pp'] * N,
                macc=c['macc'] + c['macc_pp'] * N + aff * c['macc_per_aff'])


def calc_nuke(spell, c, mix, mob):
    s = NUKES[spell]
    el = s['element']
    k = _common(c, mix, el, mob)
    macc = k['macc'] + c['skill_pp'] * mix[0] + c['skill_flat']
    dint = k['INT'] - k['t_int']
    t = 0 if dint <= 49 else 1 if dint <= 99 else 2 if dint <= 199 else 3
    V, M, off = s['V'][t], s['M'][t], (0, 50, 100, 200)[t]
    base = max(0, int(c['mdmg_pp'] * k['N'] + c['mdmg_flat'] + V + (dint - off) * M))
    h = max(5, min(95, 70 - 0.5 * (c['meva'] + k['res'] - macc))) / 100
    d = int(base * (h + (1 - h) * c['resist_factor']))
    d = int(d * (1 + 0.05 * k['aff']))
    wx = _wx(el, c)
    d = int(d * wx)
    if c['burst_step'] > 0:
        d = int(d * (1.3 + 0.05 * (c['burst_step'] - 1) + (mix[2] * c['burst_pp'] + c['burst_flat']) / 100))
    final = int(d * (100 + k['matt']) / (100 + c['mdef']))
    return dict(spell=spell, element=el, cls=s['cls'], tier=s['tier'], INT=k['INT'], t_int=k['t_int'], dint=dint,
                base=base, macc=macc, hit=h, wx=wx, aff=k['aff'], mab=k['matt'], final=final)


def calc_nin(spell, c, mix, mob):
    s = NINS[spell]
    el = s['element']
    k = _common(c, mix, el, mob)
    res = k['res']
    if c['prev'] != 'None' and OPP.get(c['prev']) == el:
        res -= 30
    dint = k['INT'] - k['t_int']
    mult = s['mult']
    if dint <= 0:
        base = max(0, s['dmg'] + dint)
    elif dint <= 60:
        base = s['dmg'] + dint * mult
    elif dint < 120:
        base = s['dmg'] + 60 * mult + (dint - 60) * mult / 2
    else:
        base = s['dmg'] + 120 * mult
    macc = k['macc'] + c['nin_macc_gear'] + (10 + (dint - 10) / 2 if dint > 10 else dint) + (25 if c['burst_step'] > 0 else 0)
    h = max(5, min(95, 70 - 0.5 * (c['meva'] + res - macc) + 3 * max(-5, min(5, c['lvl'] - c['t_lvl'])))) / 100
    d = base * _resist_ev(h)
    intended = c['engine'] == 'Intended'
    if intended:
        if c['nin_main']:
            d *= min(200, max(100, 100 + int((c['nin_skill'] - s['offset']) / 2))) / 100
        if c['futae']:
            d *= 1.5
    d = int(d * (1 + 0.05 * k['aff']))
    wx = _wx(el, c)
    d = int(d * wx)
    if c['burst_step'] > 0:
        d = int(d * (1.3 + 0.05 * (c['burst_step'] - 1) + (mix[2] * c['burst_pp'] + c['burst_flat']) / 100))
    mab = k['matt'] + c['nin_mab_gear'] + (c['extra_mab'] if intended else 0)
    final = int(d * (100 + mab) / (100 + c['mdef']))
    return dict(spell=spell, element=el, cls='Ninjutsu', tier=s['tier'], INT=k['INT'], t_int=k['t_int'], dint=dint,
                base=base, macc=macc, hit=h, wx=wx, aff=k['aff'], mab=mab, final=final)


MIXES = [('No augments', 0, 0, 0), ('All C', 16, 0, 0), ('All F', 0, 16, 0), ('All G', 0, 0, 16),
         ('4F + 12G', 0, 4, 12), ('4F + 12C', 12, 4, 0), ('8F + 8G', 0, 8, 8)]
