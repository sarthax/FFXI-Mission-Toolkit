"""Pet gear overview (avatar / wyvern / automaton / jug / charmed), from DSP src/map: CheckPetModType (which item_mods_pet rows apply),
battleentity.cpp haste cap (HASTE_GEAR 1024 base, 256 cap), charutils::AvatarPerpetuationReduction, status_effect_container perpetuation tick,
charentity.cpp blood-pact recast (BP_DELAY, 15s max). Pet base stats are the user's own numbers; this page sums gear and shows the effect."""
from __future__ import annotations

import math

fl = math.floor

# pet kind -> PetModType values whose item_mods_pet rows apply (0 = All always applies to CPetEntity pets).
# Charmed mobs are not CPetEntity, so CheckPetModType returns true for every type.
KINDS = {
    "avatar": ("Avatar", [0, 1]),
    "wyvern": ("Wyvern", [0, 2]),
    "harlequin": ("Automaton: Harlequin Frame", [0, 3, 4]),
    "valoredge": ("Automaton: Valoredge Frame", [0, 3, 5]),
    "sharpshot": ("Automaton: Sharpshot Frame", [0, 3, 6]),
    "stormwaker": ("Automaton: Stormwaker Frame", [0, 3, 7]),
    "jug": ("Beastmaster jug pet", [0]),
    "charmed": ("Beastmaster charmed mob", [0, 1, 2, 3, 4, 5, 6, 7]),
}
AFFINITY = {"fire": "perp_fire", "earth": "perp_earth", "water": "perp_water", "wind": "perp_wind", "ice": "perp_ice",
            "thunder": "perp_thunder", "light": "perp_light", "dark": "perp_dark"}

DEFAULTS = dict(
    kind="avatar", pet_hp=3000, pet_mp=500, pet_att=900, pet_acc=900, pet_ratt=0, pet_racc=0, pet_matt=0, pet_macc=900, pet_def=900,
    pet_eva=700, pet_delay=240, pet_str=0, pet_dex=0, pet_int=0, pet_mnd=0,
    master_level=99, avatar_cost=0, element="fire", day_match=False, weather_match=False, refresh_mp=0, bp_recast=60,
    summoning_skill=0, incoming=1000)


def avatar_cost(level):
    """petutils::PerpetuationCost for the standard avatar ids 0-7."""
    for lim, c in ((19, 1), (38, 2), (57, 3), (75, 4), (81, 5), (91, 6)):
        if level < lim:
            return c
    return 7


def pet_sum(pet, kind):
    """pet: {petType(str): {key: v}} from the gear panel. Returns the merged mods applying to this pet kind."""
    out = {}
    for t in KINDS[kind][1]:
        for k, v in (pet.get(str(t)) or {}).items():
            out[k] = out.get(k, 0) + v
    return out


def _f256(x):
    return fl(256 * x / 100) / 256


