"""Evidence-gated Salvage reconstruction dossier.

This service organizes already-ingested capture evidence into implementation-facing buckets.
It never invents SQL ids, instance ownership, Lua conditions, destinations, or CSIDs.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _columns(con: sqlite3.Connection, name: str) -> set[str]:
    if not _table_exists(con, name):
        return set()
    return {r[1] for r in con.execute(f"PRAGMA table_info({name})")}


def _dict_rows(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _path_regions(path_rows: list[dict], entities: list[dict]) -> tuple[list[dict], list[dict]]:
    """Build conservative spatial-region candidates from parser-native PC path legs.

    A capture path leg is an observed trace region, not a proven Salvage floor or room.
    Entity overlap uses only the observed X/Z envelope. It deliberately does not assign
    ownership when an entity overlaps multiple legs or infer boundaries beyond the trace.
    """
    by_leg: dict[object, list[dict]] = defaultdict(list)
    for row in path_rows:
        by_leg[row.get("leg")].append(row)

    regions: list[dict] = []
    entity_candidates: dict[object, list[str]] = defaultdict(list)
    for leg, rows in sorted(by_leg.items(), key=lambda item: (item[0] is None, item[0])):
        rows = sorted(rows, key=lambda r: (r.get("step") is None, r.get("step")))
        positioned = [r for r in rows if r.get("x") is not None and r.get("z") is not None]
        if not positioned:
            continue
        xs = [float(r["x"]) for r in positioned]
        ys = [float(r["y"]) for r in positioned if r.get("y") is not None]
        zs = [float(r["z"]) for r in positioned]
        region_id = f"pc_leg_{leg}"
        overlaps = []
        for entity in entities:
            if entity.get("x") is None or entity.get("z") is None:
                continue
            ex, ez = float(entity["x"]), float(entity["z"])
            if min(xs) <= ex <= max(xs) and min(zs) <= ez <= max(zs):
                eid = entity.get("entity_id")
                overlaps.append(eid)
                entity_candidates[eid].append(region_id)
        regions.append({
            "region_id": region_id,
            "source_leg": leg,
            "status": "OBSERVED_PATH_REGION",
            "basis": "capture_pc_path.leg + observed x/z envelope",
            "samples": len(positioned),
            "start": {k: positioned[0].get(k) for k in ("step", "x", "y", "z")},
            "end": {k: positioned[-1].get(k) for k in ("step", "x", "y", "z")},
            "bounds": {
                "min_x": min(xs), "max_x": max(xs),
                "min_y": min(ys) if ys else None, "max_y": max(ys) if ys else None,
                "min_z": min(zs), "max_z": max(zs),
            },
            "entity_overlap_candidates": sorted(e for e in overlaps if e is not None),
            "door_overlap_candidates": sorted(
                e.get("entity_id") for e in entities
                if e.get("entity_id") in overlaps and e.get("door_id") not in (None, 0)
            ),
            "floor_room_claim": "UNRESOLVED",
        })

    memberships = []
    for entity in entities:
        eid = entity.get("entity_id")
        candidates = entity_candidates.get(eid, [])
        memberships.append({
            "entity_id": eid,
            "name": entity.get("name"),
            "candidate_regions": candidates,
            "status": (
                "SINGLE_REGION_CANDIDATE" if len(candidates) == 1
                else "AMBIGUOUS_REGION_CANDIDATE" if len(candidates) > 1
                else "NO_PATH_REGION_OVERLAP"
            ),
        })
    return regions, memberships


def build_dossier(con: sqlite3.Connection, capture_id: int, zone_db: str | None = None) -> dict:
    cap = con.execute(
        "SELECT capture_id,capture_label,content_type,zones,mission_name,client_build,start_time,ingested_at "
        "FROM captures WHERE capture_id=?", (capture_id,)
    ).fetchone()
    if cap is None:
        raise ValueError(f"capture {capture_id} not found")
    capture = dict(zip(("capture_id","capture_label","content_type","zones","mission_name","client_build","start_time","ingested_at"), cap))

    zones = []
    if _table_exists(con, "capture_npc_entries"):
        zones = [r[0] for r in con.execute(
            "SELECT DISTINCT zone_db FROM capture_npc_entries WHERE capture_id=? AND zone_db IS NOT NULL ORDER BY zone_db",
            (capture_id,),
        )]
    selected_zone = zone_db or (zones[0] if len(zones) == 1 else None)

    dossier = {
        "capture": capture,
        "zones": zones,
        "selected_zone": selected_zone,
        "entities": [],
        "doors": [],
        "interaction_candidates": [],
        "entity_state_changes": [],
        "event_observations": [],
        "movement": [],
        "player_path": [],
        "spatial_regions": [],
        "entity_region_candidates": [],
        "actions": [],
        "gaps": [],
        "proposal_readiness": {},
    }
    if selected_zone is None:
        dossier["gaps"].append("Select a zone before producing implementation-facing reconstruction buckets.")
        return dossier

    cne_cols = _columns(con, "capture_npc_entries")
    if cne_cols:
        wanted = [c for c in ("entity_id","name","model_id","x","y","z","dir","hpp","door_id","act_index","sub_kind") if c in cne_cols]
        cur = con.execute(
            f"SELECT {','.join(wanted)} FROM capture_npc_entries WHERE capture_id=? AND zone_db=? ORDER BY entity_id",
            (capture_id, selected_zone),
        )
        dossier["entities"] = _dict_rows(cur)
        for row in dossier["entities"]:
            if row.get("door_id") not in (None, 0):
                dossier["doors"].append({**row, "basis": "capture_npc_entries.door_id"})
            if row.get("door_id") not in (None, 0) or row.get("act_index") not in (None, 0) or row.get("sub_kind") not in (None, 0):
                dossier["interaction_candidates"].append({**row, "basis": "captured interactive entity fields"})

    if _table_exists(con, "capture_npc_history"):
        dossier["entity_state_changes"] = _dict_rows(con.execute(
            "SELECT entity_id,COUNT(*) observations,MIN(ts) first_ts,MAX(ts) last_ts "
            "FROM capture_npc_history WHERE capture_id=? AND zone_db=? GROUP BY entity_id ORDER BY entity_id",
            (capture_id, selected_zone),
        ))

    if _table_exists(con, "capture_events"):
        dossier["event_observations"] = _dict_rows(con.execute(
            "SELECT seq,direction,opcode,opcode_name,entity_id,entity_name,event_hex,option,message_id,params_raw "
            "FROM capture_events WHERE capture_id=? AND zone_db=? ORDER BY seq",
            (capture_id, selected_zone),
        ))

    if _table_exists(con, "capture_npc_path"):
        dossier["movement"] = _dict_rows(con.execute(
            "SELECT entity_id,COUNT(*) samples,COUNT(DISTINCT leg) legs,MIN(x) min_x,MAX(x) max_x,MIN(y) min_y,MAX(y) max_y,MIN(z) min_z,MAX(z) max_z "
            "FROM capture_npc_path WHERE capture_id=? AND zone_db=? GROUP BY entity_id ORDER BY entity_id",
            (capture_id, selected_zone),
        ))

    if _table_exists(con, "capture_pc_path"):
        dossier["player_path"] = _dict_rows(con.execute(
            "SELECT leg,COUNT(*) samples,MIN(step) first_step,MAX(step) last_step,MIN(x) min_x,MAX(x) max_x,MIN(y) min_y,MAX(y) max_y,MIN(z) min_z,MAX(z) max_z "
            "FROM capture_pc_path WHERE capture_id=? AND zone_db=? GROUP BY leg ORDER BY leg",
            (capture_id, selected_zone),
        ))
        raw_path = _dict_rows(con.execute(
            "SELECT leg,step,x,y,z FROM capture_pc_path WHERE capture_id=? AND zone_db=? ORDER BY leg,step",
            (capture_id, selected_zone),
        ))
        dossier["spatial_regions"], dossier["entity_region_candidates"] = _path_regions(raw_path, dossier["entities"])

    entity_ids = {r.get("entity_id") for r in dossier["entities"] if r.get("entity_id") is not None}
    if _table_exists(con, "capture_actions"):
        if entity_ids:
            marks = ",".join("?" for _ in entity_ids)
            dossier["actions"] = _dict_rows(con.execute(
                f"SELECT actor,actor_name,action_type,name,animation,message,COUNT(*) observations FROM capture_actions "
                f"WHERE capture_id=? AND actor IN ({marks}) GROUP BY actor,actor_name,action_type,name,animation,message ORDER BY actor,observations DESC",
                (capture_id, *sorted(entity_ids)),
            ))
        else:
            dossier["actions"] = []

    event_entities = {r.get("entity_id") for r in dossier["event_observations"] if r.get("entity_id") is not None}
    dossier["proposal_readiness"] = {
        "npc_or_mob_rows": "READY_FOR_REVIEW" if dossier["entities"] else "NO_EVIDENCE",
        "floor_room_segmentation": "PARTIAL" if dossier["spatial_regions"] else "NO_EVIDENCE",
        "door_state_rows": "READY_FOR_REVIEW" if dossier["doors"] and dossier["entity_state_changes"] else ("PARTIAL" if dossier["doors"] else "NO_EVIDENCE"),
        "instance_entities": "PARTIAL" if dossier["entities"] else "NO_EVIDENCE",
        "mob_paths": "READY_FOR_REVIEW" if dossier["movement"] else "NO_EVIDENCE",
        "mob_lua": "PARTIAL" if dossier["actions"] else "NO_EVIDENCE",
        "telepad_csid_mapping": "PARTIAL" if dossier["event_observations"] else "NO_EVIDENCE",
        "telepad_destination": "PARTIAL" if dossier["event_observations"] and dossier["player_path"] else "NO_EVIDENCE",
        "zone_or_instance_lua": "PARTIAL" if dossier["event_observations"] else "NO_EVIDENCE",
    }
    if event_entities - entity_ids:
        dossier["gaps"].append("Some event actors are not present in capture_npc_entries; resolve identity before generating NPC/telepad rows.")
    if dossier["event_observations"]:
        dossier["gaps"].append("Event/option observations are evidence only; destination and Lua condition ownership still require correlated player movement/server/reference evidence.")
    if not dossier["player_path"] and dossier["event_observations"]:
        dossier["gaps"].append("No player path evidence is available to correlate telepad activation with a destination.")
    if dossier["spatial_regions"]:
        dossier["gaps"].append("Player path legs are observed spatial regions only; they are not proven Salvage floors or rooms until door/telepad/reference evidence establishes boundaries.")
        if any(r["status"] == "AMBIGUOUS_REGION_CANDIDATE" for r in dossier["entity_region_candidates"]):
            dossier["gaps"].append("Some entities overlap multiple observed path regions; keep floor/room ownership unresolved until stronger boundary evidence exists.")
    elif dossier["player_path"]:
        dossier["gaps"].append("Player path summary exists but no positioned path samples were available for spatial segmentation.")
    if not dossier["movement"]:
        dossier["gaps"].append("No captured NPC path evidence for this zone; do not infer roaming paths.")
    if dossier["doors"] and not dossier["entity_state_changes"]:
        dossier["gaps"].append("Door entities were observed but no NPC history is available; initial/final state must not be mistaken for an open/close transition rule.")
    return dossier


def dossier_json(con: sqlite3.Connection, capture_id: int, zone_db: str | None = None) -> str:
    return json.dumps(build_dossier(con, capture_id, zone_db), indent=2, sort_keys=True)
