#!/usr/bin/env python3
"""Connect capture observations to canonical server/event/action graph nodes.

This is deliberately conservative: event/message numbers are not declared to be CSIDs unless
the indexed server event-reference table independently contains the same literal ID. Runtime
capture evidence remains OBSERVES evidence, while server source references become VERIFIED edges.
"""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from workbench.core import graph as workbench_graph
from workbench.core.services.packet_identity import packet_node_id

def table_exists(con,name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

def connect(db: Path, graph_db: Path, capture_id: int | None = None, lua_json: Path | None = None) -> dict:
    src=sqlite3.connect(db)
    dst=workbench_graph.init_db(graph_db)
    counts={"capture_events":0,"packet_observations":0,"video_ocr_observations":0,"key_evidence":0,"event_nodes":0,"event_refs":0,"edges":0,"action_nodes":0,"lua_functions":0,"lua_calls":0,"binding_candidates":0}
    where="" if capture_id is None else " WHERE capture_id=?"
    args=() if capture_id is None else (capture_id,)
    if table_exists(src,"capture_events"):
        q=f"SELECT capture_id,zone_db,seq,direction,opcode,opcode_name,entity_id,entity_name,event_hex,option,message_id,params_raw FROM capture_events{where} ORDER BY capture_id,zone_db,seq"
        capture_event_rows=src.execute(q,args)
    else:
        capture_event_rows=()
    for cap,zone,seq,direction,opcode,opcode_name,entity_id,entity_name,event_hex,option,message_id,params in capture_event_rows:
        counts["capture_events"]+=1
        cid=f"capture:{cap}"
        dst.execute("INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                    (cid,"CAPTURE",f"capture {cap}",json.dumps({"capture_id":cap})))
        pnode=packet_node_id(opcode)
        if pnode is not None:
            dst.execute("INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                        (pnode,"PACKET",pnode.removeprefix("packet:"),json.dumps({"opcode":opcode,"opcode_name":opcode_name},sort_keys=True)))
            pev=f"evidence:capture-packet-event:{cap}:{zone}:{seq}"
            dst.execute("INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                        (pev,"CAPTURE","capture_events",f"capture:{cap}:{zone}:{seq}",None,"Observed packet opcode in runtime capture event."))
            dst.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                        (f"capture-packet-event:{cap}:{zone}:{seq}",cid,pnode,"OBSERVES",pev,"VERIFIED","DISCOVERED",
                         json.dumps({"direction":direction,"opcode_name":opcode_name},sort_keys=True),None))
            counts["packet_observations"]+=1; counts["edges"]+=1
        if message_id is None: continue
        # A capture message becomes an event node only after it has a server-side event reference.
        refs=src.execute(
            "SELECT source,zone_name,npc_script,csid FROM npc_event_refs WHERE csid=? AND lower(zone_name)=lower(?) ORDER BY source,npc_script",
            (message_id,zone)).fetchall() if table_exists(src,"npc_event_refs") else []
        if not refs:
            continue
        counts["event_refs"]+=len(refs)
        for source,zone_name,npc_script,csid in refs:
            enode=f"event:{source}:{zone_name}:{npc_script}:{csid}"
            dst.execute("INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                        (enode,"SERVER_EVENT",f"{npc_script} CSID {csid}",
                         json.dumps({"source":source,"zone":zone_name,"npc_script":npc_script,"csid":csid},sort_keys=True)))
            dst.execute("INSERT OR IGNORE INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",
                        (enode,"csid",str(csid)))
            ev=f"evidence:capture-event:{cap}:{zone}:{seq}:{source}:{npc_script}:{csid}"
            dst.execute("INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                        (ev,"CAPTURE","capture_events",f"capture:{cap}:{zone}:{seq}",None,
                         "Observed identifier independently matched to indexed server event reference."))
            rid=f"capture-event:{cap}:{zone}:{seq}:{source}:{npc_script}:{csid}"
            dst.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                        (rid,cid,enode,"OBSERVES",ev,"VERIFIED","DISCOVERED",
                         json.dumps({"opcode":opcode,"opcode_name":opcode_name,"direction":direction,"message_id":message_id}),
                         None))
            counts["event_nodes"]+=1; counts["edges"]+=1
            # Event source itself is a navigable artifact path, without asserting that the script
            # is complete or that every target function exists.
            script=f"scripts/zones/{zone_name}/npcs/{npc_script}.lua"
            aid=f"artifact:lua:{source}:{zone_name}:npcs:{npc_script}"
            dst.execute("INSERT OR REPLACE INTO artifacts VALUES(?,?,?,?,?,?,?)",
                        (aid,"LUA",script,None,None,None,json.dumps({"source":source,"role":"server_event_script"})))
            rid2=f"event-script:{enode}:{aid}"
            dst.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                        (rid2,enode,aid,"IMPLEMENTED_BY",ev,"VERIFIED","DISCOVERED",
                         json.dumps({"source":source,"path":script}),None))
            counts["edges"]+=1
    # Video OCR packet observations are deliberately separate from capture_raw_packets:
    # the video proves only that an opcode/field rendering was visible on screen, not packet bytes.
    if table_exists(src,"capture_video_observations"):
        vq="""SELECT capture_id,observation_id,ocr_run_id,section,frame,video_ts,source_url,
                    observation_type,direction,opcode,gp_command,packet_class,fields_json,
                    raw_text,corrected_text,ocr_confidence,provenance_json
             FROM capture_video_observations"""
        vargs=()
        if capture_id is not None:
            vq+=" WHERE capture_id=?"
            vargs=(capture_id,)
        vq+=" ORDER BY capture_id,video_ts,observation_id"
        for cap,obs_id,run_id,section,frame,video_ts,source_url,obs_type,direction,opcode,gp_command,packet_class,fields_json,raw_text,corrected_text,ocr_confidence,provenance_json in src.execute(vq,vargs):
            counts["video_ocr_observations"]+=1
            if not opcode:
                continue
            cid=f"capture:{cap}"
            dst.execute(
                "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (cid,"CAPTURE",f"capture {cap}",json.dumps({"capture_id":cap})),
            )
            pnode=packet_node_id(opcode)
            if pnode is None:
                continue
            dst.execute(
                "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (pnode,"PACKET",pnode.removeprefix("packet:"),
                 json.dumps({"opcode":opcode,"gp_command":gp_command},sort_keys=True)),
            )
            evidence_id=f"evidence:video-ocr:{cap}:{obs_id}"
            provenance=json.loads(provenance_json) if provenance_json else {}
            metadata={
                "source_kind":"VIDEO_OCR",
                "ocr_run_id":run_id,
                "section":section,
                "frame":frame,
                "video_timestamp_seconds":video_ts,
                "source_url":source_url,
                "direction":direction,
                "opcode":opcode,
                "gp_command":gp_command,
                "packet_class":packet_class,
                "fields":json.loads(fields_json) if fields_json else None,
                "ocr_confidence":ocr_confidence,
                "corrected":bool(corrected_text),
                "provenance":provenance,
            }
            dst.execute(
                "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                (evidence_id,"VIDEO_OCR","capture_video_observations",
                 f"capture:{cap}:video-ocr:{obs_id}",None,
                 "Opcode observed in on-screen video OCR; no packet bytes are claimed."),
            )
            dst.execute(
                "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                (f"video-ocr-packet:{cap}:{obs_id}",cid,pnode,"OBSERVES",evidence_id,
                 "INFERRED","DISCOVERED",json.dumps(metadata,sort_keys=True),None),
            )
            counts["packet_observations"]+=1
            counts["edges"]+=1

    if not table_exists(src,"capture_events") and not table_exists(src,"capture_video_observations"):
        dst.close(); src.close()
        return {"schema":1,"status":"NO_RUNTIME_OBSERVATION_TABLES","counts":counts}

    # User-curated screenshots/key events are persisted as distinct evidence entities.  Their
    # existence/provenance is verified; the gameplay interpretation remains in metadata/notes and
    # is not promoted into packet/event truth by this bridge.
    if table_exists(src,"capture_key_evidence"):
        kq="""SELECT capture_id,evidence_id,evidence_type,label,video_ts,capture_ts,clock_kind,
                    anchor_id,source_ref,file_ref,mime_type,confidence,notes,metadata_json
             FROM capture_key_evidence"""
        kargs=()
        if capture_id is not None:
            kq+=" WHERE capture_id=?"
            kargs=(capture_id,)
        kq+=" ORDER BY capture_id,created_at,evidence_id"
        for cap,evidence_id,evidence_type,label,video_ts,capture_ts,clock_kind,anchor_id,source_ref,file_ref,mime_type,declared_confidence,notes,metadata_json in src.execute(kq,kargs):
            cid=f"capture:{cap}"
            enode=f"key-evidence:{cap}:{evidence_id}"
            metadata={
                "capture_id":cap,
                "evidence_id":evidence_id,
                "evidence_type":evidence_type,
                "video_timestamp_seconds":video_ts,
                "capture_timestamp_seconds":capture_ts,
                "clock_kind":clock_kind,
                "alignment_anchor_id":anchor_id,
                "source_ref":source_ref,
                "file_ref":file_ref,
                "mime_type":mime_type,
                "declared_confidence":declared_confidence,
                "metadata":json.loads(metadata_json) if metadata_json else {},
            }
            dst.execute(
                "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (cid,"CAPTURE",f"capture {cap}",json.dumps({"capture_id":cap})),
            )
            dst.execute(
                "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (enode,"KEY_EVIDENCE",label,json.dumps(metadata,sort_keys=True)),
            )
            evid=f"evidence:key-evidence:{cap}:{evidence_id}"
            dst.execute(
                "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                (evid,"KEY_EVIDENCE","capture_key_evidence",
                 f"capture:{cap}:key-evidence:{evidence_id}",None,
                 notes or "User-curated screenshot/key-event evidence."),
            )
            dst.execute(
                "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                (f"capture-key-evidence:{cap}:{evidence_id}",cid,enode,"HAS_EVIDENCE",
                 evid,"VERIFIED","DISCOVERED",json.dumps(metadata,sort_keys=True),None),
            )
            counts["key_evidence"]+=1
            counts["edges"]+=1

    # Optional Lua event-surface bridge. Event identity is proven by npc_event_refs;
    # Lua method matches remain candidate relationships until object/class semantics are resolved.
    if lua_json is not None and lua_json.exists():
        payload=json.loads(lua_json.read_text(encoding="utf-8"))
        for row in payload.get("events",[]):
            event_id=row.get("event_id"); zone_name=row.get("zone"); script=row.get("script")
            refs=src.execute("SELECT source,zone_name,npc_script,csid FROM npc_event_refs WHERE csid=? AND lower(zone_name)=lower(?) AND lower(npc_script)=lower(?) ORDER BY source",(event_id,zone_name,script)).fetchall() if table_exists(src,"npc_event_refs") else []
            for source_ref,zref,nref,csid in refs:
                enode=f"event:{source_ref}:{zref}:{nref}:{csid}"; path=row.get("path"); fn=row.get("function"); fl=row.get("function_line")
                if not fn: continue
                fnode=f"lua:function:{source_ref}:{path}:{fl}:{fn}"
                dst.execute("INSERT OR REPLACE INTO entities VALUES(?,?,?,?)",(fnode,"LUA_FUNCTION",fn,json.dumps({"source":source_ref,"path":path,"line":fl,"function":fn},sort_keys=True)))
                dst.execute("INSERT OR IGNORE INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",(fnode,"lua_function",f"{path}:{fl}:{fn}"))
                ev=f"evidence:lua-event:{source_ref}:{path}:{event_id}:{fl}"
                dst.execute("INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",(ev,"SERVER_SOURCE",payload.get("source",source_ref),path,payload.get("source_snapshot_id"),"Lua event surface index locates the handler function."))
                dst.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",(f"event-function:{enode}:{fnode}",enode,fnode,"IMPLEMENTED_BY",ev,"VERIFIED","DISCOVERED",json.dumps({"event_expression":row.get("event_expression"),"event_id":event_id}),payload.get("source_snapshot_id")))
                counts["lua_functions"]+=1; counts["edges"]+=1
                for call in row.get("calls",[]):
                    method=call.get("method"); obj=call.get("object")
                    class_hint=call.get("class_hint")
                    if method and class_hint:
                        matches=dst.execute("SELECT binding_id,lua_name,cpp_symbol,function_id FROM bindings WHERE lower(lua_name)=lower(?) AND lower(class_name)=lower(?) ORDER BY binding_id",(method,class_hint)).fetchall()
                        hint_source=call.get("class_hint_source")
                        resolution={
                            "FUNCTION_PARAMETER_NAME":"PARAMETER_CLASS_HINT",
                            "LOCAL_ALIAS":"LOCAL_ALIAS_CLASS_HINT",
                            "CONFIGURED_RETURN_TYPE":"RETURN_TYPE_CLASS_HINT",
                            "API_RETURN_TYPE":"API_RETURN_TYPE_CLASS_HINT",
                        }.get(hint_source,"CLASS_HINT")
                    else:
                        matches=dst.execute("SELECT binding_id,lua_name,cpp_symbol,function_id FROM bindings WHERE lower(lua_name)=lower(?) ORDER BY binding_id",(method,)).fetchall() if method else []
                        resolution="NAME_ONLY_CANDIDATE"
                    for bid,lname,cpp_symbol,function_id in matches:
                        be=f"evidence:lua-call:{source_ref}:{path}:{call.get('line')}:{method}:{bid}"
                        note=(f"Lua method matched binding using inferred class hint from {call.get('class_hint_source')}." if class_hint else "Lua method name matched indexed binding; class/object semantics remain unresolved.")
                        dst.execute("INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",(be,"SERVER_SOURCE",payload.get("source",source_ref),path,payload.get("source_snapshot_id"),note))
                        dst.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",(f"lua-call:{fnode}:{bid}",fnode,bid,"CALLS",be,"INFERRED","DISCOVERED",json.dumps({"object":obj,"method":method,"line":call.get("line"),"cpp_symbol":cpp_symbol,"function_id":function_id,"class_hint":class_hint,"class_hint_source":call.get("class_hint_source"),"class_hint_trace":call.get("class_hint_trace",[]),"class_hint_evidence":call.get("class_hint_evidence",{}),"resolution":resolution},sort_keys=True),payload.get("source_snapshot_id")))
                        counts["lua_calls"]+=1; counts["binding_candidates"]+=1; counts["edges"]+=1
    # Capture actions can be traced to server mob skills when names match exactly. Keep this as a
    # candidate relationship; names alone do not prove the runtime action used that skill.
    if table_exists(src,"capture_actions") and table_exists(src,"topaz_mob_skills"):
        aq="SELECT capture_id,action_key,actor,actor_name,action_type,animation,category,message,name FROM capture_actions"
        if capture_id is not None: aq+=" WHERE capture_id=?"
        for cap,key,actor,actor_name,atype,animation,category,message,name in src.execute(aq,args):
            if not name: continue
            cand=src.execute("SELECT mob_skill_id,mob_skill_name,mob_anim_id FROM topaz_mob_skills WHERE lower(mob_skill_name)=lower(?)",(name,)).fetchall()
            for skill_id,skill_name,anim_id in cand:
                snode=f"mob-skill:topaz:{skill_id}"
                dst.execute("INSERT OR REPLACE INTO entities VALUES(?,?,?,?)",
                            (snode,"MOB_SKILL",skill_name,json.dumps({"mob_skill_id":skill_id,"animation_id":anim_id})))
                ev=f"evidence:capture-action:{cap}:{key}:mobskill:{skill_id}"
                dst.execute("INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                            (ev,"CAPTURE","capture_actions",f"capture:{cap}:action:{key}",None,
                             "Runtime action name exactly matched server mob-skill name; relationship remains candidate."))
                dst.execute("INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                            (f"capture-action-skill:{cap}:{key}:{skill_id}",f"capture:{cap}",snode,"REFERENCES",
                             ev,"INFERRED","DISCOVERED",json.dumps({"action_key":key,"actor":actor,"animation":animation}),None))
                counts["action_nodes"]+=1; counts["edges"]+=1
    workbench_graph.resolve_relationships(dst)
    dst.commit(); dst.close(); src.close()
    return {"schema":1,"status":"OK","source_db":str(db),"graph_db":str(graph_db),"capture_id":capture_id,"counts":counts}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",type=Path,default=Path("ffxi_zone_database.db"))
    ap.add_argument("--graph-db",type=Path,default=Path("workbench.db"))
    ap.add_argument("--capture-id",type=int)
    ap.add_argument("--lua-json",type=Path,help="Lua event-surface JSON produced by lua_event_index.py")
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    out=json.dumps(connect(a.db,a.graph_db,a.capture_id,a.lua_json),indent=2,sort_keys=True)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(out+"\n",encoding="utf-8")
    else: print(out)
if __name__=="__main__": main()
