#!/usr/bin/env python3
"""Focused discovery and presentation regressions for Feature Trace."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import feature_trace
from workbench.core.services.feature_trace_catalog import present_relationships, runtime_hierarchy, filter_runtime_observations
from workbench.core.services.feature_trace_dossier import build_dossier
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
    assert len(semantic_trace["edges"])==1 and semantic_trace["runtime_hierarchy"]["groups"][0]["observation_count"]==2, semantic_trace
    assert "_runtime_edges" not in semantic_trace
    dossier=build_dossier(semantic_trace)
    assert dossier["identity"]["node_id"]=="npc:root" and dossier["runtime_capture_count"]==2
    assert any(f["name"]=="Implementation / Server" for f in dossier["facets"])
    template=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"feature_trace.html").read_text(encoding="utf-8")
    assert "grouped without expanding semantic topology" in template
    assert "Evidence Dossier" in template
    assert "section.edges" in template and "{% for edge in result.edges %}" not in template
    assert "/features/trace/runtime.json" in template
    assert "runtimeEsc(e.relationship)" in template
    edges=[
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x00E","capture_id":1},"source_snapshot_id":None},
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x00E","capture_id":2},"source_snapshot_id":None},
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x032","capture_id":1},"source_snapshot_id":None},
        {"relationship":"NEW_RELATION","metadata":{}},
    ]
    sections=present_relationships(edges)
    runtime=next(s for s in sections if s["name"]=="Runtime / Captures & Packets")
    opcode=next(g for g in runtime["runtime_groups"] if g["opcode"]=="0x00E")
    assert opcode["observation_count"]==2 and opcode["capture_count"]==2 and "edges" not in opcode
    hierarchy=runtime_hierarchy(edges[:3])
    assert hierarchy["observation_count"]==3 and hierarchy["capture_count"]==2
    page=filter_runtime_observations(edges[:3],"0x00E","1",0,10)
    assert page["total"]==1 and len(page["observations"])==1
    bounded=filter_runtime_observations(edges[:3],limit=9999)
    assert bounded["limit"]==250
    assert any(s["name"]=="Other / Unclassified" for s in sections)
    # Both production databases may differ in schema; discovery must tolerate that.
    with sqlite3.connect(Path(__file__).resolve().parents[1]/"workbench.db") as graph_db, sqlite3.connect(Path(__file__).resolve().parents[1]/"ffxi_zone_database.db") as index_db:
        feature_trace.search_nodes(graph_db,"coiler",index_db)
        real=feature_trace.trace(graph_db,"npc:16974347",3,"both",index_db)
        assert real["runtime_observation_count"] > 0
        assert any(group["capture_count"] > 0 for group in real["runtime_hierarchy"]["groups"])
    print("feature trace catalog self-test: PASS")


if __name__=="__main__":
    main()
