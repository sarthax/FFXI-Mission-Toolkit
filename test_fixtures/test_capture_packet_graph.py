#!/usr/bin/env python3
"""Regression check for capture -> canonical packet -> C++ handler traversal."""
from __future__ import annotations
import json, sqlite3, tempfile
from pathlib import Path
import workbench_connect
from workbench.core import graph

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); zone=root/"zone.db"; out=root/"workbench.db"
        src=sqlite3.connect(zone)
        src.execute("CREATE TABLE capture_raw_packets(capture_id INTEGER, opcode TEXT, direction TEXT)")
        src.execute("INSERT INTO capture_raw_packets VALUES(?,?,?)",(7,"42","S2C"))
        src.commit(); src.close()

        con=graph.init_db(out)
        con.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                    ("packet:0x02a","PACKET","0x02a","{}"))
        graph.insert_record(con,{"function_id":"function:handle_dialog","qualified_name":"handle_dialog","name":"handle_dialog",
            "namespace":None,"class_name":None,"source_snapshot_id":"snap","path":"server.cpp","line":10,"kind":"FUNCTION",
            "declaration":False,"definition":True,"signature":{},"evidence_id":None,"notes":[]},"Function")
        con.execute("INSERT INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
                    ("packet-handler","packet:0x02a","cpp-symbol:handle_dialog","HANDLED_BY","server-ev","VERIFIED","DISCOVERED","{}","snap"))
        con.commit(); con.close()

        workbench_connect.connect(zone,out)
        con=sqlite3.connect(out)
        obs=con.execute("SELECT target_node,confidence FROM entity_relationships WHERE source_node='capture:7' AND relationship='OBSERVES'").fetchall()
        assert ("packet:0x02a","VERIFIED") in obs, obs
        handler=con.execute("SELECT target_node,confidence FROM entity_relationships WHERE source_node='packet:0x02a' AND relationship='HANDLED_BY'").fetchone()
        assert handler==("function:handle_dialog","VERIFIED"), handler
        assert con.execute("SELECT COUNT(*) FROM entities WHERE entity_id='packet:42'").fetchone()[0]==0
        con.close()
    print("capture packet graph self-test: PASS")
if __name__=="__main__": main()
