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
AREAS = [["npc", "NPC spawns (all zones)"], ["model", "Model / name / position"], ["script", "Script / dialog"], ["keyitem", "Key item grant"],
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
     "ki": "WHITE_STRATUM_ABYSSITE", "path": "White", "role": "start", "quest": "Drafted by the Duchy", "note": "NPC name not given in the source table (it lists the quest); matched as Voidwatch_Officer."},
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


# Build notes shown in the UI: what is implemented in the Lua slice and what is still missing (kept in sync with docs/voidwatch/UNIMPLEMENTED.md)
SLICE = "voidwatch-officers-v1 (feature/voidwatch-officers, untested in-game)"
IMPL = {
    "crimson": "Officer 963 + refiner 962 scripted; kill-tracking hook not wired; tier gate approximate",
    "indigo": "Officer 9 + refiner 8 scripted; kill-tracking hook not wired; tier gate approximate",
    "jade": "Officer 1024 + refiner 1023 scripted; kill-tracking hook not wired; Jade IV has no NM",
    "white": "Not built: no npc row, csids not scanned",
    "ashen": "Not built: no capture, csids not scanned",
    "hyacinth": "Not built: no capture, csids not scanned",
    "amber": "Not built: no capture, csids not scanned",
    "hildegard": "Not built: no capture, csids not scanned",
    "gushing": "Not built: no capture, csids not scanned",
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
        ki_id = kis.get(o["ki"]) if o["ki"] else None
        status = "built" if (has_npc and has_script) else "not built"
        gaps = []
        for z in zrows:
            if not z["npcs"]:
                gaps.append("no %s npc_list row in %s" % (o["npc"], z["zone"]))
            if not z["script"]:
                gaps.append("no script scripts/zones/%s/npcs/%s.lua" % (z["zone"], o["npc"]))
        if o["ki"] and ki_id is None:
            gaps.append("key item %s not in keyitems.lua" % o["ki"])
        rec = val.get(o["id"]) or {"areas": {}, "note": "", "updated": "", "by": ""}
        out.append({**o, "status": status, "zones_live": zrows, "ki_id": ki_id, "gaps": gaps,
                    "validation": validation_status(rec), "validation_rec": rec, "impl_note": IMPL.get(o["id"], ""), "slice": SLICE if o["id"] in ("crimson", "indigo", "jade") else ""})
    return {"areas": AREAS, "states": D.STATES, "officers": out}
