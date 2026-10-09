"""Gated npc_list fixes for the Voidwatch NPCs (officers / refiners / purveyors / Ardrick).

Three plan types, all producing the exact SQL the user can also run by hand:
  update - rename / reposition one existing row (whitelisted columns)
  delete - remove one row of a Voidwatch NPC name
  insert - add a missing row for a zone from coordinates the user supplies (!logpos x y z rot); columns copied from a sibling row of the same name.
Coordinates are never invented: an insert needs all of x/y/z/rot from the caller. New npcids follow the zone-bits rule (mobid bits 12-23 are the
zone id, targid < 0x400) and must be free in both npc_list and mob_spawn_points.
"""
from __future__ import annotations

import datetime
import json

from workbench.runtime.paths import REPO_ROOT
from workbench.server_admin.synth import recipes as R

LOG = REPO_ROOT / "data" / "voidwatch" / "edit_log.jsonl"
VW_NAMES = ("Voidwatch_Officer", "Voidwatch_Purveyor", "Atmacite_Refiner", "Ardrick")
UPDATE_COLS = {"name": str, "polutils_name": str, "pos_x": float, "pos_y": float, "pos_z": float, "pos_rot": int}

# Proposed fixes backed by DB evidence (re-evaluated live: a fix shows as done once the row matches).
FIXES = [
    {"id": "batallia_s_officer", "title": "Batallia Downs [S] row 17122262 is registered as Voidwatch_Purveyor but is the officer",
     "evidence": "polutils_name is 'Voidwatch Officer'; it sits at (429.5, 8.25, -135.5) beside the [S] refiner 17122261 and mirrors the present-day officer 17207937 "
                 "(429.299, 8.25, -136.0). npc_list.name drives script lookup, so as a Purveyor it would load the wrong script.",
     "plan": {"kind": "update", "npcid": 17122262, "changes": {"name": "Voidwatch_Officer"}}},
]
# Needs user input (not guessed): shown as open questions.
OPEN = [
    "Southern San d'Oria: purveyor rows 17719636 (-100.5,1,-51) and 17719637 (100,1,-50). The latter has the same coordinates as the [S] purveyor 17105696. "
    "Wiki says one purveyor at K-10. Stand at the real one and send !logpos to decide which to delete.",
    "Al Zahbi: purveyor rows 16974380 (-85,2,100) and 16974381 (-101,2,86). Wiki gives no grid ref; needs an in-game check.",
    "Missing rows (wiki lists the zone, DB has none): Voidwatch_Officer and Atmacite_Refiner in Qufim_Island (I-11); Voidwatch_Purveyor in RuLude_Gardens (H-10). "
    "Enter !logpos coordinates in the Add-row form.",
]


class FixError(ValueError):
    pass


def _lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, (bytes, bytearray)):
        return "X'" + bytes(v).hex() + "'"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def _cols(conn):
    return [r[0] for r in R._rows(conn, "SHOW COLUMNS FROM npc_list")]


def _row(conn, npcid):
    cols = _cols(conn)
    rows = R._rows(conn, "SELECT * FROM npc_list WHERE npcid=%s", (npcid,))
    return cols, (dict(zip(cols, rows[0])) if rows else None)


def plan_update(conn, npcid: int, changes: dict) -> dict:
    cols, row = _row(conn, npcid)
    if row is None:
        raise FixError("npc_list.npcid=%s not found" % npcid)
    if row["name"] not in VW_NAMES:
        raise FixError("%s is not a Voidwatch NPC row" % row["name"])
    clean = {}
    for k, v in changes.items():
        if k not in UPDATE_COLS:
            raise FixError("Column %r is not editable" % k)
        try:
            clean[k] = UPDATE_COLS[k](v)
        except (TypeError, ValueError):
            raise FixError("%s: %r is not valid" % (k, v))
    if not clean:
        raise FixError("no changes given")
    if "name" in clean and clean["name"] not in VW_NAMES:
        raise FixError("name must be one of " + ", ".join(VW_NAMES))
    if "pos_rot" in clean and not 0 <= clean["pos_rot"] <= 255:
        raise FixError("pos_rot must be 0..255")
    before = {k: row[k] for k in clean}
    sql = "UPDATE `npc_list` SET " + ", ".join("`%s`=%s" % (k, _lit(v)) for k, v in clean.items()) + " WHERE `npcid`=%d;" % npcid
    return {"kind": "update", "npcid": npcid, "changes": clean, "before": before, "sql": sql,
            "warnings": ["Changes the live DB; the map server needs a restart for NPC changes to show."]}


