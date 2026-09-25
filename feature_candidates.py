#!/usr/bin/env python3
"""Resolve feature candidates reachable from any canonical graph node."""
from __future__ import annotations
import argparse,json,sqlite3
from collections import deque
from pathlib import Path

def candidates(con,start,depth=6):
    queue=deque([(start,0,[])])
    seen={start}
    found=[]
    while queue:
        node,level,path=queue.popleft()
        if level>=depth:
            continue
        sql="SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,status FROM entity_relationships WHERE source_node=? OR target_node=? ORDER BY relationship_id"
        for row in con.execute(sql,(node,node)):
            rid,src,dst,rel,evidence,confidence,status=row
            other=dst if src==node else src
            step={"relationship_id":rid,"source":src,"target":dst,"relationship":rel,"evidence_id":evidence,"confidence":confidence,"status":status}
            next_path=path+[step]
            feature=con.execute("SELECT feature_id,name,feature_type,domain,status FROM features WHERE feature_id=?",(other,)).fetchone()
            if feature:
                found.append({"feature_id":feature[0],"name":feature[1],"feature_type":feature[2],"domain":feature[3],"feature_status":feature[4],"distance":level+1,"path":next_path})
            if other not in seen:
                seen.add(other)
                queue.append((other,level+1,next_path))
    found.sort(key=lambda item:(item["distance"],item["feature_id"]))
    return {"schema":1,"root":start,"max_depth":depth,"candidates":found,
            "notes":["Reachability is navigation evidence, not proof of feature ownership or requirement semantics.",
                     "Candidate paths preserve the relationship evidence used to reach each feature."]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",type=Path,default=Path("workbench.db"))
    ap.add_argument("--node",required=True)
    ap.add_argument("--depth",type=int,default=6)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    con=sqlite3.connect(args.db)
    result=candidates(con,args.node,args.depth)
    con.close()
    output=json.dumps(result,indent=2,sort_keys=True)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(output+"\n",encoding="utf-8")
    else:
        print(output)
if __name__=="__main__":
    main()
