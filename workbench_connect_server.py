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
from workbench.core.services.packet_identity import canonical_opcode, packet_node_id

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

def import_payload(path, db, lua_json=None, zone_db=None):
    payload=json.loads(path.read_text(encoding="utf-8"))
    con=workbench_graph.init_db(db)
    analysis=payload.get("analysis",{})
    sid=analysis.get("source_snapshot_id")
    source=analysis.get("source",str(path))
    imported={"functions":0,"bindings":0,"enums":0,"targets":0,"packets":0,"edges":0,"lua_functions":0,"lua_calls":0,"event_nodes":0}
    for row in payload.get("functions",[]):
        workbench_graph.insert_record(con,row,"Function"); imported["functions"]+=1
        eid=row.get("evidence_id") or (f"snapshot:{sid}" if sid else None)
        if eid:
            evidence(con,eid,"SERVER_SOURCE",source,row.get("path"),sid)
    for row in payload.get("bindings",[]):
        workbench_graph.insert_record(con,row,"Binding"); imported["bindings"]+=1
        eid=row.get("evidence_id") or (f"snapshot:{sid}" if sid else None)
        if eid: evidence(con,eid,"SERVER_SOURCE",source,row.get("path"),sid)
    for row in payload.get("enums_constants",[]):
        workbench_graph.insert_record(con,row,"EnumDefinition"); imported["enums"]+=1
        eid=row.get("evidence_id") or f"snapshot:{sid}" if sid else None
        if eid: evidence(con,eid,"SERVER_SOURCE",source,row.get("path"),sid)
    for row in payload.get("build_targets",[]):
        workbench_graph.insert_record(con,row,"BuildTarget"); imported["targets"]+=1
    for row in payload.get("opcodes",[]):
        opcode=row.get("opcode")
        if not opcode: continue
        canonical=canonical_opcode(opcode)
        node=packet_node_id(opcode)
        if node is None: continue
        con.execute("INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                    (node,"PACKET",canonical,json.dumps({"opcode":opcode,"location":row.get("location")},sort_keys=True)))
        con.execute("INSERT OR IGNORE INTO entity_identifiers(entity_id,identifier_type,identifier_value,source_snapshot_id) VALUES(?,?,?,?)",
                    (node,"opcode",str(opcode),sid))
        imported["packets"]+=1
    for row in payload.get("edges",[]):
        edge(con,row); imported["edges"]+=1
    # Optional Lua event-surface bridge. Event identity is only accepted when the
    # consolidated source index independently verifies the same zone/script/event ID.
    if lua_json is not None and lua_json.exists() and zone_db is not None and zone_db.exists():
        lua_payload=json.loads(lua_json.read_text(encoding="utf-8"))
        lua_sid=lua_payload.get("source_snapshot_id"); lua_source=lua_payload.get("source",str(lua_json))
        src=sqlite3.connect(zone_db)
        try:
            has_refs=src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='npc_event_refs'").fetchone()
            if has_refs:
                for row in lua_payload.get("events",[]):
                    event_id=row.get("event_id"); zone=row.get("zone"); script=row.get("script"); path=row.get("path"); fn=row.get("function"); fl=row.get("function_line")
                    if event_id is None or not fn: continue
                    refs=src.execute("SELECT source,zone_name,npc_script,csid FROM npc_event_refs WHERE csid=? AND lower(zone_name)=lower(?) AND lower(npc_script)=lower(?) ORDER BY source",(event_id,zone,script)).fetchall()
                    for source_ref,zref,nref,csid in refs:
                        enode=f"event:{source_ref}:{zref}:{nref}:{csid}"; fnode=f"lua:function:{source_ref}:{path}:{fl}:{fn}"
                        ev=f"evidence:lua-event-surface:{source_ref}:{path}:{event_id}:{fl}"
                        con.execute("INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",(fnode,"LUA_FUNCTION",fn,json.dumps({"source":source_ref,"path":path,"line":fl,"function":fn},sort_keys=True)))
                        con.execute("INSERT OR IGNORE INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",(fnode,"lua_function",f"{source_ref}:{path}:{fl}:{fn}"))
                        con.execute("INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",(ev,"SERVER_SOURCE",lua_source,path,lua_sid,"Lua event-surface handler independently matched npc_event_refs."))
                        con.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",(f"lua-event-function:{enode}:{fnode}",enode,fnode,"IMPLEMENTED_BY",ev,"VERIFIED","DISCOVERED",json.dumps({"event_expression":row.get("event_expression"),"event_id":event_id}),lua_sid))
                        imported["lua_functions"]+=1; imported["event_nodes"]+=1
                        for call in row.get("calls",[]):
                            method=call.get("method")
                            if not method: continue
                            class_hint=call.get("class_hint")
                            if class_hint:
                                matches=con.execute("SELECT binding_id,lua_name,cpp_symbol,function_id,class_name FROM bindings WHERE lower(lua_name)=lower(?) AND lower(class_name)=lower(?) ORDER BY binding_id",(method,class_hint)).fetchall()
                                hint_source=call.get("class_hint_source")
                                resolution={
                                    "FUNCTION_PARAMETER_NAME":"PARAMETER_CLASS_HINT",
                                    "LOCAL_ALIAS":"LOCAL_ALIAS_CLASS_HINT",
                                    "CONFIGURED_RETURN_TYPE":"RETURN_TYPE_CLASS_HINT",
                                }.get(hint_source,"CLASS_HINT")
                                confidence="INFERRED"
                            else:
                                matches=con.execute("SELECT binding_id,lua_name,cpp_symbol,function_id,class_name FROM bindings WHERE lower(lua_name)=lower(?) ORDER BY binding_id",(method,)).fetchall()
                                resolution="NAME_ONLY_CANDIDATE"; confidence="INFERRED"
                            for bid,lname,cpp_symbol,function_id,class_name in matches:
                                be=f"evidence:lua-call:{source_ref}:{path}:{call.get('line')}:{method}:{bid}"
                                note=(
                                    f"Lua method matched binding using inferred class hint from {call.get('class_hint_source')}."
                                    if class_hint else
                                    "Lua method name matched indexed binding; class/object semantics remain unresolved."
                                )
                                con.execute("INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",(be,"SERVER_SOURCE",lua_source,path,lua_sid,note))
                                con.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",(f"lua-call:{fnode}:{bid}",fnode,bid,"CALLS",be,confidence,"DISCOVERED",json.dumps({"object":call.get("object"),"method":method,"line":call.get("line"),"cpp_symbol":cpp_symbol,"function_id":function_id,"class_name":class_name,"class_hint":class_hint,"class_hint_source":call.get("class_hint_source"),"resolution":resolution},sort_keys=True),lua_sid))
                                imported["lua_calls"]+=1
        finally:
            src.close()
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
    ap.add_argument("--lua-json",type=Path,help="Optional Lua event-surface JSON.")
    ap.add_argument("--zone-db",type=Path,help="Consolidated DB used to independently verify Lua event IDs.")
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    out=json.dumps(import_payload(a.input,a.graph_db,a.lua_json,a.zone_db),indent=2,sort_keys=True)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(out+"\n",encoding="utf-8")
    else: print(out)
if __name__=="__main__": raise SystemExit(main())
