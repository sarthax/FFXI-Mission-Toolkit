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
from workbench.core.services import packet_correlation

def table_exists(con,name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

_ENTITY_IDENTIFIER_TYPES=(
    "npcid","mobid","entity_id","runtime_entity_id",
    "server_entity_id","client_entity_id","numeric_entity_id",
)

def _canonical_entity_for_numeric_id(con: sqlite3.Connection, numeric_id: int | None) -> str | None:
    """Resolve an observed runtime entity id only through explicit canonical entity identifiers.

    Numeric ids are reused across unrelated namespaces, so item/event/etc. identifiers do not
    participate. Ambiguous entity mappings are withheld rather than guessed.
    """
    if numeric_id is None or not table_exists(con,"entity_identifiers"):
        return None
    placeholders=",".join("?" for _ in _ENTITY_IDENTIFIER_TYPES)
    rows=con.execute(
        f"""SELECT DISTINCT entity_id
            FROM entity_identifiers
            WHERE (
                    lower(COALESCE(identifier_type,'')) IN ({placeholders})
                    OR lower(COALESCE(identifier_type,'')) LIKE 'client_snapshot_entity_id:%'
                  )
              AND CAST(identifier_value AS TEXT)=?
            ORDER BY entity_id LIMIT 3""",
        (*_ENTITY_IDENTIFIER_TYPES,str(numeric_id)),
    ).fetchall()
    return rows[0][0] if len(rows)==1 else None

def connect(db: Path, graph_db: Path, capture_id: int | None = None, lua_json: Path | None = None) -> dict:
    src=sqlite3.connect(db)
    dst=workbench_graph.init_db(graph_db)
    counts={"capture_events":0,"entity_observations":0,"raw_packet_observations":0,"eventview_observations":0,"packet_observations":0,"video_ocr_observations":0,"packet_correlations":0,"packet_correlations_ambiguous":0,"key_evidence":0,"event_nodes":0,"event_refs":0,"edges":0,"action_nodes":0,"lua_functions":0,"lua_calls":0,"binding_candidates":0}
    from workbench.captures import review_queue as _rq
    _ex=_rq.exclude_sql(src)   # captures with a pending blocking review item never feed the derived graph
    where=" WHERE 1=1"+_ex+("" if capture_id is None else " AND capture_id=?")
    args=() if capture_id is None else (capture_id,)

    # Refresh cross-source packet correlations before graph emission so re-ingestion/rebuild and
    # newly-added video alignment anchors cannot leave correlation state stale.
    packet_capture_ids=set()
    for table in ("capture_raw_packets","capture_eventview","capture_events","capture_video_observations"):
        if not table_exists(src,table):
            continue
        sql=f"SELECT DISTINCT capture_id FROM {table} WHERE 1=1"+_ex
        params=()
        if capture_id is not None:
            sql+=" AND capture_id=?"
            params=(capture_id,)
        packet_capture_ids.update(int(row[0]) for row in src.execute(sql,params))
    for cid_value in sorted(packet_capture_ids):
        summary=packet_correlation.correlate_capture(src,cid_value)
        counts["packet_correlations"]+=summary["matched"]
        counts["packet_correlations_ambiguous"]+=summary["ambiguous"]

    # Reconcile row-level runtime evidence owned by this bridge. INSERT OR REPLACE alone cannot
    # remove graph rows when a rebuilt capture now contains fewer observations.
    owned_relationship_prefixes=("capture-entity:","raw-packet-observation:","eventview-packet-observation:")
    owned_evidence_prefixes=("evidence:capture-entity:","evidence:raw-packet:","evidence:eventview-packet:")
    if capture_id is None:
        for prefix in owned_relationship_prefixes:
            dst.execute("DELETE FROM entity_relationships WHERE relationship_id LIKE ?",(prefix+"%",))
        for prefix in owned_evidence_prefixes:
            dst.execute("DELETE FROM evidence WHERE evidence_id LIKE ?",(prefix+"%",))
    else:
        for prefix in owned_relationship_prefixes:
            dst.execute(
                "DELETE FROM entity_relationships WHERE relationship_id LIKE ?",
                (f"{prefix}{int(capture_id)}:%",),
            )
        for prefix in owned_evidence_prefixes:
            dst.execute(
                "DELETE FROM evidence WHERE evidence_id LIKE ?",
                (f"{prefix}{int(capture_id)}:%",),
            )
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
                         json.dumps({
                             "capture_id":cap,
                             "capture_table":"capture_events",
                             "capture_row_key":{"zone_db":zone,"seq":seq},
                             "direction":direction,
                             "opcode":opcode,
                             "opcode_name":opcode_name,
                         },sort_keys=True),None))
            counts["packet_observations"]+=1; counts["edges"]+=1
        canonical_entity=_canonical_entity_for_numeric_id(dst,entity_id)
        if canonical_entity is not None:
            entity_ev=f"evidence:capture-entity:{cap}:{zone}:{seq}"
            dst.execute(
                "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                (entity_ev,"CAPTURE","capture_events",f"capture:{cap}:{zone}:{seq}",None,
                 "Observed runtime entity id matched one explicit canonical entity identity."),
            )
            dst.execute(
                "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                (f"capture-entity:{cap}:{zone}:{seq}",cid,canonical_entity,"OBSERVES_ENTITY",
                 entity_ev,"VERIFIED","DISCOVERED",
                 json.dumps({
                     "capture_id":cap,
                     "capture_table":"capture_events",
                     "capture_row_key":{"zone_db":zone,"seq":seq},
                     "entity_id":entity_id,
                     "entity_name":entity_name,
                     "direction":direction,
                     "opcode":opcode,
                     "opcode_name":opcode_name,
                 },sort_keys=True),None),
            )
            counts["entity_observations"]+=1
            counts["edges"]+=1

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
                         json.dumps({
                             "capture_id":cap,
                             "capture_table":"capture_events",
                             "capture_row_key":{"zone_db":zone,"seq":seq},
                             "opcode":opcode,
                             "opcode_name":opcode_name,
                             "direction":direction,
                             "message_id":message_id,
                         },sort_keys=True),
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
    # Canonical raw-packet observations: PacketLogger/PacketViewer, PacketDB, Packeteer, and
    # promoted logger-preserved packet bytes all converge here without losing source identity.
    if table_exists(src,"capture_raw_packets"):
        raw_cols={r[1] for r in src.execute("PRAGMA table_info(capture_raw_packets)")}
        sf="source_format" if "source_format" in raw_cols else "NULL AS source_format"
        sn="source_native_id" if "source_native_id" in raw_cols else "NULL AS source_native_id"
        zone="zone_id" if "zone_id" in raw_cols else "NULL AS zone_id"
        size="packet_size" if "packet_size" in raw_cols else "NULL AS packet_size"
        sync="sync_id" if "sync_id" in raw_cols else "NULL AS sync_id"
        rq=f"""SELECT capture_id,seq,ts,direction,opcode,raw_hex,{zone},{size},{sync},{sf},{sn}
              FROM capture_raw_packets"""
        rargs=()
        rq+=" WHERE 1=1"+_ex
        if capture_id is not None:
            rq+=" AND capture_id=?"
            rargs=(capture_id,)
        rq+=" ORDER BY capture_id,seq"
        for cap,seq,ts,direction,opcode,raw_hex,zone_id,packet_size,sync_id,source_format,source_native_id in src.execute(rq,rargs):
            pnode=packet_node_id(opcode)
            if pnode is None:
                continue
            cid=f"capture:{cap}"
            dst.execute(
                "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (cid,"CAPTURE",f"capture {cap}",json.dumps({"capture_id":cap})),
            )
            dst.execute(
                "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (pnode,"PACKET",pnode.removeprefix("packet:"),
                 json.dumps({"opcode":opcode},sort_keys=True)),
            )
            evidence_id=f"evidence:raw-packet:{cap}:{seq}"
            dst.execute(
                "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                (evidence_id,"PACKET_CAPTURE","capture_raw_packets",
                 f"capture:{cap}:packet:{seq}",None,
                 "Exact raw packet observation; packet bytes and source provenance remain in the capture store."),
            )
            metadata={
                "source_kind":"RAW_PACKET",
                "capture_id":cap,
                "capture_table":"capture_raw_packets",
                "capture_row_key":{"seq":seq},
                "seq":seq,
                "timestamp":ts,
                "direction":direction,
                "opcode":opcode,
                "byte_length":len(raw_hex or "")//2,
                "has_raw_bytes":bool(raw_hex),
                "zone_id":zone_id,
                "packet_size":packet_size,
                "sync_id":sync_id,
                "source_format":source_format,
                "source_native_id":source_native_id,
            }
            dst.execute(
                "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                (f"raw-packet-observation:{cap}:{seq}",cid,pnode,"OBSERVES_PACKET",
                 evidence_id,"VERIFIED","DISCOVERED",json.dumps(metadata,sort_keys=True),None),
            )
            counts["raw_packet_observations"]+=1
            counts["packet_observations"]+=1
            counts["edges"]+=1

    # EventView observations are decoded packet evidence, not raw-byte evidence. Preserve packet
    # class / GP command / decoded fields as metadata and keep a distinct relationship/evidence
    # identity even when the same packet opcode also exists in PacketLogger.
    if table_exists(src,"capture_eventview"):
        eq="""SELECT capture_id,zone_db,seq,ts,direction,opcode,packet_class,gp_command,
                    entity_id,mes_num,message_number,fields_json
              FROM capture_eventview"""
        eargs=()
        eq+=" WHERE 1=1"+_ex
        if capture_id is not None:
            eq+=" AND capture_id=?"
            eargs=(capture_id,)
        eq+=" ORDER BY capture_id,zone_db,seq"
        for cap,zone,seq,ts,direction,opcode,packet_class,gp_command,entity_id,mes_num,message_number,fields_json in src.execute(eq,eargs):
            pnode=packet_node_id(opcode)
            if pnode is None:
                continue
            cid=f"capture:{cap}"
            dst.execute(
                "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (cid,"CAPTURE",f"capture {cap}",json.dumps({"capture_id":cap})),
            )
            dst.execute(
                "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                (pnode,"PACKET",pnode.removeprefix("packet:"),
                 json.dumps({"opcode":opcode,"gp_command":gp_command,"packet_class":packet_class},sort_keys=True)),
            )
            evidence_id=f"evidence:eventview-packet:{cap}:{zone}:{seq}"
            dst.execute(
                "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                (evidence_id,"CAPTURE_DECODE","capture_eventview",
                 f"capture:{cap}:eventview:{zone}:{seq}",None,
                 "Decoded EventView packet observation; this does not claim possession of raw packet bytes."),
            )
            try:
                decoded_fields=json.loads(fields_json) if fields_json else {}
            except json.JSONDecodeError:
                decoded_fields={}
            metadata={
                "source_kind":"EVENTVIEW_DECODE",
                "capture_id":cap,
                "capture_table":"capture_eventview",
                "capture_row_key":{"zone_db":zone,"seq":seq},
                "zone_db":zone,
                "seq":seq,
                "timestamp":ts,
                "direction":direction,
                "opcode":opcode,
                "packet_class":packet_class,
                "gp_command":gp_command,
                "entity_id":entity_id,
                "mes_num":mes_num,
                "message_number":message_number,
                "fields":decoded_fields,
            }
            dst.execute(
                "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                (f"eventview-packet-observation:{cap}:{zone}:{seq}",cid,pnode,
                 "OBSERVES_EVENTVIEW_PACKET",evidence_id,"VERIFIED","DISCOVERED",
                 json.dumps(metadata,sort_keys=True),None),
            )
            counts["eventview_observations"]+=1
            counts["packet_observations"]+=1
            counts["edges"]+=1

    # Video OCR packet observations are deliberately separate from capture_raw_packets:
    # the video proves only that an opcode/field rendering was visible on screen, not packet bytes.
    if table_exists(src,"capture_video_observations"):
        vq="""SELECT capture_id,observation_id,ocr_run_id,section,frame,video_ts,source_url,
                    observation_type,direction,opcode,gp_command,packet_class,fields_json,
                    raw_text,corrected_text,ocr_confidence,provenance_json
             FROM capture_video_observations"""
        vargs=()
        vq+=" WHERE 1=1"+_ex
        if capture_id is not None:
            vq+=" AND capture_id=?"
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

    if not any(table_exists(src,name) for name in (
        "capture_events","capture_raw_packets","capture_eventview","capture_video_observations"
    )):
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
        kq+=" WHERE 1=1"+_ex
        if capture_id is not None:
            kq+=" AND capture_id=?"
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
        aq="SELECT capture_id,action_key,actor,actor_name,action_type,animation,category,message,name FROM capture_actions"+where
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
                             ev,"INFERRED","DISCOVERED",json.dumps({
                                 "capture_id":cap,
                                 "capture_table":"capture_actions",
                                 "capture_row_key":{"action_key":key},
                                 "action_key":key,
                                 "actor":actor,
                                 "animation":animation,
                             },sort_keys=True),None))
                counts["action_nodes"]+=1; counts["edges"]+=1
    workbench_graph.resolve_relationships(dst)
    dst.commit(); dst.close(); src.close()
    return {"schema":1,"status":"OK","source_db":str(db),"graph_db":str(graph_db),"capture_id":capture_id,"counts":counts}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",type=Path,default=Path("ffxi_zone_database.db"))
    ap.add_argument("--graph-db",type=Path,default=Path("workbench.db"))
    ap.add_argument("--capture-id",type=int)
    ap.add_argument("--lua-json",type=Path,help="Lua event-surface JSON produced by python -m workbench.analyzers.server.lua_events")
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    out=json.dumps(connect(a.db,a.graph_db,a.capture_id,a.lua_json),indent=2,sort_keys=True)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(out+"\n",encoding="utf-8")
    else: print(out)
if __name__=="__main__": main()
