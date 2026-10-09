"""Voidwatch NM dossiers: tracker + live DSP database + the DSP checkout's own Lua, plus path/progression data.

Read-only. Sources, in order of authority: the active DSP server database (what the game actually loads), the DSP checkout's
scripts (what the NM does), then the NM tracker (build status / gaps). Wiki-derived progression rules are labelled [W] and
are reference only. Topaz and LSB are never read here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from workbench.runtime.paths import REPO_ROOT
from workbench.server_admin.synth import recipes as R

TRACKER = REPO_ROOT / "data" / "voidwatch" / "nm_tracker.json"
# Extra DSP checkouts that hold Voidwatch feature work not yet in the active root. DSP-family only.
EXTRA_DSP_ROOTS = [Path(r"D:\Claude\dsp-branches")]

VALIDATION = REPO_ROOT / "data" / "voidwatch" / "nm_validation.json"
AREAS = [["spawns", "Spawns"], ["model", "Model / look"], ["hp", "HP / stats"], ["skills", "Skills"], ["spells", "Spells"], ["drops", "Drops"], ["weakness", "Weakness / stagger"], ["rift", "Rift / entry"], ["ingame", "In-game test"]]
STATES = ["untested", "ok", "issue", "n/a"]

TIERS = ["I", "II", "III", "IV", "V", "VI"]
# [W] BG Wiki digest (docs/voidwatch/research/WIKI-MECHANICS-DIGEST.md): reference only, not server truth.
PATHS = {
    "Crimson": {"officer": "San d'Oria Voidwatch Officer", "region": "THREE", "unlock": "Voidwatch Officer in San d'Oria (incl. [S] city)", "color": "#c0392b",
                "advance": {"I>II": "Atmacite Refiner", "II>III": "unknown", "III>IV": "unknown"}},
    "Indigo": {"officer": "Bastok Voidwatch Officer", "region": "THREE", "unlock": "Voidwatch Officer in Bastok (incl. [S] city)", "color": "#5b4bb5",
               "advance": {"I>II": "Atmacite Refiner", "II>III": "unknown", "III>IV": "unknown"}},
    "Jade": {"officer": "Windurst Voidwatch Officer", "region": "THREE", "unlock": "Voidwatch Officer in Windurst (incl. [S] city)", "color": "#1e9e6a",
             "advance": {"I>II": "Atmacite Refiner", "II>III": "unknown", "III>IV": "unknown"}},
    "White": {"officer": "Voidwatch Officer (quest)", "region": "unknown", "unlock": "Quest 'Drafted by the Duchy' after all three city paths", "color": "#8a97a8",
              "advance": {"I>II": "Atmacite Refiner", "II>III": "quest", "III>IV": "quest", "IV>V": "Atmacite Refiner", "V>VI": "quest"}},
    "Ashen": {"officer": "Kieran (Norg)", "region": "unknown", "unlock": "Kieran in Norg", "color": "#7a6a5a", "advance": {}},
}
EDGE_UNLOCKS = [["Crimson", "White"], ["Indigo", "White"], ["Jade", "White"]]


def load_tracker() -> list[dict]:
    return json.loads(TRACKER.read_text(encoding="utf-8")) if TRACKER.exists() else []


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-']+", " ", s.lower()).strip()


def script_name(nm: str) -> str:
    return re.sub(r"[\s\-']+", "_", nm)


def script_roots(active_root) -> list[Path]:
    roots = []
    for r in [active_root] + EXTRA_DSP_ROOTS:
        if r and Path(r).exists() and Path(r) not in roots:
            roots.append(Path(r))
    return roots


def find_script(roots, nm: str, zone_id=None):
    want = script_name(nm) + ".lua"
    for root in roots:
        for p in (root / "scripts" / "zones").glob("*/mobs/" + want):
            return root, p
    return None, None


def parse_lua(text: str) -> dict:
    out: dict = {}
    head = []
    for line in text.splitlines()[:12]:
        if line.startswith("--"):
            head.append(line.lstrip("- ").strip())
    out["header"] = [h for h in head if h]
    m = re.search(r"drops\s*=\s*\{([^}]*)\}", text)
    out["drops"] = [int(x) for x in re.findall(r"\d+", m.group(1))] if m else []
    m = re.search(r"dropRates\s*=\s*\{(.*?)\}", text, re.S)
    out["drop_rates"] = [[int(a), float(b)] for a, b in re.findall(r"\[?\s*(\d+)\s*\]?\s*=\s*([\d.]+)", m.group(1))] if m else []
    for key in ("region", "stage"):
        m = re.search(key + r'\s*=\s*"?([A-Za-z0-9]+)"?', text)
        out[key] = m.group(1) if m else ""
    m = re.search(r"\bLIMIT\s*=\s*(\d+)", text)
    out["time_limit_s"] = int(m.group(1)) if m else None
    out["mods"] = [{"call": c, "mod": a.strip(), "value": v.strip()} for c, a, v in re.findall(r"mob:(setMod|setMobMod)\(\s*([A-Za-z_0-9]+)\s*,\s*([^)]*)\)", text)]
    out["hooks"] = sorted(set(re.findall(r"^function\s+(on[A-Za-z]+)", text, re.M)))
    out["key_items"] = sorted(set(re.findall(r"addKeyItem\(\s*([A-Z_0-9]+)", text)))
    out["spell_picks"] = [x.strip() for x in re.findall(r"vwPick\([^,]+,[^,]+,\s*([^)]*)\)", text)]
    out["tags"] = {t: len(re.findall(r"\[" + t + r"[,\]\s]", text)) for t in ("C", "J", "F", "B", "D", "W", "U", "V")}
    out["tags"] = {k: v for k, v in out["tags"].items() if v}
    return out


def _item_names(conn, ids):
    ids = sorted({int(i) for i in ids if i})
    if not ids:
        return {}
    rows = R._rows(conn, f"SELECT itemid,name FROM item_basic WHERE itemid IN ({','.join(['%s'] * len(ids))})", tuple(ids))
    return {int(r[0]): r[1] for r in rows}


def _rows_dict(conn, sql, params=()):
    return R._rows(conn, sql, params)


def find_pools(conn, nm: str):
    rows = _rows_dict(conn, "SELECT poolid,name,packet_name,familyid,skill_list_id,spellList,mobType,immunity,behavior,aggro,true_detection,links,mJob,sJob,cmbDelay,cmbDmgMult,flag,entityFlags FROM mob_pools "
                            "WHERE REPLACE(REPLACE(REPLACE(LOWER(name),'_',' '),'-',' '),'''',' ')=%s", (_norm(nm),))
    return rows


COLS_POOL = ["poolid", "name", "packet_name", "familyid", "skill_list_id", "spellList", "mobType", "immunity", "behavior", "aggro", "true_detection", "links", "mJob", "sJob", "cmbDelay", "cmbDmgMult", "flag", "entityFlags"]
FAM_COLS = ["family", "system", "HP", "MP", "STR", "DEX", "VIT", "AGI", "INT", "MND", "CHR", "ATT", "DEF", "ACC", "EVA"]
RES = ["Slash", "Pierce", "H2H", "Impact", "Fire", "Ice", "Wind", "Earth", "Lightning", "Water", "Light", "Dark"]


def nm_detail(conn, active_root, nm: str) -> dict:
    tr = next((x for x in load_tracker() if x["name"].lower() == nm.lower()), None)
    if tr is None:
        raise KeyError(nm)
    d: dict = {"name": tr["name"], "tracker": tr, "pools": []}
    for row in find_pools(conn, tr["name"]):
        pool = dict(zip(COLS_POOL, row))
        pool["modelid"] = None
        pid = int(pool["poolid"])
        groups = _rows_dict(conn, "SELECT groupid,poolid,zoneid,respawntime,spawntype,dropid,HP,MP,minLevel,maxLevel,allegiance FROM mob_groups WHERE poolid=%s", (pid,))
        pool["groups"] = [dict(zip(["groupid", "poolid", "zoneid", "respawntime", "spawntype", "dropid", "HP", "MP", "minLevel", "maxLevel", "allegiance"], g)) for g in groups]
        for g in pool["groups"]:
            sp = _rows_dict(conn, "SELECT mobid,pos_x,pos_y,pos_z,pos_rot FROM mob_spawn_points WHERE groupid=%s", (g["groupid"],))
            g["spawns"] = [dict(zip(["mobid", "x", "y", "z", "rot"], s)) for s in sp]
            g["drops"] = []
            if g["dropid"]:
                dr = _rows_dict(conn, "SELECT dropType,groupId,groupRate,itemId,itemRate FROM mob_droplist WHERE dropId=%s", (g["dropid"],))
                g["drops"] = [dict(zip(["type", "group", "group_rate", "item", "rate"], r)) for r in dr]
        sk = _rows_dict(conn, "SELECT s.mob_skill_id,s.mob_skill_name,s.mob_anim_id,s.mob_skill_aoe,s.mob_skill_distance,s.mob_skill_flag,s.mob_skill_param,s.primary_sc,s.secondary_sc,s.tertiary_sc "
                              "FROM mob_skill_lists l JOIN mob_skills s ON s.mob_skill_id=l.mob_skill_id WHERE l.skill_list_id=%s ORDER BY s.mob_skill_id", (int(pool["skill_list_id"] or 0),)) if pool["skill_list_id"] else []
        pool["skills"] = [dict(zip(["id", "name", "anim", "aoe", "distance", "flag", "param", "sc1", "sc2", "sc3"], s)) for s in sk]
        sp = _rows_dict(conn, "SELECT l.spell_id,COALESCE(sl.name,''),l.min_level,l.max_level FROM mob_spell_lists l LEFT JOIN spell_list sl ON sl.spellid=l.spell_id WHERE l.spell_list_id=%s ORDER BY l.spell_id", (int(pool["spellList"] or 0),)) if pool["spellList"] else []
        pool["spells"] = [dict(zip(["id", "name", "min", "max"], s)) for s in sp]
        fam = _rows_dict(conn, "SELECT " + ",".join("`%s`" % k for k in FAM_COLS + RES) + " FROM mob_family_system WHERE familyid=%s", (int(pool["familyid"]),))
        if fam:
            keys = FAM_COLS + RES
            pool["family"] = dict(zip(keys, fam[0]))
        pool["mods"] = [dict(zip(["modid", "value", "is_mob_mod"], m)) for m in _rows_dict(conn, "SELECT modid,value,is_mob_mod FROM mob_pool_mods WHERE poolid=%s", (pid,))]
        d["pools"].append(pool)
    roots = script_roots(active_root)
    root, path = find_script(roots, tr["name"])
    d["script"] = None
    if path is not None:
        text = path.read_text(encoding="utf-8", errors="replace")
        d["script"] = {"path": str(path), "root": str(root), "in_active_root": str(root) == str(active_root), "lines": text.count("\n") + 1, "parsed": parse_lua(text), "source": text}
    ids = set()
    if d["script"]:
        ids |= set(d["script"]["parsed"]["drops"]) | {a for a, _ in d["script"]["parsed"]["drop_rates"]}
    for p in d["pools"]:
        for g in p["groups"]:
            ids |= {x["item"] for x in g["drops"]}
    d["items"] = _item_names(conn, ids)
    rifts = []
    for r in tr.get("rifts", []):
        rows = _rows_dict(conn, "SELECT npcid,name,pos_x,pos_y,pos_z FROM npc_list WHERE npcid=%s", (int(r[0]),))
        rifts.append({"npc": r[0], "pos": r[1:], "live": dict(zip(["npcid", "name", "x", "y", "z"], rows[0])) if rows else None})
    d["rifts"] = rifts
    d["checks"] = checks(d)
    d["validation"] = load_validation().get(tr["name"]) or {"areas": {}, "note": "", "updated": "", "by": ""}
    d["validation"]["status"] = validation_status(d["validation"])
    d["areas"] = AREAS
    d["states"] = STATES
    return d


def checks(d: dict) -> list[dict]:
    """Plain consistency findings between tracker, database and script. Never guesses."""
    out = []

    def add(level, msg):
        out.append({"level": level, "msg": msg})
    tr = d["tracker"]
    if not d["pools"]:
        add("bad", "No mob_pools row with this name in the active DSP database.")
    for p in d["pools"]:
        if not p["groups"]:
            add("bad", f"Pool {p['poolid']} has no mob_groups row.")
        for g in p["groups"]:
            if not g["spawns"]:
                add("bad", f"Group {g['groupid']} has no mob_spawn_points row.")
            elif any(not (s["x"] or s["y"] or s["z"]) for s in g["spawns"]):
                add("bad", f"Group {g['groupid']} has a spawn at (0,0,0); instance/zone loaders skip it.")
            if g["HP"] == 0:
                add("warn", f"Group {g['groupid']} HP is 0 (falls back to family/level scaling).")
        if not p["skills"]:
            add("warn", f"Pool {p['poolid']} has no mob skills (skill_list_id {p['skill_list_id']}).")
    if tr["status"] == "built" and d["script"] is None:
        add("bad", "Tracker says built, but no mob script was found in the DSP checkout.")
    if tr["status"] != "built" and d["script"] is not None:
        add("warn", "A mob script exists but the tracker still says 'not built'.")
    if d["script"] and not d["script"]["in_active_root"]:
        add("info", "Script found only in " + d["script"]["root"] + " (feature checkout), not in the active server root.")
    if tr.get("rifts"):
        miss = [r["npc"] for r in d["rifts"] if r["live"] is None]
        if miss:
            add("warn", "Rift NPC ids not in the active DB: " + ", ".join(map(str, miss)))
    if not tr.get("ki_id"):
        add("info", "Abyssite key item not recorded in the tracker.")
    if d["script"] and not d["script"]["parsed"]["drops"] and not d["script"]["parsed"]["drop_rates"]:
        add("warn", "Script defines no drop table.")
    return out


def overview(conn, active_root) -> dict:
    """One row per tracked NM: status plus cheap live facts, for the table and the graph."""
    tracker = load_tracker()
    roots = script_roots(active_root)
    val = load_validation()
    out = []
    for tr in tracker:
        pools = find_pools(conn, tr["name"])
        hp = None
        if pools:
            g = _rows_dict(conn, "SELECT groupid,HP,zoneid FROM mob_groups WHERE poolid=%s LIMIT 1", (int(pools[0][0]),))
            hp = int(g[0][1]) if g else None
        root, path = find_script(roots, tr["name"])
        out.append({"name": tr["name"], "zone": tr["zone"], "zone_id": tr["zone_id"], "path": tr["path"], "tier": tr["tier"], "ki_id": tr["ki_id"], "ki_name": tr["ki_name"],
                    "status": tr["status"], "has_pool": bool(pools), "hp": hp, "has_script": path is not None, "gaps": tr["gaps"], "rifts": len(tr.get("rifts", [])), "validation": validation_status(val.get(tr["name"]))})
    return {"areas": AREAS, "states": STATES, "nms": out, "paths": PATHS, "tiers": TIERS, "unlocks": EDGE_UNLOCKS,
            "note": "Progression rules are [W] BG Wiki digest, reference only. The tracker supplies path/tier/abyssite per NM; NMs without a path are not yet classified."}


def load_validation() -> dict:
    try:
        return json.loads(VALIDATION.read_text(encoding="utf-8")) if VALIDATION.exists() else {}
    except ValueError:
        return {}


def validation_status(rec: dict | None) -> str:
    """validated = every area ok/n-a; issue = any issue; partial = some ok; unvalidated = nothing recorded."""
    areas = (rec or {}).get("areas", {})
    vals = [areas.get(k, "untested") for k, _ in AREAS]
    if "issue" in vals:
        return "issue"
    if all(v in ("ok", "n/a") for v in vals):
        return "validated"
    return "partial" if "ok" in vals else "unvalidated"


def save_validation(name: str, areas: dict, note: str, who: str = "") -> dict:
    import datetime
    if not any(x["name"] == name for x in load_tracker()):
        raise KeyError(name)
    clean = {k: (areas.get(k) if areas.get(k) in STATES else "untested") for k, _ in AREAS}
    data = load_validation()
    data[name] = {"areas": clean, "note": note[:2000], "updated": datetime.datetime.now().isoformat(timespec="seconds"), "by": who}
    tmp = VALIDATION.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(VALIDATION)
    return data[name]
