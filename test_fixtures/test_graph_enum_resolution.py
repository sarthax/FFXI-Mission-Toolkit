#!/usr/bin/env python3
"""Regression checks for scoped enum resolution and metadata preservation."""
from __future__ import annotations
import json,tempfile
from pathlib import Path
from workbench.core import graph
from workbench_schema import EnumDefinition

def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"g.db")
        graph.insert_record(con,EnumDefinition("enum:state:READY","State",None,"state.h",1,"CXX_ENUM","1","READY"))
        con.execute("INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                    ("uses","function:test","READY","USES_ENUM","ev","INFERRED","DISCOVERED",'{"scope":"function"}',"snap"))
        con.execute("INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                    ("ref","artifact:test","READY","REFERENCES","ev","INFERRED","DISCOVERED",'{"keep":true}',"snap"))
        changed=graph.resolve_relationships(con)
        assert changed==1,changed
        uses=con.execute("SELECT target_node,metadata_json FROM entity_relationships WHERE relationship_id='uses'").fetchone()
        ref=con.execute("SELECT target_node,metadata_json FROM entity_relationships WHERE relationship_id='ref'").fetchone()
        meta=json.loads(uses[1])
        assert uses[0]=="enum:state:READY",uses
        assert meta["scope"]=="function" and meta["resolved_from"]=="READY",meta
        assert ref[0]=="READY" and json.loads(ref[1])=={"keep":True},ref
        con.close()
    print("graph enum resolver self-test: PASS")
if __name__=="__main__":
    main()
