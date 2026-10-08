"""Voidwatch officers: the NPCs that hand out the Stratum Abyssite and start each path. Without them no path can start.

Static facts (names, zones, grid refs, key items) come from the [W] ffxiclopedia Voidwatch Ops table the user supplied; live facts
(npc_list rows, scripts, key item constant) are read from the active DSP DB and the script checkouts.
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

from workbench.runtime.paths import REPO_ROOT
from workbench.server_admin.synth import recipes as R

from . import details as D

VALIDATION = REPO_ROOT / "data" / "voidwatch" / "officer_validation.json"
AREAS = [["npc", "NPC spawns (all zones)"], ["menu", "Menu / purchases / teleports"], ["model", "Model / name / position"], ["script", "Script / dialog"], ["keyitem", "Key item grant"],
         ["quest", "Quest flag / progression"], ["upgrade", "Abyssite upgrade turn-in"], ["ingame", "In-game test"]]

# role: start = hands out the first Stratum Abyssite; sub = sub-quest NPC (Ashen path). zones are DSP zone_settings names.
OFFICERS = [
    {"id": "crimson", "name": "Voidwatch Officer - San d'Oria", "npc": "Voidwatch_Officer", "zones": ["Southern_San_dOria", "Southern_San_dOria_[S]"], "grid": "F-9 / L-9 (S)",
     "ki": "CRIMSON_STRATUM_ABYSSITE", "path": "Crimson", "role": "start", "quest": ""},
    {"id": "indigo", "name": "Voidwatch Officer - Bastok", "npc": "Voidwatch_Officer", "zones": ["Bastok_Markets", "Bastok_Markets_[S]"], "grid": "D-11 / G-5 (S)",
     "ki": "INDIGO_STRATUM_ABYSSITE", "path": "Indigo", "role": "start", "quest": ""},
    {"id": "jade", "name": "Voidwatch Officer - Windurst", "npc": "Voidwatch_Officer", "zones": ["Windurst_Waters", "Windurst_Waters_[S]"], "grid": "G-5 / G-5 (S)",
     "ki": "JADE_STRATUM_ABYSSITE", "path": "Jade", "role": "start", "quest": ""},
    {"id": "white", "name": "Jeuno officer (Drafted by the Duchy)", "npc": "Voidwatch_Officer", "zones": ["RuLude_Gardens"], "grid": "H-6",
     "ki": "WHITE_STRATUM_ABYSSITE", "path": "White", "role": "start", "quest": "Drafted by the Duchy", "note": "Source table lists the quest, not an NPC. Actually a cutscene chain (Door:Audience Chamber / Bulwark Gate), no officer exists."},
    {"id": "ashen", "name": "Kieran - Voidwatch Ops: Border Crossing", "npc": "Kieran", "zones": ["Norg"], "grid": "I-8",
     "ki": "ASHEN_STRATUM_ABYSSITE", "path": "Ashen", "role": "start", "quest": "Voidwatch Ops: Border Crossing"},
    {"id": "hyacinth", "name": "Owain - Tavnazian Terrors", "npc": "Owain", "zones": ["Tavnazian_Safehold"], "grid": "H-6",
     "ki": "HYACINTH_STRATUM_ABYSSITE", "path": "Hyacinth", "role": "start", "quest": "Tavnazian Terrors"},
    {"id": "amber", "name": "Camille - Aht Urhgan Assault", "npc": "Camille", "zones": ["Wajaom_Woodlands"], "grid": "M-7",
     "ki": "AMBER_STRATUM_ABYSSITE", "path": "Amber", "role": "start", "quest": "Aht Urhgan Assault"},
    {"id": "hildegard", "name": "Hildegard (Kazham) - VW Op. #054 Elshimo List", "npc": "Hildegard", "zones": ["Kazham"], "grid": "F-9",
     "ki": "", "path": "Ashen", "role": "sub", "quest": "VW Op. #054: Elshimo List",
     "note": "Must be active before Holy Moly, Ildebrann and Neith count toward the Ashen upgrade; cutscene on return."},
    {"id": "gushing", "name": "Gushing Spring (Rabao) - VW Op. #101 Detour to Zepwell", "npc": "Gushing_Spring", "zones": ["Rabao"], "grid": "G-8",
     "ki": "", "path": "Ashen", "role": "sub", "quest": "VW Op. #101: Detour to Zepwell",
     "note": "Must be active before Sabotender Campeador, Tangaroa and Malleator Maurok count toward the Ashen upgrade; cutscene on return."},
]


# Other Voidwatch NPCs [W ffxiclopedia Voidwatch Officer / Voidwatch Purveyor / Atmacite Refiner / Ardrick pages, read 2026-10-08].
# zones maps zone -> wiki grid ref ("" = wiki gives none). City starting officers are tracked above.
def _npc(i, name, npc, kind, zones, note=""):
    return {"id": i, "name": name, "npc": npc, "zones": list(zones), "grid": ", ".join("%s %s" % (z, g) if g else z for z, g in zones.items()),
            "ki": "", "path": "", "role": kind, "quest": "", "note": note}


OTHER_NPCS = [
    _npc("officer_field", "Voidwatch Officer - field zones", "Voidwatch_Officer", "officer",
         {"Rolanberry_Fields": "J-5", "Sauromugue_Champaign": "F-6", "Batallia_Downs": "J-5", "Batallia_Downs_[S]": "K-8", "Qufim_Island": "I-11"},
         "Same menu as the city officers [W]: questions, Ops, debriefing, Voidstone request/stock, reward issuance; sells Cobalt/Rubicund/Xanthous Cell 3,000 cruor, "
         "Periapts, Petrifacts 330,000 cruor; converts Voiddust to Voidstone."),
    _npc("refiner_present", "Atmacite Refiner - present-day", "Atmacite_Refiner", "refiner",
         {"Southern_San_dOria": "G-9", "Bastok_Markets": "D-11", "Windurst_Waters": "G-5", "Batallia_Downs": "K-8", "Sauromugue_Champaign": "F-6",
          "Rolanberry_Fields": "", "Qufim_Island": "I-11"},
         "Enrich Atmacite (levels 1-10), upgrade Stratum Abyssite, teleport 1000 cruor to present-day Voidwatch staging points [W]."),
    _npc("refiner_past", "Atmacite Refiner - Crystal War era", "Atmacite_Refiner", "refiner",
         {"Southern_San_dOria_[S]": "L-9", "Bastok_Markets_[S]": "G-5", "Windurst_Waters_[S]": "G-5", "Batallia_Downs_[S]": "K-8",
          "Sauromugue_Champaign_[S]": "E-6", "Rolanberry_Fields_[S]": "J-5"},
         "Same functions, teleports only to [S] era destinations [W]."),
    _npc("refiner_outland", "Atmacite Refiner - Zilart/Tavnazia/Aht Urhgan", "Atmacite_Refiner", "refiner",
         {"Tavnazian_Safehold": "H-6", "Wajaom_Woodlands": "M-7", "Rabao": "G-8", "Kazham": "F-9", "Norg": "I-8"},
         "Present-day refiners next to Owain/Camille/Gushing Spring/Hildegard/Kieran."),
    _npc("purveyor_sandy", "Voidwatch Purveyor - San d'Oria", "Voidwatch_Purveyor", "purveyor",
         {"Southern_San_dOria": "K-10", "Southern_San_dOria_[S]": "", "Northern_San_dOria": "C-8"},
         "Sells Cobalt/Rubicund/Xanthous/Jade Cell 3,000 and Voiddust 2,000 for regional credit (Conquest Points / Imperial Standing / Allied Notes) [W]."),
    _npc("purveyor_bastok", "Voidwatch Purveyor - Bastok", "Voidwatch_Purveyor", "purveyor",
         {"Bastok_Mines": "H-10", "Bastok_Markets": "D-11", "Port_Bastok": "", "Bastok_Markets_[S]": "H-4"}, "Same stock as above [W]."),
    _npc("purveyor_windurst", "Voidwatch Purveyor - Windurst", "Voidwatch_Purveyor", "purveyor",
         {"Windurst_Waters": "F-5", "Windurst_Waters_[S]": "G-5", "Port_Windurst": "", "Windurst_Woods": ""}, "Same stock as above [W]."),
    _npc("purveyor_jeuno", "Voidwatch Purveyor - Jeuno", "Voidwatch_Purveyor", "purveyor",
         {"RuLude_Gardens": "H-10", "Upper_Jeuno": "F-6", "Lower_Jeuno": "", "Port_Jeuno": ""}, "Same stock as above [W]."),
    _npc("purveyor_ahturhgan", "Voidwatch Purveyor - Aht Urhgan", "Voidwatch_Purveyor", "purveyor",
         {"Al_Zahbi": "", "Aht_Urhgan_Whitegate": "I-8", "Nashmau": ""}, "Same stock as above [W]."),
    _npc("ardrick", "Ardrick (Jugner Forest)", "Ardrick", "misc", {"Jugner_Forest": "I-8"},
         "Sells Phase Displacer 20,000 gil; trade 5 Pulse Cells for Anhur Robe/Asteria/Aytanri/Borealis/Coruscanti/Delphinius/Ephemeron/Fazheluo Radiant Mail/"
         "Heka's Kalasiris/Mekira Meikogai/Mextli Harness/Murasamemaru/Toci's Harness [W]."),
]
OFFICERS = OFFICERS + OTHER_NPCS
ROLE_LABEL = {"start": "starting officer", "sub": "sub-quest NPC", "officer": "field officer", "refiner": "atmacite refiner", "purveyor": "purveyor", "misc": "other"}


# Build notes shown in the UI: what is implemented in the Lua slice and what is still missing (kept in sync with docs/voidwatch/UNIMPLEMENTED.md)
SLICE = "voidwatch-officers-v5 (feature/voidwatch-officers, untested in-game)"
IMPL = {
    "crimson": "Officer 963 + refiner 962 scripted; kill-tracking hook not wired; tier gate approximate",
    "indigo": "Officer 9 + refiner 8 scripted; kill-tracking hook not wired; tier gate approximate",
    "jade": "Officer 1024 + refiner 1023 scripted; kill-tracking hook not wired; Jade IV has no NM",
    "white": "Not an officer: quest chain Guardian of the Void -> Drafted by the Duchy (cutscenes at Veridical Conflux / Ru'Lude door / Bulwark Gate); not built, csids undecoded",
    "ashen": "Scripted from client-dat csids (Kieran event 259 + refiner 264); no capture; nation bits unknown; untested",
    "hyacinth": "Scripted from client-dat csids (Owain event 626 + refiner 627); no capture; nation bits unknown; untested",
    "amber": "Scripted from client-dat csids (Camille event 23 + refiner 24); no capture; nation bits unknown; untested",
    "hildegard": "Scripted from client-dat csids (Hildegard event 314 + refiner 316; quest flags not implemented); no capture; nation bits unknown; untested",
    "officer_field": "No field-officer scripts yet (only Bastok Markets / Southern San d'Oria / Windurst Waters have one); needs per-zone csids",
    "refiner_present": "Refiner scripts exist for Bastok Markets, Southern San d'Oria, Windurst Waters only; field zones and Qufim not scripted",
    "refiner_past": "No [S] zone scripts; [S] csids not captured",
    "refiner_outland": "Scripted from client-dat csids alongside the Owain/Camille/Gushing/Hildegard/Kieran NPCs; untested",
    "purveyor_sandy": "No Purveyor script exists anywhere; rows only", "purveyor_bastok": "No Purveyor script exists anywhere; rows only",
    "purveyor_windurst": "No Purveyor script exists anywhere; rows only", "purveyor_jeuno": "No Purveyor script exists anywhere; rows only",
    "purveyor_ahturhgan": "No Purveyor script exists anywhere; rows only",
    "ardrick": "No Ardrick script exists; row only",
    "gushing": "Scripted from client-dat csids (Gushing Spring event 14 + refiner 16; quest flags not implemented); no capture; nation bits unknown; untested",
}


def load_validation() -> dict:
    try:
        return json.loads(VALIDATION.read_text(encoding="utf-8")) if VALIDATION.exists() else {}
    except ValueError:
        return {}


def validation_status(rec) -> str:
    vals = [((rec or {}).get("areas", {})).get(k, "untested") for k, _ in AREAS]
    if "issue" in vals:
        return "issue"
    if all(v in ("ok", "n/a") for v in vals):
        return "validated"
    return "partial" if "ok" in vals else "unvalidated"


def save_validation(oid: str, areas: dict, note: str, who: str = "") -> dict:
    if not any(o["id"] == oid for o in OFFICERS):
        raise KeyError(oid)
    clean = {k: (areas.get(k) if areas.get(k) in D.STATES else "untested") for k, _ in AREAS}
    data = load_validation()
    data[oid] = {"areas": clean, "note": note[:2000], "updated": datetime.datetime.now().isoformat(timespec="seconds"), "by": who}
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    tmp = VALIDATION.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(VALIDATION)
    return data[oid]


def _ki_ids(roots) -> dict:
    out = {}
    for root in roots:
        f = root / "scripts" / "globals" / "keyitems.lua"
        if f.exists():
            for name, val in re.findall(r"^\s*([A-Z0-9_]+)\s*=\s*(\d+)", f.read_text(encoding="utf-8", errors="replace"), re.M):
                out.setdefault(name, int(val))
    return out


def overview(conn, active_root) -> dict:
    roots = D.script_roots(active_root)
    zones = {r[1]: int(r[0]) for r in R._rows(conn, "SELECT zoneid,name FROM zone_settings")}
    zones_by_id = {v: k for k, v in zones.items()}
    kis = _ki_ids(roots)
    val = load_validation()
    out = []
    for o in OFFICERS:
        zrows = []
        for z in o["zones"]:
            zid = zones.get(z)
            rows = R._rows(conn, "SELECT npcid,pos_x,pos_y,pos_z,pos_rot,flag,polutils_name FROM npc_list WHERE name=%s AND ((npcid>>12)&4095)=%s", (o["npc"], zid)) if zid is not None else []
            script = None
            for root in roots:
                p = root / "scripts" / "zones" / z / "npcs" / (o["npc"] + ".lua")
                if p.exists():
                    script = str(p)
                    break
            zrows.append({"zone": z, "zone_id": zid, "script": script,
                          "npcs": [{"npcid": int(r[0]), "x": r[1], "y": r[2], "z": r[3], "rot": r[4], "flag": r[5], "display": r[6]} for r in rows]})
        has_npc = all(z["npcs"] for z in zrows)
        has_script = all(z["script"] for z in zrows)
        expect = o["npc"].replace("_", " ")
        in_list = {zz for q in OFFICERS if q["npc"] == o["npc"] for zz in q["zones"]}
        all_rows = R._rows(conn, "SELECT npcid,polutils_name FROM npc_list WHERE name=%s", (o["npc"],))
        extra_z = sorted({zn for zn in (zones_by_id.get((int(r[0]) >> 12) & 4095) for r in all_rows) if zn and zn not in in_list})
        mism = [(int(r[0]), zones_by_id.get((int(r[0]) >> 12) & 4095), r[1]) for r in all_rows if r[1] and r[1] != expect]
        ki_id = kis.get(o["ki"]) if o["ki"] else None
        status = "built" if (has_npc and has_script) else ("partial" if any(z["npcs"] and z["script"] for z in zrows) else "not built")
        gaps = []
        for z in zrows:
            if len(z["npcs"]) > 1 and o["role"] not in ("start", "sub"):
                gaps.append("%d %s rows in %s (wiki lists one location): check for a duplicate" % (len(z["npcs"]), o["npc"], z["zone"]))
        for nid, zn, disp in mism:
            gaps.append("%s row %d in %s has polutils name '%s' but npc name %s: the name drives script lookup" % (o["npc"], nid, zn, disp, o["npc"]))
        if extra_z:
            gaps.append("%s also in the DB at zones not on the wiki list: %s" % (o["npc"], ", ".join(extra_z)))
        for z in zrows:
            if not z["npcs"]:
                gaps.append("no %s npc_list row in %s" % (o["npc"], z["zone"]))
            if not z["script"]:
                gaps.append("no script scripts/zones/%s/npcs/%s.lua" % (z["zone"], o["npc"]))
        if o["ki"] and ki_id is None:
            gaps.append("key item %s not in keyitems.lua" % o["ki"])
        rec = val.get(o["id"]) or {"areas": {}, "note": "", "updated": "", "by": ""}
        out.append({**o, "status": status, "zones_live": zrows, "ki_id": ki_id, "gaps": gaps,
                    "validation": validation_status(rec), "validation_rec": rec, "role_label": ROLE_LABEL.get(o["role"], o["role"]), "impl_note": IMPL.get(o["id"], ""), "slice": SLICE if IMPL.get(o["id"], "").find("Not built") < 0 else ""})
    return {"areas": AREAS, "states": D.STATES, "officers": out}
