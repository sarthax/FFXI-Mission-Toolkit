"""Healing / defense overview calculator, ported from DSP scripts/globals/magic.lua (getCurePower, getBaseCure, getCureFinal),
the cure*/curaga* spell scripts (tier tables snapshotted into heal_data.json by parsing them) and battleutils.cpp damage-taken clamps.
Read-only what-if. Mods are the real modifier.h ids summed by the gear panel; negative damage-taken = reduction."""
from __future__ import annotations

import json
import math
from pathlib import Path

fl = math.floor
DATA = json.loads((Path(__file__).parent / "heal_data.json").read_text(encoding="utf-8"))
EL = ["fire", "ice", "wind", "earth", "thunder", "water", "light", "dark"]
STATUS = ["sleep", "poison", "paralyze", "blind", "silence", "virus", "petrify", "bind", "curse", "gravity", "slow", "stun", "charm", "amnesia", "lullaby", "death"]
PHYS = ["slash", "pierce", "impact", "hth"]

DEFAULTS = dict(
    mnd=300, vit=120, agi=100, heal_skill=470, evasion_skill=300, base_hp=2900, base_mp=1500,
    old_formula=False, cure_power_setting=1.0,
    divine_seal=False, rapture=False, rapture_amount=0, day="light", weather="light", wx_strength="None", proc="Obi", irid=False,
    missing_hp=100000, e_macc=900, e_lvl_diff=0)


def cure_power(c, old=False):
    if old:
        return 3 * c["mnd"] + c["vit"] + 3 * fl(c["heal_skill"] / 5)
    return fl(c["mnd"] / 2) + fl(c["vit"] / 4) + c["heal_skill"]


def _tier(spell, power):
    for lim, div, const, base in spell["tiers"]:
        if lim is None or power < lim:
            return div, const, base
    return tuple(spell["tiers"][-1][1:])


def day_weather(c):
    P = 1.0 if c["proc"] == "Obi" else 0.33
    amt = {"Single": 0.1, "Double": 0.25}.get(c["wx_strength"], 0)
    w = d = 0.0
    if amt:
        if c["weather"] == "light":
            w = P * (amt + (0.1 if c["irid"] else 0))
        elif c["weather"] == "dark":
            w = -amt * P
    if c["day"] == "light":
        d = 0.1 * P
    elif c["day"] == "dark":
        d = -0.1 * P
    return min(1.4, 1 + w + d)


def cure_final(c, m, base, min_cure):
    base = max(base, min_cure)
    pot = min(1.5, 1 + min(50, m.get("cure_pot", 0)) / 100)
    f = fl(base)
    f = fl(f * pot)
    f = fl(f * day_weather(c))
    if c["rapture"]:
        f = fl(f * (1.5 + c["rapture_amount"] / 100))
    if c["divine_seal"]:
        f *= 2
    f = f + f * m.get("cure_rcvd", 0) / 100
    return f * c["cure_power_setting"]


def heals(c, m):
    out = []
    p_new, p_old = cure_power(c), cure_power(c, True)
    mx = max(1, c["base_hp"] * (1 + m.get("hpp", 0) / 100) + m.get("hp", 0))
    for name, s in DATA.items():
        if s["kind"] == "new":
            if c["old_formula"]:
                out.append(dict(spell=name, power=p_old, note="old-formula tables for Cure I-VI are not snapshotted"))
                continue
            power = p_new
            div, const, base = _tier(s, power)
            raw = (power - base) / div + const
        else:
            power = p_old
            div, const = s["div"], s["const"]
            for lim, d2, c2 in s["over"]:
                if power > lim:
                    div, const = d2, c2
                    break
            raw = (power / 2) / div + const
        fin = fl(cure_final(c, m, raw, s["min"]))
        out.append(dict(spell=name, power=power, base=raw, min=s["min"], final=fin, pct_max_hp=fin / mx * 100,
                        capped=min(fin, c["missing_hp"])))
    return out


