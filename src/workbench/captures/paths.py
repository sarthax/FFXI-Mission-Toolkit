"""Capture PathLog trace queries for the Zone Editor's Paths tab.

Unlike capture spatial (one position per entity), this returns the full per-leg PathLog traces:
capture_npc_path / capture_pc_path rows carry (leg, step, x, y, z, dir, delta). Legs are kept
separate so a discontinuity (zone-in, teleport, despawn/respawn) is never drawn as a straight
line between two unrelated points.
"""
from __future__ import annotations

import json
import math
import sqlite3


def zone_db_for_zoneid(con: sqlite3.Connection, zoneid: int) -> str | None:
    """Inverse of gui_server.zoneid_for_zone_db: zones.name is SCREAMING_SNAKE, zone_db is spaced."""
    row = con.execute("SELECT name FROM zones WHERE zoneid=?", (zoneid,)).fetchone()
    return row[0] if row else None


def _norm(s: str) -> str:
    return (s or "").upper().replace(" ", "_").replace("'", "")


def _zone_dbs(con: sqlite3.Connection, zoneid: int) -> list[str]:
    """Every capture zone_db spelling that normalizes to this zone's name."""
    name = zone_db_for_zoneid(con, zoneid)
    if not name:
        return []
    target = _norm(name)
    seen = set()
    for table in ("capture_npc_path", "capture_pc_path"):
        for (z,) in con.execute(f"SELECT DISTINCT zone_db FROM {table}").fetchall():
            if z and _norm(z) == target:
                seen.add(z)
    return sorted(seen)


def captures_for_zone(con: sqlite3.Connection, zoneid: int) -> list[dict]:
    """Captures that have any PathLog data in this zone, newest id first."""
    zdbs = _zone_dbs(con, zoneid)
    if not zdbs:
        return []
    ph = ",".join("?" * len(zdbs))
    npc = {r[0]: (r[1], r[2]) for r in con.execute(
        f"""SELECT capture_id, COUNT(DISTINCT entity_id), COUNT(*) FROM capture_npc_path
            WHERE zone_db IN ({ph}) GROUP BY capture_id""", zdbs)}
    pc = {r[0]: r[1] for r in con.execute(
        f"""SELECT capture_id, COUNT(*) FROM capture_pc_path
            WHERE zone_db IN ({ph}) GROUP BY capture_id""", zdbs)}
    out = []
    for cid in sorted(set(npc) | set(pc), reverse=True):
        row = con.execute("SELECT capture_label, mission_name FROM captures WHERE capture_id=?", (cid,)).fetchone()
        out.append({
            "capture_id": cid,
            "title": (row[0] if row else None) or f"capture {cid}",
            "mission": row[1] if row else None,
            "npc_entities": npc.get(cid, (0, 0))[0],
            "npc_points": npc.get(cid, (0, 0))[1],
            "pc_points": pc.get(cid, 0),
        })
    return out


def _legs(rows) -> list[dict]:
    legs: dict[int, list] = {}
    for leg, x, y, z, d, delta in rows:
        legs.setdefault(leg, []).append([x, y if y is not None else 0, z, d or 0, delta or 0])
    return [{"leg": k, "points": v} for k, v in sorted(legs.items())]


def _length(legs: list[dict]) -> float:
    total = 0.0
    for leg in legs:
        p = leg["points"]
        for a, b in zip(p, p[1:]):
            total += math.hypot(b[0] - a[0], b[2] - a[2])
    return round(total, 1)


def capture_paths(con: sqlite3.Connection, zoneid: int, capture_id: int) -> dict:
    """All PathLog traces for one capture within one zone: PC trace + every NPC/mob entity."""
    zdbs = _zone_dbs(con, zoneid)
    out = {"capture_id": capture_id, "zoneid": zoneid, "zone_dbs": zdbs, "pc": [], "npcs": []}
    if not zdbs:
        return out
    ph = ",".join("?" * len(zdbs))

    pc_rows = con.execute(
        f"""SELECT leg, x, y, z, dir, delta FROM capture_pc_path
            WHERE capture_id=? AND zone_db IN ({ph}) ORDER BY leg, step""",
        [capture_id, *zdbs]).fetchall()
    out["pc"] = _legs(pc_rows)

    names = {int(r[0]): r for r in con.execute(
        f"""SELECT entity_id, name, x, y, z, model_id, hpp FROM capture_npc_entries
            WHERE capture_id=? AND zone_db IN ({ph})""", [capture_id, *zdbs])}
    ids = [r[0] for r in con.execute(
        f"""SELECT DISTINCT entity_id FROM capture_npc_path
            WHERE capture_id=? AND zone_db IN ({ph}) ORDER BY entity_id""", [capture_id, *zdbs])]
    for eid in ids:
        rows = con.execute(
            f"""SELECT leg, x, y, z, dir, delta FROM capture_npc_path
                WHERE capture_id=? AND entity_id=? AND zone_db IN ({ph}) ORDER BY leg, step""",
            [capture_id, eid, *zdbs]).fetchall()
        legs = _legs(rows)
        meta = names.get(int(eid))
        out["npcs"].append({
            "id": int(eid),
            "name": (meta[1] if meta else None) or "?",
            "model": meta[5] if meta else None,
            "spawn": {"x": meta[2], "y": meta[3], "z": meta[4]} if meta and meta[2] is not None else None,
            "n_points": sum(len(l["points"]) for l in legs),
            "length": _length(legs),
            "legs": legs,
        })
    return out
