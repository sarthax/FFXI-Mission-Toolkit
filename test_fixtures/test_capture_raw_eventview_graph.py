#!/usr/bin/env python3
"""Regression for row-level raw PacketLogger + EventView runtime graph linkage."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import feature_trace
from workbench.runtime import connect as workbench_connect
from workbench.captures.correlation.graph_connect import connect
from workbench.core import graph
from workbench.core.services import capture_integrity


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        srcdb=root/"capture.db"
        graphdb=root/"workbench.db"

        src=sqlite3.connect(srcdb)
        src.executescript("""
            CREATE TABLE capture_raw_packets(
                capture_id INTEGER, seq INTEGER, ts TEXT, direction TEXT, opcode TEXT, raw_hex TEXT,
                PRIMARY KEY(capture_id,seq)
            );
            CREATE TABLE capture_eventview(
                capture_id INTEGER, zone_db TEXT, seq INTEGER, ts TEXT, direction TEXT,
                opcode TEXT, packet_class TEXT, gp_command TEXT,
                entity_id INTEGER, mes_num INTEGER, message_number INTEGER, fields_json TEXT,
                PRIMARY KEY(capture_id,zone_db,seq)
            );
        """)
        capture_integrity.init_db(src)

        # Same opcode twice: these must remain two independent raw observations.
        src.execute(
            "INSERT INTO capture_raw_packets VALUES(?,?,?,?,?,?)",
            (8,0,"2026-09-28 10:00:00","incoming","0x034","01020304"),
        )
        src.execute(
            "INSERT INTO capture_raw_packets VALUES(?,?,?,?,?,?)",
            (8,1,"2026-09-28 10:00:01","incoming","0x034","AABBCCDD"),
        )
        # EventView decode of the same canonical packet opcode, deliberately separate evidence.
        src.execute(
            "INSERT INTO capture_eventview VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                8,"Test Zone",0,"2026-09-28 10:00:02","incoming","0x034",
                "CEventPacket","GP_SERV_COMMAND_EVENT",17000001,42,99,
                json.dumps({"UniqueNo":"17000001","MesNum":"42","MessageNumber":"99"}),
            ),
        )
        capture_integrity.record_row_locator(
            src,8,"PacketLogger/incoming/0x034.log","capture_raw_packets",
            json.dumps({"seq":0},sort_keys=True),"block",
            source_sha256="1"*64,start_line=1,end_line=3,start_offset=0,end_offset=64,
            details={"opcode":"0x034","direction":"incoming"},
        )
        capture_integrity.record_row_locator(
            src,8,"PacketLogger/incoming/0x034.log","capture_raw_packets",
            json.dumps({"seq":1},sort_keys=True),"block",
            source_sha256="1"*64,start_line=4,end_line=6,start_offset=64,end_offset=128,
            details={"opcode":"0x034","direction":"incoming"},
        )
        capture_integrity.record_row_locator(
            src,8,"EventView/Tester/Test Zone.log","capture_eventview",
            json.dumps({"zone_db":"Test Zone","seq":0},sort_keys=True),"block",
            source_sha256="2"*64,start_line=1,end_line=8,start_offset=0,end_offset=160,
            details={"opcode":"0x034","packet_class":"CEventPacket","gp_command":"GP_SERV_COMMAND_EVENT"},
        )
        src.commit()
        src.close()

        graph.init_db(graphdb).close()
        result=connect(srcdb,graphdb)
        assert result["status"]=="OK",result
        assert result["counts"]["raw_packet_observations"]==2,result
        assert result["counts"]["eventview_observations"]==1,result
        assert result["counts"]["packet_observations"]==3,result

        con=sqlite3.connect(graphdb)
        raw=con.execute(
            """SELECT relationship_id,target_node,evidence_id,metadata_json
               FROM entity_relationships
               WHERE source_node='capture:8' AND relationship='OBSERVES_PACKET'
               ORDER BY relationship_id"""
        ).fetchall()
        assert len(raw)==2,raw
        assert [r[0] for r in raw]==[
            "raw-packet-observation:8:0","raw-packet-observation:8:1"
        ],raw
        assert all(r[1]=="packet:0x034" for r in raw),raw
        raw_meta=[json.loads(r[3]) for r in raw]
        assert [m["capture_row_key"] for m in raw_meta]==[{"seq":0},{"seq":1}],raw_meta
        assert [m["byte_length"] for m in raw_meta]==[4,4],raw_meta
        assert all(m["source_kind"]=="RAW_PACKET" for m in raw_meta),raw_meta

        ev=con.execute(
            """SELECT target_node,evidence_id,metadata_json
               FROM entity_relationships
               WHERE relationship_id='eventview-packet-observation:8:Test Zone:0'"""
        ).fetchone()
        assert ev is not None,ev
        assert ev[0]=="packet:0x034",ev
        ev_meta=json.loads(ev[2])
        assert ev_meta["source_kind"]=="EVENTVIEW_DECODE",ev_meta
        assert ev_meta["capture_table"]=="capture_eventview",ev_meta
        assert ev_meta["capture_row_key"]=={"zone_db":"Test Zone","seq":0},ev_meta
        assert ev_meta["gp_command"]=="GP_SERV_COMMAND_EVENT",ev_meta
        assert ev_meta["fields"]["MessageNumber"]=="99",ev_meta

        evidence=con.execute(
            """SELECT evidence_id,evidence_type,source,location
               FROM evidence
               WHERE evidence_id LIKE 'evidence:raw-packet:8:%'
                  OR evidence_id='evidence:eventview-packet:8:Test Zone:0'
               ORDER BY evidence_id"""
        ).fetchall()
        assert len(evidence)==3,evidence
        assert {r[1] for r in evidence}=={"PACKET_CAPTURE","CAPTURE_DECODE"},evidence
        assert {r[2] for r in evidence}=={"capture_raw_packets","capture_eventview"},evidence

        # Feature Trace must expose all three independent runtime observations and resolve each
        # back to its exact capture source locator.
        cap=sqlite3.connect(srcdb)
        page=feature_trace.runtime_observation_page(
            con,"packet:0x034",1,"both",cap,"0x034","8",0,100
        )
        assert page["total"]==3,page
        kinds=[]
        filenames=[]
        for obs in page["observations"]:
            kinds.append((obs.get("metadata") or {}).get("source_kind"))
            prov=obs.get("capture_provenance") or []
            assert len(prov)==1,obs
            filenames.append(prov[0]["filename"])
        assert kinds.count("RAW_PACKET")==2,kinds
        assert kinds.count("EVENTVIEW_DECODE")==1,kinds
        assert filenames.count("PacketLogger/incoming/0x034.log")==2,filenames
        assert filenames.count("EventView/Tester/Test Zone.log")==1,filenames

        cap.close()
        con.close()

        # General connector and capture-specific connector must be idempotent with one another.
        workbench_connect.connect(srcdb,graphdb)
        connect(srcdb,graphdb)
        con=sqlite3.connect(graphdb)
        exact_count=con.execute(
            """SELECT COUNT(*) FROM entity_relationships
               WHERE source_node='capture:8'
                 AND relationship IN ('OBSERVES_PACKET','OBSERVES_EVENTVIEW_PACKET')"""
        ).fetchone()[0]
        assert exact_count==3,exact_count

        # Reconciliation removes stale bridge-owned rows after the normalized capture shrinks.
        src=sqlite3.connect(srcdb)
        src.execute("DELETE FROM capture_raw_packets WHERE capture_id=8 AND seq=1")
        src.execute("DELETE FROM capture_eventview WHERE capture_id=8")
        src.commit()
        src.close()
        result2=connect(srcdb,graphdb,capture_id=8)
        assert result2["counts"]["raw_packet_observations"]==1,result2
        assert result2["counts"]["eventview_observations"]==0,result2
        stale=con.execute(
            """SELECT relationship_id FROM entity_relationships
               WHERE relationship_id IN (
                 'raw-packet-observation:8:1',
                 'eventview-packet-observation:8:Test Zone:0'
               )"""
        ).fetchall()
        assert stale==[],stale
        remaining=con.execute(
            """SELECT relationship_id FROM entity_relationships
               WHERE relationship_id='raw-packet-observation:8:0'"""
        ).fetchone()
        assert remaining is not None
        con.close()

    print("raw packet + EventView runtime graph regression: PASS")


if __name__=="__main__":
    main()
