#!/usr/bin/env python3
"""Regression checks for deterministic C++ graph symbol alias resolution."""
from __future__ import annotations
import json, tempfile
from pathlib import Path
from workbench.core import graph

def fn(fid, qualified, name):
    return {"function_id":fid,"qualified_name":qualified,"name":name,"namespace":None,"class_name":None,
            "source_snapshot_id":"snap","path":"server.cpp","line":1,"kind":"FUNCTION","declaration":False,
            "definition":True,"signature":{},"evidence_id":None,"notes":[]}

def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        graph.insert_record(con,fn("function:handle_dialog","handle_dialog","handle_dialog"),"Function")
        graph.insert_record(con,fn("function:A::shared","A::shared","shared"),"Function")
        graph.insert_record(con,fn("function:B::shared","B::shared","shared"),"Function")
        for rid,target in (("r1","cpp-symbol:handle_dialog"),("r2","cpp-symbol:shared"),("r3","cpp-symbol:A::shared")):
            con.execute("INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                        (rid,"packet:0x02a",target,"HANDLED_BY","ev","VERIFIED","DISCOVERED",json.dumps({"origin":"fixture"}),"snap"))
        changed=graph.resolve_relationships(con)
        assert changed==2, changed
        r1=con.execute("SELECT target_node,metadata_json FROM entity_relationships WHERE relationship_id='r1'").fetchone()
        r2=con.execute("SELECT target_node FROM entity_relationships WHERE relationship_id='r2'").fetchone()
        r3=con.execute("SELECT target_node,metadata_json FROM entity_relationships WHERE relationship_id='r3'").fetchone()
        assert r1[0]=="function:handle_dialog" and json.loads(r1[1])["resolution"]=="exact qualified C++ symbol"
        assert json.loads(r1[1])["origin"]=="fixture"
        assert r2[0]=="cpp-symbol:shared", r2
        assert r3[0]=="function:A::shared" and json.loads(r3[1])["resolution"]=="exact qualified C++ symbol"
        assert json.loads(r3[1])["origin"]=="fixture"
        con.close()
    print("graph C++ symbol resolver self-test: PASS")
if __name__=="__main__": main()