def _f256(x):
    return fl(256 * x / 100) / 256


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def taken(m):
    """Damage-taken multipliers as battleutils applies them (UDMG* first, then DMG* + DMG clamped)."""
    dmg = m.get("dmg", 0) - m.get("dmg_neg", 0)

    def stage(key, ukey):
        u = max(0, 1 + _f256(m.get(ukey, 0)))
        v = _clamp(1 + _f256(m.get(key, 0) - m.get(key + "_neg", 0)) + _f256(dmg), 0.5, 1.5)
        return u, v

    up, pv = stage("dmg_phys", "udmg_phys")
    um, mv = stage("dmg_magic", "udmg_magic")
    ii = _clamp(mv + _f256(m.get("dmg_magic2", 0)), 0.125, 1.5)
    ub, bv = stage("dmg_breath", "udmg_breath")
    ur, rv = stage("dmg_range", "udmg_range")
    rows = [("Physical", up * pv, "DMGPHYS + DMG clamped 50-150%"),
            ("Magical", um * ii, "DMGMAGIC + DMG (50% floor), then DMGMAGIC_II (87.5% total cap)"),
            ("Breath", ub * bv, "DMGBREATH + DMG clamped 50-150%"),
            ("Ranged", ur * rv, "DMGRANGE + DMG clamped 50-150%")]
    out = [dict(kind=n, multiplier=t, reduction_pct=(1 - t) * 100, note=note) for n, t, note in rows]
    hints = []
    if 1 + _f256(m.get("dmg_phys", 0) - m.get("dmg_phys_neg", 0) + dmg) < 0.5:
        hints.append("Physical reduction is past the 50% cap; extra DMGPHYS/DMG is wasted.")
    if 1 + _f256(m.get("dmg_magic", 0) - m.get("dmg_magic_neg", 0) + dmg) < 0.5:
        hints.append("DMGMAGIC + DMG is past its 50% floor; only DMGMAGIC_II continues past it (cap 87.5% total).")
    if mv + _f256(m.get("dmg_magic2", 0)) < 0.125:
        hints.append("Magical total is past the 87.5% cap.")
    return out, hints


def defense(c, m):
    mx = c["base_hp"] * (1 + m.get("hpp", 0) / 100) + m.get("hp", 0)
    mp = c["base_mp"] * (1 + m.get("mpp", 0) / 100) + m.get("mp", 0)
    d = (8 + m.get("def", 0) + c["vit"] / 2) * (1 + m.get("defp", 0) / 100)
    sk = c["evasion_skill"]
    sk = sk if sk <= 200 else 200 + (sk - 200) * 0.9
    eva = max(0, m.get("eva", 0) + sk + c["agi"] / 2)
    keys = ["rdef", "reva", "meva", "block", "spellint", "fastcast", "ufastcast", "cure_cast", "regen", "refresh", "regain", "hpheal",
            "mpheal", "enmity", "conserve_mp", "absorb_chance", "magic_absorb", "phys_absorb"]
    r = dict(hp=fl(mx), mp=fl(mp), defense=fl(d), evasion=fl(eva), mdef=m.get("mdef_self", 0))
    r.update({k: m.get(k, 0) for k in keys})
    return r


def hit_rate(c, meva, res, extra=0):
    """applyResistanceEffect: p = clamp(70 - 0.5*(MEVA + RES - MACC) + 3*clamp(lvlDiff,-5,5) - statusRes, 5, 95)."""
    return _clamp(70 - 0.5 * (meva + res - c["e_macc"]) + 3 * _clamp(c["e_lvl_diff"], -5, 5) - extra, 5, 95)


def _ev(h):
    q = 1 - h
    return h + 0.5 * (q - q**2) + 0.25 * (q**2 - q**3) + 0.125 * (q**3 - q**4) + 0.0625 * q**4


def resists(c, m):
    meva = m.get("meva", 0)
    els = []
    for e in EL:
        r = m.get("res_" + e, 0)
        p = hit_rate(c, meva, r)
        els.append(dict(element=e, res=r, defense=m.get("def_" + e, 0), land=p, resist_ev=_ev(p / 100)))
    base = hit_rate(c, meva, 0)
    sts = [dict(status=s, res=m.get("sres_" + s, 0), land=hit_rate(c, meva, 0, m.get("sres_" + s, 0)), base_land=base) for s in STATUS]
    phys = [dict(kind=k, res=m.get("res_" + k, 0)) for k in PHYS]
    return dict(elements=els, statuses=sts, physical=phys)