def compute(c, pet, master):
    pm = pet_sum(pet, c["kind"])
    g = lambda k: pm.get(k, 0)
    # pet stats
    hp = fl(c["pet_hp"] * (1 + g("hpp") / 100) + g("hp"))
    mp = fl(c["pet_mp"] + g("mp"))
    defense = fl((c["pet_def"] + g("def")) * (1 + g("defp") / 100))
    stats = [("HP", hp), ("MP", mp), ("Attack", c["pet_att"] + g("att")), ("Accuracy", c["pet_acc"] + g("acc")),
             ("Ranged attack", c["pet_ratt"] + g("ratt")), ("Ranged accuracy", c["pet_racc"] + g("racc")),
             ("Magic attack bonus", c["pet_matt"] + g("matt")), ("Magic accuracy", c["pet_macc"] + g("macc")),
             ("Defense", defense), ("Evasion", c["pet_eva"] + g("eva")),
             ("STR", c["pet_str"] + g("str")), ("DEX", c["pet_dex"] + g("dex")), ("INT", c["pet_int"] + g("int")), ("MND", c["pet_mnd"] + g("mnd"))]
    haste = min(256, g("haste_gear"))
    delay = c["pet_delay"] * (1024 - haste) / 1024
    offense = [("Gear haste (1024 base, cap 256)", f"{g('haste_gear')} ({haste / 10.24:.1f}% effective)"),
               ("Weapon delay", f"{delay:.1f} (was {c['pet_delay']:.0f}); {60 * 60 / max(1, delay):.1f} swings/min"),
               ("Double attack %", g("da")), ("Crit rate %", g("crit_rate")), ("Store TP", g("store_tp")), ("TP bonus", g("tp_bonus")),
               ("Regain", g("regain")), ("Magic crit rate %", g("m562"))]
    taken = _taken(pm)
    sustain = [("Regen (HP/tick)", g("regen")), ("Refresh (MP/tick)", g("refresh")), ("HP while healing", g("hpheal")), ("MP while healing", g("mpheal")),
               ("Enmity", g("enmity")), ("Spell interruption down", g("spellint")), ("Fast cast", g("fastcast")), ("Cure potency %", g("cure_pot"))]
    known = {"hp", "hpp", "mp", "def", "defp", "att", "acc", "ratt", "racc", "matt", "macc", "eva", "str", "dex", "int", "mnd", "haste_gear",
             "da", "crit_rate", "store_tp", "tp_bonus", "regain", "m562", "regen", "refresh", "hpheal", "mpheal", "enmity", "spellint",
             "fastcast", "cure_pot", "dmg", "dmg_phys", "dmg_magic", "dmg_breath", "dmg_range", "dmg_magic2"}
    other = {k: v for k, v in pm.items() if k not in known and v}
    m = lambda k: master.get(k, 0)
    res = dict(kind=KINDS[c["kind"]][0], applies=KINDS[c["kind"]][1], stats=stats, offense=offense, taken=taken, sustain=sustain, other=other)
    if c["kind"] == "avatar":
        base = c["avatar_cost"] or avatar_cost(c["master_level"])
        red = m("perp_red") + m(AFFINITY.get(c["element"], "")) + (m("day_red") if c["day_match"] else 0) + (m("weather_red") if c["weather_match"] else 0)
        cost = max(1, base - red)
        res["perp"] = dict(base=base, reduction=red, cost=cost, net=m("refresh") + c["refresh_mp"] - cost, parts=[
            ("Perpetuation reduction gear", m("perp_red")), (f"{c['element']} affinity perp", m(AFFINITY.get(c["element"], ""))),
            ("Day reduction (if matching)", m("day_red") if c["day_match"] else 0), ("Weather reduction (if matching)", m("weather_red") if c["weather_match"] else 0)])
        d = min(15, m("bp_delay"))
        res["bp"] = dict(reduction=d, recast=c["bp_recast"] - d, wasted=max(0, m("bp_delay") - 15), bp2=m("bp_delay2"))
    master_rows = [(l, m(k)) for l, k in [("Summoning skill", "summoning"), ("Weather perp reduction", "weather_red"), ("Day perp reduction", "day_red"),
                   ("Charm time", "charm_time"), ("Charm chance", "charm_chance"), ("Reward HP bonus %", "reward_hp"), ("Feral Howl duration", "feral_howl"),
                   ("Jug level range", "jug_range"), ("Wyvern breath threshold", "wyvern_breath"), ("Maneuver bonus", "maneuver_bonus"),
                   ("Overload threshold", "overload_thresh"), ("Automaton decision delay", "auto_decision"), ("Shield bash delay", "auto_bash_delay"),
                   ("Magic delay", "auto_magic_delay"), ("Healing delay", "auto_heal_delay"), ("Healing threshold", "auto_heal_thresh"),
                   ("Burden decay", "burden_decay"), ("Repair effect", "repair_effect"), ("Repair potency %", "repair_potency"),
                   ("Prevent overload", "prevent_overload"), ("Store TP (master)", "store_tp")]]
    res["master"] = master_rows
    return res


def _taken(pm):
    dmg = pm.get("dmg", 0)
    rows = []
    for name, key in (("Physical", "dmg_phys"), ("Magical", "dmg_magic"), ("Breath", "dmg_breath"), ("Ranged", "dmg_range")):
        v = max(0.5, min(1.5, 1 + _f256(pm.get(key, 0)) + _f256(dmg)))
        if key == "dmg_magic":
            v = max(0.125, min(1.5, v + _f256(pm.get("dmg_magic2", 0))))
        rows.append(dict(kind=name, multiplier=v, reduction_pct=(1 - v) * 100))
    return rows
