"""Virtual gear loadout for the calculators (read-only; nothing is written to any character).

Item data comes from the active server's DB (item_armor / item_weapon / item_mods / item_basic), augments from
augments (+ sql/augments.sql names). Augment effect follows CItemArmor::SetAugmentMod:
    mod = (value > 0 ? value + stored : value - stored) * (multiplier > 1 ? multiplier : 1)
Latent / conditional item mods are NOT counted (only unconditional item_mods)."""
from __future__ import annotations

from pathlib import Path

from . import presets as _presets
from workbench.editors.character.equipment_augments import (AUGMENT_SLOTS, EQUIP_SLOTS, _friendly, _mod_names,
                                                           augment_catalog)

# modifier.h ids -> calculator stat keys (ws_calc stats / magic_calc extras)
MOD_STAT = {8: "str", 9: "dex", 10: "vit", 11: "agi", 12: "int", 13: "mnd", 14: "chr", 23: "att", 25: "acc", 24: "ratt", 26: "racc",
            28: "matt", 30: "macc", 165: "crit_rate", 421: "crit_dmg", 288: "da", 302: "ta", 430: "qa",
            840: "wsd", 311: "mdmg", 487: "burst", 115: "elem_skill", 118: "nin_skill", 29: "mdef_self"}
DEF_STAT = {1: 'def', 63: 'defp', 2: 'hp', 3: 'hpp', 5: 'mp', 6: 'mpp', 68: 'eva', 69: 'rdef', 70: 'reva', 31: 'meva', 112: 'heal_skill', 27: 'enmity', 296: 'conserve_mp', 160: 'dmg', 161: 'dmg_phys', 162: 'dmg_breath', 163: 'dmg_magic', 164: 'dmg_range', 831: 'dmg_magic2', 387: 'udmg_phys', 388: 'udmg_breath', 389: 'udmg_magic', 390: 'udmg_range', 168: 'spellint', 170: 'fastcast', 407: 'ufastcast', 519: 'cure_cast', 370: 'regen', 369: 'refresh', 368: 'regain', 71: 'mpheal', 72: 'hpheal', 838: 'regen_mult', 374: 'cure_pot', 375: 'cure_rcvd', 518: 'block', 480: 'absorb_chance', 475: 'magic_absorb', 512: 'phys_absorb', 516: 'absorb_mp', 54: 'res_fire', 15: 'def_fire', 55: 'res_ice', 16: 'def_ice', 56: 'res_wind', 17: 'def_wind', 57: 'res_earth', 18: 'def_earth', 58: 'res_thunder', 19: 'def_thunder', 59: 'res_water', 20: 'def_water', 60: 'res_light', 21: 'def_light', 61: 'res_dark', 22: 'def_dark', 49: 'res_slash', 50: 'res_pierce', 51: 'res_impact', 52: 'res_hth', 240: 'sres_sleep', 241: 'sres_poison', 242: 'sres_paralyze', 243: 'sres_blind', 244: 'sres_silence', 245: 'sres_virus', 246: 'sres_petrify', 247: 'sres_bind', 248: 'sres_curse', 249: 'sres_gravity', 250: 'sres_slow', 251: 'sres_stun', 252: 'sres_charm', 253: 'sres_amnesia', 254: 'sres_lullaby', 255: 'sres_death'}
MOD_STAT.update(DEF_STAT)
MASTER_STAT = {117: 'summoning', 346: 'perp_red', 357: 'bp_delay', 541: 'bp_delay2', 372: 'weather_red', 373: 'day_red', 553: 'perp_fire', 554: 'perp_earth', 555: 'perp_water', 556: 'perp_ice', 557: 'perp_thunder', 558: 'perp_wind', 559: 'perp_light', 560: 'perp_dark', 360: 'charm_time', 364: 'reward_hp', 391: 'charm_chance', 503: 'feral_howl', 564: 'jug_range', 504: 'maneuver_bonus', 505: 'overload_thresh', 842: 'auto_decision', 843: 'auto_bash_delay', 844: 'auto_magic_delay', 845: 'auto_heal_delay', 846: 'auto_heal_thresh', 847: 'burden_decay', 848: 'auto_bash_slow', 849: 'auto_tp_eff', 850: 'auto_scan', 853: 'repair_effect', 854: 'repair_potency', 855: 'prevent_overload', 829: 'wyvern_breath', 73: 'store_tp', 384: 'haste_gear', 345: 'tp_bonus'}
MOD_STAT.update(MASTER_STAT)
MELEE_STAT = {62: 'attp', 259: 'dual_wield', 289: 'subtle_blow', 171: 'delay_mod', 380: 'delayp', 173: 'martial_arts', 292: 'kick_attack', 386: 'kick_dmg', 481: 'extra_dw', 482: 'extra_kick', 306: 'zanshin', 291: 'counter', 432: 'enspell_bonus', 856: 'enspell_chance', 506: 'extra_dmg_chance', 507: 'occ_extra_dmg', 523: 'ammo_swing', 408: 'da_double', 409: 'ta_triple', 410: 'zanshin_double', 415: 'samba_double', 377: 'main_rank', 378: 'sub_rank', 366: 'main_rating', 367: 'sub_rating', 499: 'item_spikes_type', 500: 'item_spikes_dmg', 501: 'item_spikes_chance', 48: 'wsacc', 166: 'enemy_crit', 167: 'haste_magic', 383: 'haste_ability'}
MOD_STAT.update(MELEE_STAT)
AFF_DMG = {347: "fire", 348: "earth", 349: "water", 350: "ice", 351: "lightning", 352: "wind", 353: "light", 354: "dark"}
AFF_ACC = {544: "fire", 545: "earth", 546: "water", 547: "ice", 548: "lightning", 549: "wind", 550: "light", 551: "dark"}
STAT_LABEL = {"str": "STR", "dex": "DEX", "vit": "VIT", "agi": "AGI", "int": "INT", "mnd": "MND", "chr": "CHR",
              "att": "Attack", "acc": "Accuracy", "ratt": "Ranged Attack", "racc": "Ranged Accuracy", "matt": "Magic Atk Bonus", "macc": "Magic Accuracy",
              "crit_rate": "Crit rate %", "crit_dmg": "Crit dmg %", "da": "Double Attack %", "ta": "Triple Attack %",
              "qa": "Quad Attack %", "wsd": "WS damage % (all hits)", "mdmg": "Magic Damage", "burst": "Magic Burst Bonus %",
              "elem_skill": "Elemental skill", "nin_skill": "Ninjutsu skill", "mdef_self": "Magic Def Bonus", "aff_all": "Magic Affinity (all elements)",
              "nin_mab": "Ninjutsu DMG (= NIN_NUKE_BONUS, extra MAB)", "nin_macc": "Ninjutsu Mag.Acc.", "cure_pot": "Cure Potency %", "cure_rcvd": "Cure Potency Received %", "heal_skill": "Healing Magic skill", "meva": "Magic Evasion", "def": "Defense", "eva": "Evasion", "hp": "HP", "mp": "MP"}


