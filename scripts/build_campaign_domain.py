"""Build data/campaign/campaign.json from the existing Campaign research.

Inputs (all read-only):
  docs/campaign/data/missions_enriched.tsv   246 wiki-derived mission rows
  docs/campaign/TRACKER.md                   per-mission build status grid
  data/campaign/curation.json                hand-curated NPCs / menus / rewards / systems
  ffxi_zone_database.db  capture_post_meta   tagged campaign captures
  <active server>/sql/npc_list.sql           name presence check (file text, not the live DB)

Nothing is invented: a field with no source stays null/'unknown'.
Run:  py -3 scripts/build_campaign_domain.py
"""
import csv
import datetime
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent / "docs" / "campaign"
OUT = ROOT / "data" / "campaign" / "campaign.json"
EMOJI = {"🔴": "not built", "🟡": "partial", "🟢": "built", "✅": "done"}
CAP_EMOJI = {"⬜": "none", "🟦": "indexed", "🟩": "downloaded", "✅": "analysed"}
CATS = {"offensive": "Offensive", "defensive": "Defensive", "intel": "Intel gathering", "military": "Military training",
        "resource": "Resource procurement", "supply transport": "Supply transport", "supply manufacture": "Supply manufacture",
        "security": "Security"}
NATION = {"Rasdinice": "San d'Oria", "Hieronymus": "Bastok", "Emhi": "Windurst"}
GIVER_ID = {"Rasdinice": "rasdinice", "Hieronymus": "hieronymus", "Emhi": "emhi"}


def cat_of(s):
    s = (s or "").lower()
    for k, v in CATS.items():
        if s.startswith(k):
            return v
    return s.title() or "Unknown"


def npc_of(s):
    s = s or ""
    hits = [n for n in NATION if n in s]
    return hits[0] if len(hits) == 1 else ("(several)" if hits else "")


def grid_of(s):
    m = re.search(r"\(([A-L]-\d{1,2})\)", s or "") or re.search(r"\|([A-L]-\d{1,2})\}", s or "")
    return m.group(1) if m else ""


def tracker():
    rows = {}
    f = DOCS / "TRACKER.md"
    if not f.exists():
        return rows
    for line in f.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 8 and c[0] not in ("Mission", "---") and not c[0].startswith("-"):
            rows[c[0]] = {"S": EMOJI.get(c[4], ""), "B": EMOJI.get(c[5], ""), "W": EMOJI.get(c[6], ""),
                          "capture": CAP_EMOJI.get(c[7], ""), "notes": c[8] if len(c) > 8 else ""}
    return rows


def missions():
    trk = tracker()
    out = []
    with open(DOCS / "data" / "missions_enriched.tsv", encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            base, nat = r["base"].strip(), r["nation"].strip()
            t = trk.get(base, {})
            out.append({"id": "%s-%s" % (r["idx"], nat), "cidx": r["idx"],
                        "name": base, "nation": nat, "category": cat_of(r["category"]), "min_medal": r["min_medal"].strip(),
                        "giver": npc_of(r["start_npc"]), "giver_id": GIVER_ID.get(npc_of(r["start_npc"]), ""), "giver_grid": grid_of(r["start_npc"]), "requirements": r["requirements"].strip(),
                        "size": r["size"].strip(), "cost": r["cost"].strip(), "result": r["result"].strip(), "tiers": r["tiers"].strip(),
                        "status": t.get(nat, "") or "not built", "capture": t.get("capture", "none"),
                        "ev": "W" + ("C" if t.get("capture") in ("downloaded", "analysed") else ""), "verified": False})
    return out


def captures():
    db = ROOT / "ffxi_zone_database.db"
    out = []
    if not db.exists():
        return out
    con = sqlite3.connect(db)
    try:
        for cid, typ, sec, title, up, date, ops, vid in con.execute(
                "SELECT capture_id,capture_type,secondary_types,title,uploader,post_date,ops_missions,video_url FROM capture_post_meta ORDER BY capture_id"):
            out.append({"id": cid, "type": typ or "", "secondary": sec or "", "title": title or "", "uploader": up or "", "date": date or "",
                        "ops_missions": ops or "", "video": vid or ""})
    except sqlite3.Error:
        pass
    return out


def server_names():
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from workbench.runtime.legacy_settings import get_active_server_root
        root = get_active_server_root()
        f = Path(root) / "sql" / "npc_list.sql" if root else None
        return (f.read_text(encoding="utf-8", errors="replace"), str(root)) if f and f.exists() else ("", str(root or ""))
    except Exception:
        return "", ""


def main():
    cur = json.loads((ROOT / "data" / "campaign" / "curation.json").read_text(encoding="utf-8"))
    ms, caps = missions(), captures()
    sql_text, sroot = server_names()
    for n in cur["npcs"]:
        key = n["name"].split(",")[0].split(" ")[0]
        n["in_server_sql"] = (bool(re.search(r"[\"']%s\b" % re.escape(key), sql_text)) if sql_text and n["status"] != "unknown" else None)
        n["missions"] = sum(1 for m in ms if m["giver_id"] == n["id"])
    cats = {}
    for m in ms:
        c = cats.setdefault(m["category"], {"name": m["category"], "count": 0, "by_status": {}})
        c["count"] += 1
        c["by_status"][m["status"]] = c["by_status"].get(m["status"], 0) + 1
    by_type = {}
    for c in caps:
        by_type[c["type"] or "(untyped)"] = by_type.get(c["type"] or "(untyped)", 0) + 1
    medals = sorted({m["min_medal"] for m in ms if m["min_medal"]})
    data = {"generated": datetime.datetime.now().isoformat(timespec="seconds"), "server_root": sroot,
            "systems": cur["systems"], "npcs": cur["npcs"], "menus": cur["menus"], "rewards": cur["rewards"], "quests": cur["quests"],
            "open_questions": cur["open_questions"], "missions": ms, "categories": sorted(cats.values(), key=lambda x: -x["count"]),
            "captures": caps, "capture_types": by_type, "medal_requirements": medals}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT, "| missions", len(ms), "npcs", len(cur["npcs"]), "menus", len(cur["menus"]), "captures", len(caps))


if __name__ == "__main__":
    main()
