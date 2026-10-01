"""Shared capture spatial entity queries for 2D/3D visualization."""
from __future__ import annotations

import sqlite3


def capture_spatial_entities(
    con: sqlite3.Connection,
    capture_id: int,
    zone_db: str,
    q: str = "",
) -> list[dict]:
    """Return every capture-observed entity with a real XYZ position in one zone.

    Path presence is annotated separately so fixed NPCs/props remain visible instead of being
    silently dropped by the legacy path-only viewers.
    """
    q_norm = (q or "").strip().lower()
    path_ids = {
        int(r[0]) for r in con.execute(
            "SELECT DISTINCT entity_id FROM capture_npc_path WHERE capture_id=? AND zone_db=?",
            (capture_id, zone_db),
        ).fetchall()
    }
    rows = con.execute(
        """SELECT entity_id,name,model_id,x,y,z,hpp,door_id,act_index,sub_kind
           FROM capture_npc_entries
           WHERE capture_id=? AND zone_db=? AND x IS NOT NULL AND y IS NOT NULL AND z IS NOT NULL
           ORDER BY COALESCE(name,''),entity_id""",
        (capture_id, zone_db),
    ).fetchall()
    out = []
    for row in rows:
        entity_id = int(row[0])
        name = row[1] or ""
        if q_norm and q_norm not in name.lower() and q_norm not in str(entity_id):
            continue
        out.append({
            "id": entity_id,
            "n": name or "?",
            "model": row[2],
            "x": row[3],
            "y": row[4],
            "z": row[5],
            "hpp": row[6],
            "door_id": row[7],
            "act_index": row[8],
            "sub_kind": row[9],
            "has_path": entity_id in path_ids,
            "k": "c",
        })
    return out
