#!/usr/bin/env python3
"""Regression check for capture_events -> canonical packet OBSERVES edges."""
from __future__ import annotations
import sqlite3,tempfile
from pathlib import Path
from workbench.captures.correlation.graph_connect import connect
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
                    (3,"Bastok_Mines",1,"S2C","02A","event packet",17000001,"Test NPC",None,None,None,None))
        src.commit(); src.close()
        g=graph.init_db(graphdb)
        g.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                  ("npc:test","NPC","Test NPC","{}"))
        g.execute("INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",
                  ("npc:test","npcid","17000001"))
        # Reused numeric values in unrelated namespaces must not suppress the entity match.
        g.execute("INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",
                  ("item:collision","itemid","17000001"))
        g.commit(); g.close()

        result=connect(srcdb,graphdb)
        assert result["counts"]["packet_observations"]==1,result
        assert result["counts"]["entity_observations"]==1,result

        con=sqlite3.connect(graphdb)
        edge=con.execute("""SELECT source_node,target_node,relationship,confidence
                            FROM entity_relationships
                            WHERE relationship_id='capture-packet-event:3:Bastok_Mines:1'""").fetchone()
        assert edge==("capture:3","packet:0x02a","OBSERVES","VERIFIED"),edge
        assert con.execute("SELECT COUNT(*) FROM entities WHERE entity_id='packet:02a'").fetchone()[0]==0
        entity_edge=con.execute("""SELECT source_node,target_node,relationship,confidence
                                   FROM entity_relationships
                                   WHERE relationship_id='capture-entity:3:Bastok_Mines:1'""").fetchone()
        assert entity_edge==("capture:3","npc:test","OBSERVES_ENTITY","VERIFIED"),entity_edge

        # Ambiguous entity mappings are withheld rather than guessed.
        con.execute("INSERT INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                    ("mob:ambiguous","MOB","Ambiguous","{}"))
        con.execute("INSERT INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",
                    ("mob:ambiguous","mobid","17000001"))
        con.commit(); con.close()
        result=connect(srcdb,graphdb)
        assert result["counts"]["entity_observations"]==0,result
        con=sqlite3.connect(graphdb)
        assert con.execute("SELECT COUNT(*) FROM entity_relationships WHERE relationship_id='capture-entity:3:Bastok_Mines:1'").fetchone()[0]==0
        con.close()
    print("capture event packet graph self-test: PASS")

if __name__=="__main__":
    main()
