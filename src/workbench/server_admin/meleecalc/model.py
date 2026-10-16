"""Basic melee overview from DSP src/map (attack.cpp, battleentity.cpp, charutils, battleutils): attack/defense ratio, hit and crit rate, pDIF,
swings per round (double/triple/quad, dual wield, kicks), delay with haste caps, TP gain, enspells and spikes. Where the engine has no data
(mob stats, buffs, enspell cast damage) the value is the user's own input. Read-only what-if."""
from __future__ import annotations

import math

fl = math.floor
TWO_H = {4, 6, 7, 8, 10, 12}   # GSD GAX SYH POL GKT STF (item_weapon.cpp setSkillType)
H2H = 1

DEFAULTS = dict(
    wtype="auto", use_gear=True, level=99, skill=400, main_dmg=0, main_delay=0, main_hits=1, sub_dmg=0, sub_delay=0, sub_hits=1,
    base_str=100, base_dex=100, att_buff=0, attp_buff=0, acc_buff=0, haste_magic=0, haste_ability=0,
    da_trait=0, ta_trait=0, qa_trait=0, crit_trait=0, crit_dmg_trait=0, store_tp_trait=0, subtle_trait=0, dw_trait=0, regain_trait=0,
    t_level=99, t_def=1000, t_eva=1000, t_vit=100, t_agi=100, t_pc=False,
    ench=0, ench_base=0, ench_skill=0, spikes_dmg=0, mob_delay=240, mob_hit=75, ammo=False)


def _fstr(dstr, rank):
    for lim, add in ((12, 4), (6, 6), (1, 7), (-2, 8), (-7, 9), (-15, 10), (-21, 12)):
        if dstr >= lim:
            f = (dstr + add) / 2
            break
    else:
        f = (dstr + 13) / 2
    f /= 2
    return max(-rank, min(rank + 8, f))


def _base_tp(d):
    if d <= 180: return 61 + (d - 180) * 63 / 360
    if d <= 540: return 61 + (d - 180) * 88 / 360
    if d <= 630: return 149 + (d - 540) * 20 / 360
    if d <= 720: return 154 + (d - 630) * 28 / 360
    if d <= 900: return 161 + (d - 720) * 24 / 360
    return 173 + (d - 900) * 28 / 360


def _lim(c):
    """pDIF (min, max). Max is the table; the min keeps the engine's integer-division quirk (0.38-1.25 and 1.51-2.44 give cRatio)."""
    up = c + .5 if c < .5 else 1 if c < .7 else c + .3 if c < 1.2 else c * 1.25 if c < 1.5 else c + .375 if c < 2.625 else 3
    lo = 0 if c < .38 else c if c < 1.25 else 1 if c < 1.51 else c if c < 2.44 else c - .375
    return lo, up


