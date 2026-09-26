#!/usr/bin/env python3
"""Synthetic regression check for the server Lua event graph bridge."""
from __future__ import annotations
import json, sqlite3, tempfile
from pathlib import Path
import workbench_connect_server
from workbench.core import graph

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); zone=root/"zone.db"; out=root/"workbench.db"
        z=sqlite3.connect(zone)
        z.execute("CREATE TABLE npc_event_refs(source TEXT, zone_name TEXT, npc_script TEXT, csid INTEGER)")
        z.execute("INSERT INTO npc_event_refs VALUES(?,?,?,?)",("topaz","Test_Zone","Test_NPC",42))
        z.commit(); z.close()
        api={"analysis":{"analysis_id":"synthetic-api","analysis_type":"CPP_API","source":"synthetic","target":None,"feature_id":None,"status":"ANALYZED","created_at":None,"tool_version":None,"findings":[],"notes":[],"source_snapshot_id":"api-snap"},
             "functions":[
                {"function_id":"function:CLuaBaseEntity::getID","qualified_name":"CLuaBaseEntity::getID","name":"getID","namespace":None,"class_name":"CLuaBaseEntity","source_snapshot_id":"api-snap","path":"src/lua.cpp","line":10,"kind":"METHOD","declaration":False,"definition":True,"signature":{"return_type":None,"parameters":[]},"evidence_id":"ev:function","notes":[]},
                {"function_id":"function:CLuaBaseEntity::getName","qualified_name":"CLuaBaseEntity::getName","name":"getName","namespace":None,"class_name":"CLuaBaseEntity","source_snapshot_id":"api-snap","path":"src/lua.cpp","line":11,"kind":"METHOD","declaration":False,"definition":True,"signature":{"return_type":None,"parameters":[]},"evidence_id":"ev:function2","notes":[]}
             ],
             "bindings":[
                {"binding_id":"binding:base:getID","lua_name":"getID","binding_system":"SOL","cpp_symbol":"CLuaBaseEntity::getID","class_name":"CLuaBaseEntity","function_id":"function:CLuaBaseEntity::getID","source_snapshot_id":"api-snap","path":"src/lua.cpp","line":20,"evidence_id":"ev:binding","status":"VERIFIED","notes":[]},
                {"binding_id":"binding:base:getName","lua_name":"getName","binding_system":"SOL","cpp_symbol":"CLuaBaseEntity::getName","class_name":"CLuaBaseEntity","function_id":"function:CLuaBaseEntity::getName","source_snapshot_id":"api-snap","path":"src/lua.cpp","line":21,"evidence_id":"ev:binding2","status":"VERIFIED","notes":[]}
             ]}
        lua={"source":"synthetic-server","source_snapshot_id":"lua-snap","events":[
            {"zone":"Test_Zone","script":"Test_NPC","path":"scripts/zones/Test_Zone/npcs/Test_NPC.lua","event_id":42,"event_expression":"csid ==","function":"onEventFinish","function_line":5,"calls":[
                {"object":"player","method":"getID","line":7,"class_hint":"CLuaBaseEntity","class_hint_source":"FUNCTION_PARAMETER_NAME"},
                {"object":"p","method":"getName","line":8,"class_hint":"CLuaBaseEntity","class_hint_source":"LOCAL_ALIAS"}
             ]},
            {"zone":"Test_Zone","script":"Test_NPC","path":"scripts/zones/Test_Zone/npcs/Test_NPC.lua","event_id":99,"event_expression":"csid ==","function":"onEventFinish","function_line":5,"calls":[]}]}
        ap=root/"api.json"; lp=root/"lua.json"; ap.write_text(json.dumps(api)); lp.write_text(json.dumps(lua))
        workbench_connect_server.import_payload(ap,out,lp,zone)
        con=sqlite3.connect(out)
        rel=con.execute("SELECT relationship,confidence,metadata_json FROM entity_relationships").fetchall()
        assert any(a=="IMPLEMENTED_BY" and b=="VERIFIED" for a,b,_ in rel), rel
        calls=[(b,json.loads(m)) for a,b,m in rel if a=="CALLS"]
        assert len(calls)==2 and all(conf=="INFERRED" for conf,_ in calls), calls
        resolutions={meta["method"]:meta["resolution"] for _conf,meta in calls}
        assert resolutions["getID"]=="PARAMETER_CLASS_HINT", calls
        assert resolutions["getName"]=="LOCAL_ALIAS_CLASS_HINT", calls
        assert con.execute("SELECT COUNT(*) FROM entity_relationships WHERE source_node LIKE 'event:%:99'").fetchone()[0]==0
        assert con.execute("SELECT COUNT(*) FROM entity_relationships WHERE relationship='BINDS'").fetchone()[0]>=1
        con.close()
    print("server Lua graph bridge self-test: PASS")
    return 0
if __name__=="__main__": raise SystemExit(main())
