#!/usr/bin/env python3
"""Focused discovery and presentation regressions for Feature Trace."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import feature_trace
from workbench.core.services.feature_trace_catalog import present_relationships
from pathlib import Path


def main():
    con=sqlite3.connect(":memory:")
    con.execute("CREATE TABLE entities (entity_id TEXT, entity_type TEXT, display_name TEXT, metadata_json TEXT)")
    con.execute("CREATE TABLE sql_item_basic (itemid INTEGER, name TEXT, sortname TEXT)")
    con.executemany("INSERT INTO sql_item_basic VALUES (?,?,?)",[(2413,"Coiler","coiler"),(8583,"Coiler","coiler")])
    con.execute("INSERT INTO entities VALUES (?,?,?,?)",("entity:fixture","NPC","Coiler","{}"))
    matches=feature_trace.search_nodes(con,"cOiL")
    assert len(matches)==3 and {m["node_id"] for m in matches if m["catalog_only"]}=={"catalog:sql_item_basic:2413","catalog:sql_item_basic:8583"}
    assert feature_trace.node_info(con,"catalog:sql_item_basic:2413")["known"]
    assert feature_trace.node_info(con,"catalog:sql_item_basic:2413")["representations"][0]["metadata"]["numeric_id"]==2413
    assert len(feature_trace.search_nodes(con,"2413"))==1
    assert len(feature_trace.search_nodes(con,"Coiler"))==3  # ambiguity remains visible
    graph=sqlite3.connect(":memory:")
    graph.execute("CREATE TABLE entities (entity_id TEXT, entity_type TEXT, display_name TEXT, metadata_json TEXT)")
    graph.execute("CREATE TABLE entity_relationships (relationship_id TEXT, source_node TEXT, target_node TEXT, relationship TEXT, evidence_id TEXT, confidence TEXT, status TEXT, metadata_json TEXT, source_snapshot_id TEXT)")
    bridged=feature_trace.search_nodes(graph,"Coiler",con)
    assert any(m["node_id"]=="catalog:sql_item_basic:2413" for m in bridged)
    catalog_trace=feature_trace.trace(graph,"catalog:sql_item_basic:2413",3,"both",con)
    assert catalog_trace["nodes"][0]["known"] and not catalog_trace["edges"]
    graph.executemany("INSERT INTO entities VALUES (?,?,?,?)",[("npc:root","NPC","Root","{}"),("runtime:one","OBSERVATION","Packet one","{}"),("entity:semantic","NPC","Semantic","{}")])
    graph.executemany("INSERT INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",[
        ("semantic","npc:root","entity:semantic","IMPLEMENTS",None,"HIGH","KNOWN","{}",None),
        ("packet-1","npc:root","runtime:one","OBSERVES","ev:1","OBSERVED","KNOWN",'{"opcode":"0x00E","capture_id":1}',None),
        ("packet-2","npc:root","runtime:one","OBSERVES","ev:2","OBSERVED","KNOWN",'{"opcode":"0x00E","capture_id":2}',None),
    ])
    semantic_trace=feature_trace.trace(graph,"npc:root",3,"both",con)
    assert {node["node_id"] for node in semantic_trace["nodes"]}=={"npc:root","entity:semantic"}
    assert len(semantic_trace["edges"])==1 and semantic_trace["runtime_summary"][0]["runtime_groups"][0]["observation_count"]==2, semantic_trace
    template=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"feature_trace.html").read_text(encoding="utf-8")
    assert "do not expand the semantic trace topology" in template
    assert "semantic node(s)" in template
    edges=[
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x00E","capture_id":1},"source_snapshot_id":None},
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x00E","capture_id":2},"source_snapshot_id":None},
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x032","capture_id":1},"source_snapshot_id":None},
        {"relationship":"NEW_RELATION","metadata":{}},
    ]
    sections=present_relationships(edges)
    runtime=next(s for s in sections if s["name"]=="Runtime / Captures & Packets")
    opcode=next(g for g in runtime["runtime_groups"] if g["opcode"]=="0x00E")
    assert opcode["observation_count"]==2 and opcode["capture_count"]==2 and len(opcode["edges"])==2
    assert any(s["name"]=="Other / Unclassified" for s in sections)
    # Both production databases may differ in schema; discovery must tolerate that.
    with sqlite3.connect(Path(__file__).resolve().parents[1]/"workbench.db") as graph_db, sqlite3.connect(Path(__file__).resolve().parents[1]/"ffxi_zone_database.db") as index_db:
        feature_trace.search_nodes(graph_db,"coiler",index_db)
    print("feature trace catalog self-test: PASS")


if __name__=="__main__":
    main()
