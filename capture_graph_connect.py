#!/usr/bin/env python3
"""Connect capture observations to canonical server/event/action graph nodes.

This is deliberately conservative: event/message numbers are not declared to be CSIDs unless
the indexed server event-reference table independently contains the same literal ID. Runtime
capture evidence remains OBSERVES evidence, while server source references become VERIFIED edges.
"""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
import workbench_graph

def table_exists(con,name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

def connect(db: Path, graph_db: Path, capture_id: int | None = None) -> dict:
    src=sqlite3.connect(db)
    dst=workbench_graph.init_db(graph_db)
    counts={"capture_events":0,"event_nodes":0,"event_refs":0,"edges":0,"action_nodes":0}
    where="" if capture_id is None else " WHERE capture_id=?"
    args=() if capture_id is None else (capture_id,)
    if not table_exists(src,"capture_events"):
        return {"schema":1,"status":"NO_CAPTURE_EVENTS_TABLE","counts":counts}
    q=f"SELECT capture_id,zone_db,seq,direction,opcode,opcode_name,entity_id,entity_name,event_hex,option,message_id,params_raw FROM capture_events{where} ORDER BY capture_id,zone_db,seq"
    for cap,zone,seq,direction,opcode,opcode_name,entity_id,entity_name,event_hex,option,message_id,params in src.execute(q,args):
        counts["capture_events"]+=1
        cid=f"capture:{cap}"
        dst.execute("INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                    (cid,"CAPTURE",f"capture {cap}",json.dumps({"capture_id":cap})))
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
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    out=json.dumps(connect(a.db,a.graph_db,a.capture_id),indent=2,sort_keys=True)
    if a.json: a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(out+"\n",encoding="utf-8")
    else: print(out)
if __name__=="__main__": main()