def _q(conn, sql, args=()):
    cur = conn.cursor()
    try:
        cur.execute(sql, args)
        return cur.fetchall() or []
    finally:
        cur.close()


def slots() -> list[str]:
    return list(EQUIP_SLOTS)


def search(conn, slot: int, text: str, limit: int = 60) -> list[dict]:
    """Items that fit EQUIP_SLOTS[slot], by name (item_armor.slot bit = slot index; weapons have a row there too)."""
    like = f"%{text.strip().replace(' ', '_')}%"
    rows = _q(conn, "SELECT a.itemId, COALESCE(NULLIF(b.sortname,''), a.name), a.level, a.ilevel FROM item_armor a "
                    "LEFT JOIN item_basic b ON b.itemid=a.itemId WHERE (a.slot & %s) <> 0 AND (a.name LIKE %s OR b.sortname LIKE %s) "
                    "ORDER BY a.level DESC, a.name LIMIT %s", (1 << slot, like, like, int(limit)))
    return [{"id": int(i), "name": str(n).replace("_", " "), "level": int(lv or 0), "ilevel": int(il or 0)} for i, n, lv, il in rows]


def augment_options(root) -> list[dict]:
    cat = augment_catalog(root)
    out = []
    for r in cat["rows"]:
        eff = [e for e in r["effects"]]
        label = ", ".join(f"{e['mod_name']}{' (pet)' if e['pet'] else ''}" + (f" x{e['multiplier']}" if e["multiplier"] > 1 else "") + f" {e['value']:+d}" for e in eff)
        out.append({"id": r["id"], "label": label, "effects": eff})
    return out


def item_info(conn, item_id: int) -> dict:
    mods = _q(conn, "SELECT modId, value FROM item_mods WHERE itemId=%s", (item_id,))
    wp = _q(conn, "SELECT skill, dmg, delay, hit, dmgType FROM item_weapon WHERE itemId=%s", (item_id,))
    return {"mods": [(int(m), int(v)) for m, v in mods], "weapon": ({"skill": int(wp[0][0]), "dmg": int(wp[0][1]), "delay": int(wp[0][2]), "hit": int(wp[0][3]), "dmg_type": int(wp[0][4])} if wp else None)}


