#!/usr/bin/env python3
"""Connect the existing consolidated FFXI index into the canonical Workbench graph.

This adapter deliberately does not copy every source table into the graph. The existing SQLite
database remains the detailed source/index cache; this layer creates stable graph nodes and
evidence-backed relationships that let Feature Trace move between systems.

Reference/wiki data is navigation evidence only. Capture data is observed runtime evidence.
Neither is promoted to server/client truth by this connector.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import workbench_graph
from workbench_schema import Feature
import re


def _add_entity(con, entity_id, entity_type, display_name, metadata=None):
    con.execute(
        "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
        (entity_id, entity_type, display_name, json.dumps(metadata or {}, sort_keys=True)),
    )


def _identifier(con, entity_id, kind, value):
    con.execute(
        "INSERT OR IGNORE INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",
        (entity_id, kind, str(value)),
    )


def _evidence(con, evidence_id, evidence_type, source, location=None, notes=None):
    con.execute(
        "INSERT OR REPLACE INTO evidence(evidence_id,evidence_type,source,location,snapshot,notes) VALUES(?,?,?,?,?,?)",
        (evidence_id, evidence_type, source, location, None, notes),
    )


def _edge(con, rid, src, dst, rel, evidence_id, confidence="VERIFIED", status="DISCOVERED", metadata=None):
    con.execute(
        "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
        (rid, src, dst, rel, evidence_id, confidence, status,
         json.dumps(metadata or {}, sort_keys=True), None),
    )


def connect(db: Path, graph_db: Path, limit: int | None = None) -> dict:
    src = sqlite3.connect(db)
    dst = workbench_graph.init_db(graph_db)
    counts = {"entities": 0, "identifiers": 0, "evidence": 0, "edges": 0}

    def add_entity(*args):
        _add_entity(dst, *args)
        counts["entities"] += 1

    def add_identifier(*args):
        _identifier(dst, *args)
        counts["identifiers"] += 1

    def add_evidence(*args):
        _evidence(dst, *args)
        counts["evidence"] += 1

    def add_edge(*args):
        _edge(dst, *args)
        counts["edges"] += 1

    # NPC/entity index -> canonical entity. This is the primary bridge for Entity Profile,
    # Wiki, server SQL/Lua, and captures.
    try:
        q = "SELECT npcid,name,zoneid FROM npc_names ORDER BY npcid"
        if limit:
            q += f" LIMIT {int(limit)}"
        for npcid, name, zoneid in src.execute(q):
            eid = f"npc:{npcid}"
            add_entity(eid, "NPC", name, {"zoneid": zoneid})
            add_identifier(eid, "npcid", npcid)
            ev = f"evidence:topaz-npc:{npcid}"
            add_evidence(ev, "SERVER_DB", "ffxi_zone_database", "npc_names", "Indexed NPC identity")
            # Capture observation bridge.
            for cap_id, cap_name in src.execute(
                "SELECT DISTINCT capture_id,name FROM capture_npc_entries WHERE entity_id=? ORDER BY capture_id",
                (npcid,),
            ):
                cid = f"capture:{cap_id}"
                add_entity(cid, "CAPTURE", cap_name or f"capture {cap_id}", {"capture_id": cap_id})
                add_identifier(cid, "capture_id", cap_id)
                cev = f"evidence:capture:{cap_id}:npc:{npcid}"
                add_evidence(cev, "CAPTURE", "build_capture_index", f"capture_npc_entries:{cap_id}:{npcid}",
                             "Observed runtime entity occurrence")
                add_edge(f"observed:{cap_id}:{npcid}", cid, eid, "OBSERVES", cev, "VERIFIED",
                         "DISCOVERED", {"entity_id": npcid})

    _add_entity(dst, "domain:assault", "DOMAIN", "Assault", {"source": "ffxi_zone_database"})

    # Assault mission index -> canonical feature/entity. Kept generic enough that other domain
    # adapters can later add Salvage/Nyzul/etc without changing the core graph.
    try:
        for mid, name in src.execute("SELECT mission_id,name FROM assault_missions ORDER BY mission_id"):
            fid = f"feature:assault-mission:{mid}"
            workbench_graph.insert_record(dst, Feature(fid, name, "MISSION", "Assault", status="DISCOVERED", metadata={"mission_id": mid}))
            add_entity(fid, "FEATURE", name, {"domain": "Assault", "mission_id": mid})
            add_identifier(fid, "mission_id", mid)
            ev = f"evidence:server-db:assault-mission:{mid}"
            add_evidence(ev, "SERVER_DB", "ffxi_zone_database", "assault_missions", "Indexed mission identity")
            add_edge(f"mission-entity:{mid}", fid, f"domain:assault", "BELONGS_TO", ev, "VERIFIED",
                     "DISCOVERED", {"domain": "Assault"})
    except sqlite3.OperationalError:
        pass

    # Wiki is explicitly a reference/navigation layer. Create page nodes and links to canonical
    # NPCs where the normalized page title matches an indexed NPC name.
    try:
        for norm, title, url in src.execute("SELECT norm_title,title,url FROM wiki_pages ORDER BY norm_title"):
            wid = f"wiki:page:{norm}"
            add_entity(wid, "REFERENCE_PAGE", title, {"url": url, "source": "BGWiki"})
            add_identifier(wid, "wiki_norm_title", norm)
            ev = f"evidence:wiki:{norm}"
            add_evidence(ev, "REFERENCE", "BGWiki", url, "Reference/navigation only")
            npc = None
            for npcid, npc_name in src.execute("SELECT npcid,name FROM npc_names"):
                if re.sub(r"[^a-z0-9]", "", (npc_name or "").lower()) == norm:
                    npc = npcid
                    break
            if npc is not None:
                add_edge(f"wiki-about:{norm}:npc:{npc}", wid, f"npc:{npc}", "REFERENCES", ev,
                         "VERIFIED", "DISCOVERED", {"role": "navigation", "reference_only": True})
    except sqlite3.OperationalError:
        pass

    # Preserve existing packet/capture evidence as navigable nodes without pretending that a
    # packet occurrence identifies its server implementation.
    try:
        for cap_id, opcode, direction in src.execute(
            "SELECT DISTINCT capture_id,opcode,direction FROM capture_raw_packets ORDER BY capture_id,opcode,direction"
        ):
            raw = str(opcode)
            try:
                value = int(raw, 0)
                canonical = f"0x{value:03x}"
            except (TypeError, ValueError):
                canonical = raw.lower()
            pid = f"packet:{canonical}"
            add_entity(pid, "PACKET", str(opcode), {"opcode": opcode})
            add_identifier(pid, "opcode", opcode)
            cev = f"evidence:capture-packet:{cap_id}:{opcode}:{direction}"
            add_evidence(cev, "PACKET_CAPTURE", "capture_raw_packets", f"capture:{cap_id}", "Observed packet")
            add_edge(f"capture-packet:{cap_id}:{opcode}:{direction}", f"capture:{cap_id}", pid,
                     "OBSERVES", cev, "VERIFIED", "DISCOVERED", {"direction": direction})
    except sqlite3.OperationalError:
        pass

    dst.commit()
    workbench_graph.resolve_relationships(dst)
    dst.commit()
    result = {"schema": 1, "source_db": str(db), "graph_db": str(graph_db), "counts": counts}
    dst.close()
    src.close()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("ffxi_zone_database.db"))
    ap.add_argument("--graph-db", type=Path, default=Path("workbench.db"))
    ap.add_argument("--limit", type=int, default=None, help="Limit NPC entities for development/testing.")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    result = connect(args.db, args.graph_db, args.limit)
    out = json.dumps(result, indent=2, sort_keys=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(out + "\n", encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    main()
