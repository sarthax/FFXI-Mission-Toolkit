#!/usr/bin/env python3
"""Import server-side analyzer outputs into the canonical Workbench graph.

This connector joins the existing C++ API, binding, dependency, and build analyzers without
duplicating their detailed indexes. Evidence remains snapshot-scoped and lexical/inferred edges
retain their original confidence.
"""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from workbench.core import graph as workbench_graph

def edge(con, row):
    con.execute("INSERT OR REPLACE INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)", (
        row["edge_id"], row["source_node"], row["target_node"], row["relationship"],
        row.get("evidence_id"), row.get("confidence","UNKNOWN"), row.get("status","DISCOVERED"),
        json.dumps({"discovered_by":row.get("discovered_by"),"source_location":row.get("source_location"),
                    "notes":row.get("notes")}, sort_keys=True),
        row.get("source_snapshot_id")))

def evidence(con, eid, typ, source, location, snapshot):
    con.execute("INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?)",
                (eid,typ,source,location,snapshot,"Imported analyzer evidence."))

def import_payload(path, db):
    payload=json.loads(path.read_text(encoding="utf-8"))
    con=workbench_graph.init_db(db)
    analysis=payload.get("analysis",{})
    sid=analysis.get("source_snapshot_id")
    source=analysis.get("source",str(path))
    imported={"functions":0,"bindings":0,"enums":0,"targets":0,"edges":0}
    for row in payload.get("functions",[]):
        workbench_graph.insert_record(con,row,"Function"); imported["functions"]+=1
        eid=row.get("evidence_id") or (f"snapshot:{sid}" if sid else None)
        if eid:
            evidence(con,eid,"SERVER_SOURCE",source,row.get("path"),sid)
    for row in payload.get("bindings",[]):
        workbench_graph.insert_record(con,row,"Binding"); imported["bindings"]+=1
        eid=row.get("evidence_id") or f"snapshot:{sid}" if sid else None
        if eid: evidence(con,eid,"SERVER_SOURCE",source,row.get("path"),sid)
    for row in payload.get("enums_constants",[]):
        workbench_graph.insert_record(con,row,"EnumDefinition"); imported["enums"]+=1
        eid=row.get("evidence_id") or f"snapshot:{sid}" if sid else None
        if eid: evidence(con,eid,"SERVER_SOURCE",source,row.get("path"),sid)
    for row in payload.get("build_targets",[]):
        workbench_graph.insert_record(con,row,"BuildTarget"); imported["targets"]+=1
    for row in payload.get("edges",[]):
        edge(con,row); imported["edges"]+=1
    if analysis:
        workbench_graph.insert_record(con,analysis,"AnalysisResult")
    workbench_graph.resolve_relationships(con)
    con.commit(); con.close()
    return {"schema":1,"source":source,"source_snapshot_id":sid,"input":str(path),
            "graph_db":str(db),"imported":imported}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input",type=Path,help="JSON output from cpp_api_index, cpp_dependency_index, or build_integration_index.")
    ap.add_argument("--graph-db",type=Path,default=Path("workbench.db"))
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    out=json.dumps(import_payload(a.input,a.graph_db),indent=2,sort_keys=True)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(out+"\n",encoding="utf-8")
    else: print(out)
if __name__=="__main__": raise SystemExit(main())
