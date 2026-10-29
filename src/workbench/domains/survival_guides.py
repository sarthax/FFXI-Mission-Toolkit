"""Survival Guides domain: one row per guide in <DSP checkout> sql/survival_guides_apply.sql, joined with the DAT-verified id list
(data/survival_guides/dat_verified.json), the live DB (dspdb_fresh, best effort) and the user's validation marks (validation.json)."""
from __future__ import annotations

import datetime
import json
import re
import sqlite3

from workbench.runtime.local_roots import dsp_root
from workbench.runtime.paths import REPO_ROOT

DIR = REPO_ROOT / "data" / "survival_guides"
VALID = DIR / "validation.json"
VERIFIED = DIR / "dat_verified.json"
def _dsp_file(*parts):
    root = dsp_root()
    return str(root.joinpath(*parts)) if root else "<dsp-root-not-configured>"


STATES = ("ok", "warn", "bad", "idle")
ROW = re.compile(r"VALUES \((\d+),'Survival_Guide','Survival Guide',(\d+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+).*?--\s*zone (\d+)(?: pos:(\w+))?")


def _load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _live_ids() -> set | None:
    try:
        import mysql.connector
        cf = open(_dsp_file("conf", "map_darkstar.conf"), encoding="utf8").read()
        g = lambda k: re.search(r"^%s:\s*(\S+)" % k, cf, re.M).group(1)
        c = mysql.connector.connect(host=g("mysql_host"), port=int(g("mysql_port")), user=g("mysql_login"), password=g("mysql_password"),
                                    database=g("mysql_database"), connection_timeout=3)
        q = c.cursor()
        q.execute("select npcid from npc_list where name='Survival_Guide'")
        return {r[0] for r in q.fetchall()}
    except Exception:
        return None


def overview() -> dict:
    marks, ver, live = _load(VALID), set(_load(VERIFIED) or []), _live_ids()
    names = {}
    try:
        con = sqlite3.connect(str(REPO_ROOT / "ffxi_zone_database.db"))
        names = dict(con.execute("select zoneid,name from zones").fetchall())
    except Exception:
        pass
    rows = []
    for line in open(_dsp_file("sql", "survival_guides_apply.sql"), encoding="utf8", errors="replace"):
        m = ROW.search(line)
        if not m:
            continue
        nid, rot, x, y, z, zone, src = int(m[1]), m[2], float(m[3]), float(m[4]), float(m[5]), int(m[6]), m[7] or ""
        mk = marks.get("guide:%d" % nid, {})
        rows.append({"id": nid, "zoneid": zone, "zone": names.get(zone, ""), "x": x, "y": y, "z": z, "pos_source": src,
                     "zero_pos": x == 0 and z == 0, "dat_verified": nid in ver,
                     "live": None if live is None else nid in live,
                     "validation": mk.get("state", "idle"), "vnote": mk.get("note", "")})
    rows.sort(key=lambda r: r["zoneid"])
    s = {"total": len(rows), "dat_verified": sum(r["dat_verified"] for r in rows), "zero_pos": sum(r["zero_pos"] for r in rows),
         "live": None if live is None else sum(1 for r in rows if r["live"]),
         "in_game_ok": sum(r["validation"] == "ok" for r in rows), "bad": sum(r["validation"] == "bad" for r in rows)}
    return {"summary": s, "guides": rows}


def mark(ident: str, state: str, note: str = "") -> dict:
    if state not in STATES:
        raise ValueError("state must be one of %s" % ", ".join(STATES))
    if not any(str(r["id"]) == str(ident) for r in overview()["guides"]):
        raise KeyError("no guide %r" % ident)
    marks = _load(VALID)
    marks["guide:%s" % ident] = {"state": state, "note": note.strip()[:500], "updated": datetime.datetime.now().isoformat(timespec="seconds")}
    DIR.mkdir(parents=True, exist_ok=True)
    VALID.write_text(json.dumps(marks, indent=1), encoding="utf-8")
    return marks["guide:%s" % ident]
