#!/usr/bin/env python3
"""Regression check for capture_events -> canonical packet OBSERVES edges."""
from __future__ import annotations
import sqlite3,tempfile
from pathlib import Path
from capture_graph_connect import connect
from workbench.core import graph

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); srcdb=root/"capture.db"; graphdb=root/"workbench.db"
        src=sqlite3.connect(srcdb)
        src.execute("""CREATE TABLE capture_events(
            capture_id INTEGER, zone_db TEXT, seq INTEGER, direction TEXT,
            opcode TEXT, opcode_name TEXT, entity_id INTEGER, entity_name TEXT,
            event_hex TEXT, option INTEGER, message_id INTEGER, params_raw TEXT
        )""")
        src.execute("INSERT INTO capture_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (3,"Bastok_Mines",1,"S2C","02A","event packet",None,None,None,None,None,None))
        src.commit(); src.close()
        graph.init_db(graphdb).close()

        result=connect(srcdb,graphdb)
        assert result["counts"]["packet_observations"]==1,result

        con=sqlite3.connect(graphdb)
        edge=con.execute("""SELECT source_node,target_node,relationship,confidence
                            FROM entity_relationships
                            WHERE relationship_id='capture-packet-event:3:Bastok_Mines:1'""").fetchone()
        assert edge==("capture:3","packet:0x02a","OBSERVES","VERIFIED"),edge
        assert con.execute("SELECT COUNT(*) FROM entities WHERE entity_id='packet:02a'").fetchone()[0]==0
        con.close()
    print("capture event packet graph self-test: PASS")

if __name__=="__main__":
    main()
