#!/usr/bin/env python3
"""P0 runtime-validation integration regression.

Proves the runtime path from capture-index tables through canonical packet evidence
and capture backtrace, alongside canonical ValidationRun/ValidationResult persistence.
"""
from pathlib import Path
import sqlite3
import tempfile

from capture_graph_connect import connect as connect_capture_graph
from capture_backtrace import backtrace
from workbench.core import graph
from workbench.core.services.validation_run import ValidationSpec, run_validation_suite


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        capture_db=root/"capture.db"
        graph_db=root/"workbench.db"

        con=sqlite3.connect(capture_db)
        con.execute(
            "CREATE TABLE captures("
            "capture_id INTEGER PRIMARY KEY,source_path TEXT,capturer TEXT,capture_label TEXT,"
            "content_type TEXT,zones TEXT,mission_name TEXT,addons TEXT,client_build TEXT,"
            "is_retail INTEGER,start_time INTEGER,ingested_at TEXT)"
        )
        con.execute(
            "CREATE TABLE capture_events("
            "capture_id INTEGER,zone_db TEXT,seq INTEGER,direction TEXT,opcode TEXT,"
            "opcode_name TEXT,entity_id INTEGER,entity_name TEXT,event_hex TEXT,"
            "option INTEGER,message_id INTEGER,params_raw TEXT)"
        )
        con.execute(
            "CREATE TABLE capture_npc_entries("
            "capture_id INTEGER,zone_db TEXT,entity_id INTEGER,name TEXT,model_id INTEGER,"
            "x REAL,y REAL,z REAL)"
        )
        con.execute(
            "CREATE TABLE capture_actions("
            "capture_id INTEGER,action_key TEXT,actor INTEGER,actor_name TEXT,"
            "action_type TEXT,animation INTEGER,category INTEGER,message INTEGER,name TEXT,ts INTEGER)"
        )
        con.execute(
            "CREATE TABLE capture_raw_packets("
            "capture_id INTEGER,seq INTEGER,ts TEXT,direction TEXT,opcode TEXT,raw_hex TEXT)"
        )
        con.execute(
            "INSERT INTO captures VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (1,"fixture.zip","tester","runtime fixture","Mission","Test_Zone","Demo",
             "NPCLogger,ActionView","30191204_1",1,0,"now"),
        )
        con.execute(
            "INSERT INTO capture_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (1,"Test_Zone",1,"S2C","02A","event packet",17000001,"Demo_NPC",None,None,None,None),
        )
        con.execute(
            "INSERT INTO capture_npc_entries VALUES(?,?,?,?,?,?,?,?)",
            (1,"Test_Zone",17000001,"Demo_NPC",0,1.0,2.0,3.0),
        )
        con.execute(
            "INSERT INTO capture_actions VALUES(?,?,?,?,?,?,?,?,?,?)",
            (1,"a1",17000001,"Demo_NPC","ABILITY",10,1,100,"Demo Action",0),
        )
        con.execute(
            "INSERT INTO capture_raw_packets VALUES(?,?,?,?,?,?)",
            (1,1,"now","S2C","02A","00"),
        )
        con.commit()
        con.close()

        graph.init_db(graph_db).close()
        connected=connect_capture_graph(capture_db,graph_db)
        assert connected["counts"]["packet_observations"]==1,connected

        trace=backtrace(capture_db,1,graph_db)
        assert any(check["kind"]=="ENTITY" for check in trace["checks"]),trace
        packets=[check for check in trace["checks"] if check["kind"]=="PACKET"]
        assert packets and packets[0]["canonical_packet_node"]=="packet:0x02a",trace

        script=root/"validator.py"
        script.write_text("raise SystemExit(0)\n",encoding="utf-8")
        suite=run_validation_suite(
            [ValidationSpec(
                validation_id="runtime:fixture",
                validation_type="RUNTIME_FIXTURE",
                subject_id="capture:1",
                script=str(script),
                dimension="runtime",
                required=True,
            )],
            run_id="run:runtime:p0",
            name="runtime p0 fixture",
            target_snapshot_id="runtime:test",
            graph_db=graph_db,
        )
        assert suite["validation_run"]["status"]=="VERIFIED",suite
        assert suite["dimensions"]["runtime"]["status"]=="VERIFIED",suite

        con=sqlite3.connect(graph_db)
        assert con.execute(
            "SELECT COUNT(*) FROM validation_results WHERE run_id='run:runtime:p0'"
        ).fetchone()[0]==1
        assert con.execute(
            "SELECT COUNT(*) FROM entity_relationships WHERE relationship='OBSERVES'"
        ).fetchone()[0]>=1
        con.close()

    print("runtime validation P0 self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
