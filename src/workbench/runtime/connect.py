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
from workbench.core.services.packet_identity import canonical_opcode, packet_node_id
from pathlib import Path

from workbench.core import graph as workbench_graph
from workbench.core.schema import Feature
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


from workbench.captures import review_queue as _rq   # quarantined captures never feed the graph


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
            for cap_id, cap_name in src.execute(
                "SELECT DISTINCT capture_id,name FROM capture_npc_entries WHERE entity_id=?" + _rq.exclude_sql(src) + " ORDER BY capture_id",
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
    except sqlite3.OperationalError:
        pass

    _add_entity(dst, "domain:assault", "DOMAIN", "Assault", {"source": "ffxi_zone_database"})

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

    try:
        packet_cols = {row[1] for row in src.execute("PRAGMA table_info(capture_raw_packets)")}
        if "seq" in packet_cols:
            select_cols = ["capture_id", "seq", "direction", "opcode"]
            for optional in ("ts", "raw_hex"):
                if optional in packet_cols:
                    select_cols.append(optional)
            rows = src.execute(
                f"SELECT {','.join(select_cols)} FROM capture_raw_packets WHERE 1=1{_rq.exclude_sql(src)} ORDER BY capture_id,seq"
            )
            for row in rows:
                values = dict(zip(select_cols, row))
                cap_id = values["capture_id"]
                seq = values["seq"]
                direction = values.get("direction")
                opcode = values.get("opcode")
                pid = packet_node_id(opcode)
                if pid is None:
                    continue
                add_entity(pid, "PACKET", str(opcode), {"opcode": opcode})
                add_identifier(pid, "opcode", opcode)
                cev = f"evidence:raw-packet:{cap_id}:{seq}"
                add_evidence(
                    cev, "PACKET_CAPTURE", "capture_raw_packets",
                    f"capture:{cap_id}:packet:{seq}",
                    "Exact runtime packet observation; raw bytes remain in the capture store.",
                )
                raw_hex = values.get("raw_hex")
                metadata = {
                    "source_kind": "RAW_PACKET",
                    "capture_id": cap_id,
                    "capture_table": "capture_raw_packets",
                    "capture_row_key": {"seq": seq},
                    "seq": seq,
                    "timestamp": values.get("ts"),
                    "direction": direction,
                    "opcode": opcode,
                    "byte_length": len(raw_hex or "") // 2,
                    "has_raw_bytes": bool(raw_hex),
                }
                add_edge(
                    f"raw-packet-observation:{cap_id}:{seq}",
                    f"capture:{cap_id}", pid, "OBSERVES_PACKET", cev, "VERIFIED",
                    "DISCOVERED", metadata,
                )
        else:
            for cap_id, opcode, direction in src.execute(
                "SELECT DISTINCT capture_id,opcode,direction FROM capture_raw_packets WHERE 1=1"
                + _rq.exclude_sql(src) + " ORDER BY capture_id,opcode,direction"
            ):
                pid = packet_node_id(opcode)
                if pid is None:
                    continue
                add_entity(pid, "PACKET", str(opcode), {"opcode": opcode})
                add_identifier(pid, "opcode", opcode)
                cev = f"evidence:capture-packet:{cap_id}:{opcode}:{direction}"
                add_evidence(
                    cev, "PACKET_CAPTURE", "capture_raw_packets", f"capture:{cap_id}",
                    "Legacy opcode/direction summary; no source row identity is available.",
                )
                add_edge(
                    f"capture-packet:{cap_id}:{opcode}:{direction}", f"capture:{cap_id}", pid,
                    "OBSERVES", cev, "VERIFIED", "DISCOVERED",
                    {
                        "source_kind": "RAW_PACKET_SUMMARY",
                        "aggregate": True,
                        "capture_id": cap_id,
                        "direction": direction,
                        "opcode": opcode,
                    },
                )
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