def compute(c, g, weapon, sub):
    G = lambda k: g.get(k, 0)
    notes = []
    w = weapon if (c["use_gear"] and weapon) else None
    s = sub if (c["use_gear"] and sub) else None
    wt = c["wtype"]
    if wt == "auto":
        wt = "h2h" if (w and w.get("skill") == H2H) else "2h" if (w and w.get("skill") in TWO_H) else "dw" if s else "1h"
    mdmg = w["dmg"] if w else c["main_dmg"]; mdel = w["delay"] if w else c["main_delay"]
    mhit = max(1, int(w.get("hit", 1) if w else c["main_hits"]))
    sdmg = s["dmg"] if s else c["sub_dmg"]; sdel = s["delay"] if s else c["sub_delay"]
    shit = max(1, int(s.get("hit", 1) if s else c["sub_hits"]))
    dw = wt == "dw"; h2h = wt == "h2h"; two = wt == "2h"
    lvl = c["level"]; skill = c["skill"]
    stt = c["base_str"] + G("str"); dxx = c["base_dex"] + G("dex")
    att = (8 + G("att") + c["att_buff"] + (stt * 3 / 4 if two else stt / 2) + skill) * (1 + (G("attp") + c["attp_buff"]) / 100)
    sk = skill if skill <= 200 else 200 + 0.9 * (skill - 200)
    acc = sk + dxx * (0.75 if two else 0.5) + G("acc") + c["acc_buff"]
    hr = max(20, min(95, 75 + (acc - c["t_eva"]) / 2 + (lvl - c["t_level"]) * 2)) / 100
    cr = max(0, min(100, 5 + max(0, min(50, dxx - c["t_agi"])) * 30 / 100 + G("crit_rate") + c["crit_trait"] + G("enemy_crit"))) / 100
    cd = G("crit_dmg") + c["crit_dmg_trait"]
    ratio = max(0, min(2.25, att / max(1, c["t_def"])))
    if lvl < c["t_level"]:
        ratio = max(0, ratio - 0.05 * (c["t_level"] - lvl))
    lo, up = _lim(ratio)
    cratio = min(2.25, ratio + 1)
    clo, cup = _lim(cratio)
    k = 1 + max(0, min(100, cd)) / 100
    avg_n = (lo + up) / 2 * 1.025
    avg_c = (clo + cup) / 2 * k * 1.025
    f = _fstr(stt - c["t_vit"], (mdmg + G("main_rank")) / 9)
    base = (max(mdmg, 3) + 0.11 * skill + f) if h2h else mdmg + f
    sf = _fstr(stt - c["t_vit"], (sdmg + G("sub_rank")) / 9) if dw else 0
    sbase = sdmg + sf if dw else 0
    ocp = G("extra_dmg_chance") / 1000
    occ = 1 + ocp * (G("occ_extra_dmg") / 100 - 1) if G("occ_extra_dmg") else 1
    crit_total = 1 + cd / 100
    hit_n = base * avg_n * occ
    hit_c = base * avg_c * crit_total * occ
    per_hit = (1 - cr) * hit_n + cr * hit_c
    s_hit = (1 - cr) * sbase * avg_n * occ + cr * sbase * avg_c * crit_total * occ

    d_ = min(100, G("da") + c["da_trait"]) / 100
    t_ = min(100, G("ta") + c["ta_trait"]) / 100
    q_ = min(100, G("qa") + c["qa_trait"]) / 100
    extra = lambda n: (q_ * 3 + (1 - q_) * t_ * 2 + (1 - q_) * (1 - t_) * d_) if n == 1 else 0
    m_sw = mhit + extra(mhit)
    s_sw = (shit + extra(shit)) if dw else 0
    extra_dw_sw = min(100, G("extra_dw")) / 100 * s_sw if dw else 0
    kicks = (min(100, G("kick_attack")) / 100) * (1 + min(100, G("extra_kick")) / 100) if h2h else 0
    ammo = min(100, G("ammo_swing")) / 100 if c["ammo"] else 0
    swings = m_sw + s_sw + extra_dw_sw + kicks + ammo
    main_total = (m_sw + extra_dw_sw + ammo) * hr * per_hit
    sub_total = s_sw * hr * s_hit
    kick_dmg = kicks * hr * ((G("kick_dmg") + 3 + f) * avg_n * occ)
    dmg_round = main_total + sub_total + kick_dmg
    hits_round = swings * hr

    # delay (ms)
    d_main = (mdel - G("delay_mod")) * 1000 / 60
    base_d = mdel * 1000 / 60
    if h2h:
        d_main -= G("martial_arts") * 1000 / 60
    if dw:
        d_main += (sdel - G("delay_mod")) * 1000 / 60
        base_d = (mdel + sdel) * 1000 / 60
        d_main *= (100 - min(100, G("dual_wield") + c["dw_trait"])) / 100
    hm = min(448, G("haste_magic") + c["haste_magic"])
    ha = min(256, G("haste_ability") + c["haste_ability"])
    hg = min(256, G("haste_gear"))
    hf = (1024 - hm - ha - hg) / 1024
    dp = (100 + G("delayp")) / 100
    floor_ = 0.2 * base_d
    d_tp = max(floor_, d_main * dp)
    d_hasted = max(floor_, d_main * hf * dp)
    rounds_s = 1000 / d_hasted if d_hasted > 0 else 0
    dps = dmg_round * rounds_s

    # TP
    btp = _base_tp(d_tp * 60 / 1000) if d_tp > 0 else 0
    if dw: btp /= 2
    if h2h: btp /= 2
    stp = G("store_tp") + c["store_tp_trait"]
    tp_hit = btp * (1 + stp / 100)
    sub_mult = (100 - max(0, min(50, G("subtle_blow") + c["subtle_trait"]))) / 100
    tp_round = tp_hit * hits_round
    reg = G("regain") + c["regain_trait"]
    tp_s = tp_round * rounds_s + reg / 3
    tp_taken = (btp / 3) * sub_mult if c["t_pc"] else (btp + 30) * sub_mult

    # enspell / spikes
    chance = (G("enspell_chance") or 100) / 100
    if c["ench"] == 1:
        e_hit = c["ench_base"] + G("enspell_bonus")
        e_round = e_hit * chance * hits_round
    elif c["ench"] == 2:
        sk2 = c["ench_skill"]
        e_hit = 2 * (5 + 5 * sk2 / 100) if sk2 > 200 else 2 * (3 + 6 * sk2 / 100)
        e_round = e_hit * chance * hr
        notes.append("Enspell tier 2 procs on the first swing only; the cap value is the upper estimate.")
    else:
        e_hit = e_round = 0
    sp_dmg = c["spikes_dmg"] + G("item_spikes_dmg")
    sp_ps = (60 / max(1, c["mob_delay"])) * (c["mob_hit"] / 100)
    sp_ch = G("item_spikes_chance") / 100 if G("item_spikes_dmg") and not c["spikes_dmg"] else 1

    notes += ["Crit damage is applied twice by this engine (once in pDIF, capped at +100%, and again uncapped in attack.cpp); both are modeled.",
              "The pDIF minimum keeps the engine's integer-division quirk (min equals cRatio over 0.38-1.25 and 1.51-2.44).",
              "The DELAY mod unit is assumed to be 1/60 s ticks (unverified). The MAX_ATTACKS cap, double and triple damage multipliers and counter damage are not modeled.",
              "Dual wield off-hand swings use the same hit and crit rate as the main hand."]
    return dict(
        setup=dict(wtype=wt, main=[mdmg, mdel, mhit], sub=[sdmg, sdel, shit] if dw else None),
        summary=[("Damage per second", dps + e_round * rounds_s), ("Damage per round", dmg_round + e_round), ("TP per second", tp_s)],
        stats=[("STR", stt), ("DEX", dxx), ("Attack", att), ("Accuracy", acc), ("Ratio (att/def, capped 2.25)", ratio), ("fSTR", f)],
        hits=[("Hit rate %", hr * 100), ("Crit rate %", cr * 100), ("Crit damage mod %", cd), ("pDIF min-max", f"{lo:.2f}-{up:.2f}"),
              ("Crit pDIF min-max (before crit mod)", f"{clo:.2f}-{cup:.2f}"), ("Avg normal hit", hit_n), ("Avg crit hit", hit_c),
              ("Avg hit (crit weighted)", per_hit), ("Occasional extra damage mult", occ)],
        swings=[("Double attack %", d_ * 100), ("Triple attack %", t_ * 100), ("Quad attack %", q_ * 100), ("Main hand swings", m_sw),
                ("Off hand swings", s_sw), ("Extra dual wield swings", extra_dw_sw), ("Kick swings", kicks), ("Ammo swings", ammo),
                ("Swings per round", swings), ("Hits per round", hits_round)],
        delay=[("Base delay (ms)", base_d), ("Delay after dual wield (ms)", d_main), ("Haste factor (magic+ability+gear)", hf),
               ("Final delay (ms)", d_hasted), ("Rounds per second", rounds_s), ("Delay floor 20% (ms)", floor_)],
        tp=[("Base TP per hit", btp), ("Store TP %", stp), ("TP per hit", tp_hit), ("TP per round", tp_round), ("Regain (per 3s tick)", reg),
            ("TP per second", tp_s), ("Seconds to 1000 TP", 1000 / tp_s if tp_s else 0), ("Subtle blow multiplier", sub_mult),
            ("TP the target gains per hit", tp_taken)],
        magic=[("Enspell tier", c["ench"]), ("Enspell damage per hit", e_hit), ("Enspell damage per round", e_round), ("Enspell bonus mod", G("enspell_bonus")),
               ("Enspell proc chance %", chance * 100), ("Spike damage", sp_dmg), ("Spike procs per second", sp_ps * sp_ch if sp_dmg else 0),
               ("Spike damage per second", sp_dmg * sp_ps * sp_ch), ("Counter", G("counter")), ("Zanshin", G("zanshin"))],
        notes=notes,
        other={kk: v for kk, v in g.items() if kk in ("da_double", "ta_triple", "zanshin_double", "samba_double", "wsacc", "item_spikes_type", "main_rating", "sub_rating") and v})
