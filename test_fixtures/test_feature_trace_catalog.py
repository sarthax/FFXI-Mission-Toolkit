#!/usr/bin/env python3
"""Focused discovery and presentation regressions for Feature Trace."""
from __future__ import annotations

import sqlite3

import feature_trace
from workbench.core.services.feature_trace_catalog import present_relationships


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
    print("feature trace catalog self-test: PASS")


if __name__=="__main__":
    main()