def totals(conn, root, loadout: list[dict]) -> dict:
    """loadout: [{slot, item, augments:[{id, value}]}]. Returns summed stats, affinity, weapon info and a per-slot breakdown."""
    root = Path(root) if root else None
    names = _mod_names(root)
    aug = {a["id"]: a for a in augment_options(root)}
    stat: dict[str, float] = {}
    aff_dmg: dict[str, float] = {}
    aff_acc: dict[str, float] = {}
    other: dict[int, float] = {}
    weapon = None
    sub_weapon = None
    ranged_dmg = {}
    pet: dict[int, dict[str, float]] = {}
    pet_names: dict[str, str] = {}
    per_slot = []

    def add_pet(ptype: int, mod: int, v: float):
        k = MOD_STAT.get(mod) or f"m{mod}"
        pet.setdefault(int(ptype), {})[k] = pet.setdefault(int(ptype), {}).get(k, 0) + v
        pet_names[k] = STAT_LABEL.get(k) or _friendly(names.get(mod, (None, ''))[0], mod)

    def add(mod: int, v: float):
        if mod in MOD_STAT:
            k = MOD_STAT[mod]
            stat[k] = stat.get(k, 0) + v
        elif mod in AFF_DMG:
            aff_dmg[AFF_DMG[mod]] = aff_dmg.get(AFF_DMG[mod], 0) + v
        elif mod in AFF_ACC:
            aff_acc[AFF_ACC[mod]] = aff_acc.get(AFF_ACC[mod], 0) + v
        else:
            other[mod] = other.get(mod, 0) + v

    for ent in loadout or []:
        item = int(ent.get("item") or 0)
        if not item:
            continue
        info = item_info(conn, item)
        lines = []
        for mod, v in info["mods"]:
            add(mod, v)
            lines.append(f"{_friendly(names.get(mod, (None, ''))[0], mod)} {v:+d}")
        for mod, v, ptype in _q(conn, "SELECT modId, `value`, petType FROM item_mods_pet WHERE itemId=%s", (item,)):
            add_pet(ptype, int(mod), int(v))
            lines.append(f"pet({ptype}): {_friendly(names.get(int(mod), (None, ''))[0], int(mod))} {int(v):+d}")
        pre = _presets.by_id().get(ent.get("preset") or "")
        if pre:
            for k, v in pre["effects"].items():
                stat[k] = stat.get(k, 0) + v
                lines.append(f"aug: {STAT_LABEL.get(k, k)} {v:+d}")
            lines += [f"aug (not modeled): {l['text']}" for l in pre["lines"] if not l["modeled"]]
        for a in ([] if pre else (ent.get("augments") or [])[:AUGMENT_SLOTS]):
            aid, stored = int(a.get("id") or 0), max(0, min(31, int(a.get("value") or 0)))
            if not aid or aid not in aug:
                continue
            for e in aug[aid]["effects"]:
                v = e["value"]
                v = (v + stored if v > 0 else v - stored) * (e["multiplier"] if e["multiplier"] > 1 else 1)
                if e["pet"]:
                    add_pet(e.get("pet_type", 0), e["mod"], v)
                    lines.append(f"aug pet({e.get('pet_type', 0)}): {e['mod_name']} {v:+d}")
                    continue
                add(e["mod"], v)
                lines.append(f"aug: {e['mod_name']} {v:+d}")
        if info["weapon"] and int(ent.get("slot", -1)) == 0:
            weapon = info["weapon"]
        if info["weapon"] and int(ent.get("slot", -1)) == 1:
            sub_weapon = info["weapon"]
        if info["weapon"] and int(ent.get("slot", -1)) in (2, 3):
            ranged_dmg[int(ent["slot"])] = info["weapon"]["dmg"]
        per_slot.append({"slot": int(ent.get("slot", -1)), "item": item, "lines": lines})
    return {"stats": stat, "aff_dmg": aff_dmg, "aff_acc": aff_acc, "weapon": weapon, "sub_weapon": sub_weapon, "rdmg": sum(ranged_dmg.values()) if ranged_dmg else None, "per_slot": per_slot, "pet": pet, "pet_names": pet_names,
            "other": [{"mod": m, "name": _friendly(names.get(m, (None, ''))[0], m), "value": v} for m, v in sorted(other.items())],
            "labels": STAT_LABEL}
