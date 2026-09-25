#!/usr/bin/env python3
"""Backtrace one runtime capture into server/client implementation evidence."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from datetime import datetime, timezone

SCHEMA=1

def table_exists(con,name):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None

def rows(con,sql,args=()):
    return con.execute(sql,args).fetchall()

def graph_matches(con,node_id=None,name=None):
    out=[]
    for table,key,col in [("entities","entity_id","display_name"),("features","feature_id","name"),
                          ("functions","function_id","qualified_name"),("bindings","binding_id","lua_name"),
                          ("capabilities","capability_id","name"),("artifacts","artifact_id","path")]:
        if node_id:
            r=con.execute(f"SELECT {key},{col} FROM {table} WHERE {key}=?",(node_id,)).fetchone()
            if r: out.append({"table":table,"id":r[0],"name":r[1]})
        elif name:
            for r in con.execute(f"SELECT {key},{col} FROM {table} WHERE {col} LIKE ? ORDER BY {key}",(f"%{name}%",)):
                out.append({"table":table,"id":r[0],"name":r[1]})
    return out

def canonical_opcode(value):
    raw=str(value)
    try: return f"0x{int(raw,0):03x}"
    except (TypeError,ValueError): return raw.lower()

def graph_walk(con,start,max_depth=4):
    seen={start}; frontier=[start]; edges=[]
    for depth in range(max_depth):
        if not frontier: break
        nxt=[]
        for node in frontier:
            for r in rows(con,"SELECT source_node,target_node,relationship,status,confidence,evidence_id FROM entity_relationships WHERE source_node=? ORDER BY relationship_id",(node,)):
                edge=dict(zip(("source","target","relationship","status","confidence","evidence_id"),r))
                edge["depth"]=depth+1; edges.append(edge)
                if r[1] not in seen: seen.add(r[1]); nxt.append(r[1])
        frontier=nxt
    return edges
def capability_status(con,name):
    hits=rows(con,"SELECT capability_id,name,status,value_json FROM capabilities WHERE name LIKE ? ORDER BY capability_id",(f"%{name}%",))
    if not hits: return {"status":"UNKNOWN","matches":[]}
    return {"status":"VERIFIED" if any(r[2]=="VERIFIED" for r in hits) else "PRESENT_UNVERIFIED",
            "matches":[dict(zip(("id","name","status","value"),r)) for r in hits]}

def backtrace(db,capture_id,graph_db=None):
    src=sqlite3.connect(db)
    g=sqlite3.connect(graph_db) if graph_db and Path(graph_db).exists() else None
    cap=src.execute("SELECT * FROM captures WHERE capture_id=?",(capture_id,)).fetchone()
    if not cap: raise SystemExit(f"capture {capture_id} not found")
    cols=[d[1] for d in src.execute("PRAGMA table_info(captures)")]
    report={"schema":SCHEMA,"trace_id":f"capture-trace:{capture_id}",
            "created_at":datetime.now(timezone.utc).isoformat(),
            "capture":dict(zip(cols,cap)),"observations":[],"checks":[],
            "notes":["Capture observations are runtime evidence, not server/client truth.",
                     "MISSING means no matching indexed implementation/evidence was found; UNKNOWN means the indexes cannot establish the answer.",
                     "Client availability remains UNKNOWN unless a client capability/DAT/EXE/DLL record exists."]}
    entities={}
    if table_exists(src,"capture_npc_entries"):
        for r in rows(src,"SELECT entity_id,name,zone_db,model_id,x,y,z FROM capture_npc_entries WHERE capture_id=?",(capture_id,)):
            eid,name,zone,model,x,y,z=r
            entities[eid]={"entity_id":eid,"name":name,"zone":zone,"model_id":model,"position":[x,y,z]}
    if table_exists(src,"capture_events"):
        for r in rows(src,"SELECT zone_db,seq,opcode,opcode_name,entity_id,entity_name,option,message_id,params_raw FROM capture_events WHERE capture_id=? ORDER BY seq",(capture_id,)):
            zone,seq,opcode,oname,eid,ename,option,msg,params=r
            report["observations"].append({"kind":"EVENT","seq":seq,"zone":zone,"opcode":opcode,
                "opcode_name":oname,"entity_id":eid,"entity_name":ename,"option":option,
                "message_id":msg,"params_raw":params})
            if eid is not None and eid not in entities:
                entities[eid]={"entity_id":eid,"name":ename,"zone":zone}
    for eid,obs in sorted(entities.items(),key=lambda x:x[0]):
        check={"kind":"ENTITY","entity_id":eid,"name":obs.get("name"),"zone":obs.get("zone")}
        if g:
            check["canonical_matches"]=graph_matches(g,node_id=f"npc:{eid}")
            check["server_entity_status"]="PRESENT" if check["canonical_matches"] else "UNKNOWN"
        report["checks"].append(check)
        if obs.get("name") and table_exists(src,"topaz_mob_spawn_points"):
            cand=rows(src,"SELECT mobid,mobname,groupid,pos_x,pos_y,pos_z FROM topaz_mob_spawn_points WHERE lower(mobname)=lower(?) ORDER BY mobid",(obs["name"],))
            report["checks"].append({"kind":"SPAWN_POINT","entity_id":eid,"name":obs["name"],
                "status":"PRESENT" if len(cand)==1 else ("AMBIGUOUS" if cand else "UNKNOWN"),
                "candidates":[dict(zip(("mobid","name","groupid","x","y","z"),r)) for r in cand]})
    if table_exists(src,"capture_actions"):
        for r in rows(src,"SELECT action_key,actor,actor_name,action_type,animation,category,message,name,ts FROM capture_actions WHERE capture_id=? ORDER BY action_key",(capture_id,)):
            key,actor,actor_name,atype,anim,cat,msg,name,ts=r
            item={"kind":"ACTION","action_key":key,"actor":actor,"actor_name":actor_name,
                  "action_type":atype,"animation":anim,"category":cat,"message":msg,"name":name,"ts":ts}
            if name and table_exists(src,"topaz_mob_skills"):
                cand=rows(src,"SELECT mob_skill_id,mob_skill_name,mob_anim_id FROM topaz_mob_skills WHERE lower(mob_skill_name)=lower(?) ORDER BY mob_skill_id",(name,))
                item["server_mob_skill_candidates"]=[dict(zip(("mob_skill_id","name","animation_id"),r)) for r in cand]
                item["server_data_status"]="PRESENT" if cand else "UNKNOWN"
            if g: item["client_capability"]=capability_status(g,name or f"animation:{anim}")
            report["checks"].append(item)
    if table_exists(src,"capture_raw_packets"):
        for opcode,count in rows(src,"SELECT opcode,COUNT(*) FROM capture_raw_packets WHERE capture_id=? GROUP BY opcode ORDER BY opcode",(capture_id,)):
            item={"kind":"PACKET","opcode":opcode,"observed_count":count}
            if g:
                packet_node=f"packet:{canonical_opcode(opcode)}"
                item["canonical_packet_node"]=packet_node
                item["canonical_packet_matches"]=graph_matches(g,node_id=packet_node)
                handler=rows(g,"SELECT source_node,target_node,relationship,status,confidence FROM entity_relationships WHERE source_node=? OR target_node=? ORDER BY relationship_id",(packet_node,packet_node))
                item["graph_relationships"]=[dict(zip(("source","target","relationship","status","confidence"),r)) for r in handler]
                item["implementation_path"]=graph_walk(g,packet_node,4)
                item["server_handler_status"]="PRESENT" if any(r[2]=="HANDLED_BY" for r in handler) else "UNKNOWN"
            report["checks"].append(item)
    message_ids=set()
    if table_exists(src,"capture_events"):
        message_ids.update(r[0] for r in rows(src,"SELECT message_id FROM capture_events WHERE capture_id=? AND message_id IS NOT NULL",(capture_id,)))
    if table_exists(src,"capture_eventview"):
        message_ids.update(r[0] for r in rows(src,"SELECT mes_num FROM capture_eventview WHERE capture_id=? AND mes_num IS NOT NULL",(capture_id,)))
    for mid in sorted(message_ids):
        item={"kind":"EVENT_IDENTIFIER","value":mid,"semantic_label":"MESSAGE_OR_EVENT_ID","status":"UNKNOWN",
              "note":"Resolve to CSID/startEvent/csid only when packet or server-event evidence establishes that meaning."}
        if g:
            ids=rows(g,"SELECT entity_id,identifier_type,identifier_value FROM entity_identifiers WHERE identifier_value=? ORDER BY entity_id",(str(mid),))
            item["identifier_matches"]=[dict(zip(("entity_id","type","value"),r)) for r in ids]
        report["checks"].append(item)
    if g: g.close()
    src.close()
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",type=Path,default=Path("ffxi_zone_database.db"))
    ap.add_argument("--graph-db",type=Path)
    ap.add_argument("--capture-id",type=int,required=True)
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    out=json.dumps(backtrace(a.db,a.capture_id,a.graph_db),indent=2,sort_keys=True,default=str)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(out+"\n",encoding="utf-8")
    else: print(out)
if __name__=="__main__": main()
