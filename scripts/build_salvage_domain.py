"""Build data/salvage/salvage.json for the Salvage domain page.

Scans three source trees (live Topaz, the DSP target in dsp-branches, the LandSandBoat reference) and the toolkit
capture DB. Everything counted here is read from a file or a DB row; anything not found is left null/"unknown"
rather than estimated. Curated, hand-written facts live in data/salvage/curation.json.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "salvage" / "salvage.json"
CUR = ROOT / "data" / "salvage" / "curation.json"
DB = ROOT / "ffxi_zone_database.db"
TREES = {"topaz": Path("C:/topaz"), "dsp": Path("D:/Claude/dsp-branches"), "lsb": Path("D:/Claude/landsandboat-reference")}
HOOKS = ["afterInstanceRegister", "onInstanceCreated", "onInstanceTimeUpdate", "onInstanceFailure", "onInstanceComplete",
         "onInstanceProgressUpdate", "onInstanceStageChange", "onInstanceLoadFailed"]
ZONES = [  # key, folder, instance_list name stem, wiki zone name
    ("zhayolm", "Zhayolm_Remnants", "zhayolm_remnants", "Zhayolm Remnants"),
    ("arrapago", "Arrapago_Remnants", "arrapago_remnants", "Arrapago Remnants"),
    ("bhaflau", "Bhaflau_Remnants", "bhaflau_remnants", "Bhaflau Remnants"),
    ("silver_sea", "Silver_Sea_Remnants", "silver_sea_remnants", "Silver Sea Remnants"),
]


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def lua_files(tree: Path, folder: str, sub: str) -> list[str]:
    d = tree / "scripts" / "zones" / folder / sub
    return sorted(p.stem for p in d.glob("*.lua")) if d.is_dir() else []


def instance_rows(tree: Path) -> dict:
    """instance_list rows for the Remnants names -> {name: {'id','live'}} (live = row not commented out)."""
    out = {}
    for line in read(tree / "sql" / "instance_list.sql").splitlines():
        m = re.match(r"\s*(-- )?INSERT INTO `instance_list` VALUES \((\d+),'(\w+)',(\d+),(\d+),(?:NULL,)?(\d+)", line)
        if m and "remnants" in m.group(3):
            out[m.group(3)] = {"id": int(m.group(2)), "zone": int(m.group(4)), "entry_zone": int(m.group(5)),
                               "time_limit": int(m.group(6)), "live": m.group(1) is None}
    return out


def entity_counts(tree: Path) -> dict:
    out: dict[int, int] = {}
    for line in read(tree / "sql" / "instance_entities.sql").splitlines():
        m = re.match(r"\s*INSERT INTO `instance_entities` VALUES \((\d+),", line)
        if m:
            out[int(m.group(1))] = out.get(int(m.group(1)), 0) + 1
    return out


def live_entity_counts() -> dict:
    """instance_entities counts from the live Topaz DB (credentials from conf/map.conf); {} if unreachable."""
    try:
        import mysql.connector
        cfg = read(TREES["topaz"] / "conf" / "map.conf")
        g = lambda k: re.search(r"^" + k + r":\s*(.+)$", cfg, re.M).group(1).strip()
        c = mysql.connector.connect(host=g("mysql_host"), port=int(g("mysql_port")), user=g("mysql_login"),
                                    password=g("mysql_password"), database=g("mysql_database"), connection_timeout=4)
        q = c.cursor()
        q.execute("select instanceid, count(*) from instance_entities group by instanceid")
        return {int(i): int(n) for i, n in q.fetchall()}
    except Exception:
        return {}


def inst_info(tree: Path, folder: str, stem: str) -> dict:
    d = tree / "scripts" / "zones" / folder
    inst = d / "instances"
    files = sorted(inst.glob("*.lua")) if inst.is_dir() else []
    src = "\n".join(read(f) for f in files)
    info = {
        "zone_lua": (d / "Zone.lua").exists(),
        "ids_lua": (d / "IDs.lua").exists() or (d / "TextIDs.lua").exists(),
        "instance_files": [f.name for f in files],
        "hooks": [h for h in HOOKS if re.search(r"\b" + h + r"\b", src)],
        "uses_doors": bool(re.search(r"unsealDoors|setAnimation|_2[0-9a-f]{2}", src)),
        "uses_regions": "registerRegion" in read(d / "Zone.lua") or "registerRegion" in src,
        "mobs": lua_files(tree, folder, "mobs"),
        "npcs": lua_files(tree, folder, "npcs"),
    }
    return info


def captures() -> list[dict]:
    try:
        c = sqlite3.connect(str(DB))
        q = ("select capture_id,capture_label,zones,mission_name from captures where "
             "lower(coalesce(zones,'')||coalesce(mission_name,'')||coalesce(capture_label,'')) like '%remnant%' or "
             "lower(coalesce(capture_label,'')) like '%salvage ii%' or lower(coalesce(capture_label,'')) like '%salvage -%' "
             "or lower(coalesce(capture_label,'')) like '%salavge%' or lower(coalesce(capture_label,'')) like '%salvage-%' "
             "or lower(coalesce(capture_label,'')) like '%salvage prep%' order by capture_id")
        rows = c.execute(q).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for cid, label, zones, mission in rows:
        text = ((zones or "") + " " + (label or "") + " " + (mission or "")).lower()
        zk = next((k for k, _, _, w in ZONES if w.lower() in text), None)
        if zk is None and "silver" in text:
            zk = "silver_sea"
        out.append({"id": cid, "label": label, "zone": zk, "mission": mission,
                    "salvage2": "salvage ii" in text or "salvage-ii" in text})
    return out


def main() -> None:
    cur = json.loads(read(CUR) or "{}")
    rows = {k: instance_rows(t) for k, t in TREES.items()}
    ents = {k: entity_counts(t) for k, t in TREES.items()}
    live = live_entity_counts()
    caps = captures()
    zones, tracks = [], []
    for zk, folder, stem, wiki in ZONES:
        info = {k: inst_info(t, folder, stem) for k, t in TREES.items()}
        zcaps = [c for c in caps if c["zone"] == zk]
        zones.append({"id": zk, "name": wiki, "folder": folder, "info": info,
                      "captures": len(zcaps), "status": "partial" if info["topaz"]["instance_files"] else "not built"})
        for roman, name in (("I", stem), ("II", stem + "_ii")):
            r = {k: rows[k].get(name) for k in TREES}
            t = info["topaz"]
            if roman == "I":
                if not r["topaz"] or not r["topaz"]["live"]:
                    status = "not built"
                elif t["instance_files"] and t["mobs"]:
                    status = "partial"
                else:
                    status = "not built"
                dsp = "partial" if info["dsp"]["instance_files"] else ("not built" if r["dsp"] else "unknown")
            else:
                status = "not built"
                dsp = "not built"
            tid = r["topaz"]["id"] if r["topaz"] else None
            tracks.append({
                "id": zk + "_" + roman.lower(), "zone": zk, "name": "%s %s" % (wiki, roman), "level": roman,
                "status": status, "dsp_status": dsp,
                "instance_name": name,
                "topaz_instance_id": tid, "topaz_row_live": bool(r["topaz"] and r["topaz"]["live"]),
                "dsp_instance_id": r["dsp"]["id"] if r["dsp"] else None,
                "lsb_instance_id": r["lsb"]["id"] if r["lsb"] else None,
                "time_limit": r["topaz"]["time_limit"] if r["topaz"] else None,
                "topaz_entities": ents["topaz"].get(tid) if tid is not None else None,
                "live_db_entities": live.get(tid) if (live and tid is not None) else None,
                "sql_db_mismatch": bool(live and tid is not None and roman == "I" and live.get(tid, 0) != ents["topaz"].get(tid, 0)),
                "hooks": t["hooks"] if roman == "I" else [],
                "mob_scripts": len(t["mobs"]) if roman == "I" else 0,
                "npc_scripts": len(t["npcs"]) if roman == "I" else 0,
                "captures": len([c for c in zcaps if c["salvage2"] == (roman == "II")]),
            })
    out = {"zones": zones, "tracks": tracks, "captures": caps,
           "systems": cur.get("systems", []), "rewards": cur.get("rewards", []),
           "npcs": cur.get("npcs", []), "open_questions": cur.get("open_questions", [])}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("zones", len(zones), "tracks", len(tracks), "captures", len(caps))


if __name__ == "__main__":
    main()