def plan_delete(conn, npcid: int) -> dict:
    cols, row = _row(conn, npcid)
    if row is None:
        raise FixError("npc_list.npcid=%s not found" % npcid)
    if row["name"] not in VW_NAMES:
        raise FixError("Only Voidwatch NPC rows can be deleted here")
    return {"kind": "delete", "npcid": npcid,
            "before": {k: row[k] for k in ("name", "polutils_name", "pos_x", "pos_y", "pos_z", "pos_rot")},
            "sql": "DELETE FROM `npc_list` WHERE `npcid`=%d AND `name`=%s;" % (npcid, _lit(row["name"])),
            "warnings": ["Deletes the row; the 'before' values are logged so it can be restored."]}


def _free_npcid(conn, zid: int) -> int:
    base = 0x1000000 | (zid << 12)
    used = {int(r[0]) & 0xFFF for r in R._rows(conn, "SELECT npcid FROM npc_list WHERE ((npcid>>12)&4095)=%s", (zid,))}
    used |= {int(r[0]) & 0xFFF for r in R._rows(conn, "SELECT mobid FROM mob_spawn_points WHERE ((mobid>>12)&4095)=%s", (zid,))}
    t = max([u for u in used if u < 0x400] or [0]) + 1
    while t in used:
        t += 1
    if t >= 0x400:
        raise FixError("no free targid below 0x400 in zone %d" % zid)
    return base | t


def plan_insert(conn, npc_name: str, zone: str, x, y, z, rot) -> dict:
    if npc_name not in VW_NAMES:
        raise FixError("npc must be one of " + ", ".join(VW_NAMES))
    try:
        x, y, z, rot = float(x), float(y), float(z), int(float(rot))
    except (TypeError, ValueError):
        raise FixError("x, y, z and rot are all required numbers (use !logpos); coordinates are never guessed")
    if not any((x, y, z)):
        raise FixError("position (0,0,0) is refused")
    if not 0 <= rot <= 255:
        raise FixError("rot must be 0..255")
    zr = R._rows(conn, "SELECT zoneid FROM zone_settings WHERE name=%s", (zone,))
    if not zr:
        raise FixError("unknown zone %r" % zone)
    zid = int(zr[0][0])
    if R._rows(conn, "SELECT 1 FROM npc_list WHERE name=%s AND ((npcid>>12)&4095)=%s LIMIT 1", (npc_name, zid)):
        raise FixError("%s already has a row in %s; update or delete it instead" % (npc_name, zone))
    cols = _cols(conn)
    tmpl = R._rows(conn, "SELECT * FROM npc_list WHERE name=%s ORDER BY npcid LIMIT 1", (npc_name,))
    if not tmpl:
        raise FixError("no sibling %s row to copy columns from" % npc_name)
    new = dict(zip(cols, tmpl[0]))
    new.update({"npcid": _free_npcid(conn, zid), "pos_x": x, "pos_y": y, "pos_z": z, "pos_rot": rot})
    sql = "INSERT INTO `npc_list` (%s) VALUES (%s);" % (",".join("`%s`" % c for c in cols), ",".join(_lit(new[c]) for c in cols))
    return {"kind": "insert", "npcid": new["npcid"], "zone": zone,
            "row": {k: (bytes(v).hex() if isinstance(v, (bytes, bytearray)) else v) for k, v in new.items()}, "sql": sql,
            "warnings": ["Columns copied from sibling row %s (look/flags/animation); verify the model in game." % tmpl[0][0],
                         "Run !checknav %s %s %s in %s before trusting the position (Y axis is inverted)." % (x, y, z, zone)]}


def apply(conn, p: dict, who: str = "") -> int:
    cur = conn.cursor()
    try:
        if p["kind"] == "update":
            cur.execute("UPDATE npc_list SET " + ",".join("`%s`=%%s" % k for k in p["changes"]) + " WHERE npcid=%s",
                        (*p["changes"].values(), p["npcid"]))
        elif p["kind"] == "delete":
            cur.execute("DELETE FROM npc_list WHERE npcid=%s", (p["npcid"],))
        else:
            cols = _cols(conn)
            vals = [bytes.fromhex(p["row"][c]) if c == "look" else p["row"][c] for c in cols]
            cur.execute("INSERT INTO npc_list (%s) VALUES (%s)" % (",".join("`%s`" % c for c in cols), ",".join(["%s"] * len(cols))), vals)
        n = cur.rowcount
        conn.commit()
    finally:
        cur.close()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": datetime.datetime.now().isoformat(timespec="seconds"), "by": who, "table": "npc_list", "key": p["npcid"],
                             "kind": p["kind"], "before": p.get("before"), "sql": p["sql"], "rows": n}, default=str) + "\n")
    return int(n)


def overview(conn) -> dict:
    out = []
    for f in FIXES:
        pl = f["plan"]
        cols, row = _row(conn, pl["npcid"])
        done = bool(row) and all(row.get(k) == v for k, v in pl["changes"].items())
        out.append({**f, "done": done, "exists": row is not None,
                    "plan_result": None if done or row is None else plan_update(conn, pl["npcid"], pl["changes"])})
    return {"fixes": out, "open": OPEN, "names": list(VW_NAMES)}
