#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.captures.correlation.graph_connect import connect as connect_capture_graph
from workbench.core import graph
from workbench.core.services import packet_correlation as pc
from workbench.core.services import timeline_alignment as ta


def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        db=root/"capture.db"
        graph_db=root/"workbench.db"
        con=sqlite3.connect(db)
        build_capture_index.init_db(con)
        cid=build_capture_index.create_manual_capture(
            con,"correlation fixture","Research",None,
            video_url="https://youtu.be/abcdefghijk",ocr_run_id="abcdefghijk",
        )

        # Clean one-to-one raw/EventView pairs at t=0 and t=5.
        raw_rows=[
            (cid,0,"2026-09-28 10:00:00","incoming","0x034","0102"),
            (cid,1,"2026-09-28 10:00:05","incoming","0x034","0304"),
            # Deliberate duplicate same-second source candidates -> ambiguity.
            (cid,2,"2026-09-28 10:00:10","incoming","0x034","0506"),
            (cid,3,"2026-09-28 10:00:10","incoming","0x034","0708"),
        ]
        con.executemany(
            "INSERT INTO capture_raw_packets(capture_id,seq,ts,direction,opcode,raw_hex) VALUES(?,?,?,?,?,?)",
            raw_rows,
        )
        ev_rows=[
            (cid,"Test Zone",0,"2026-09-28 10:00:00","<<","0x034","CEventPacket",
             "GP_SERV_COMMAND_EVENT",17000001,42,55,json.dumps({"UniqueNo":"17000001","MessageNumber":"55"})),
            (cid,"Test Zone",1,"2026-09-28 10:00:05","<<","0x034","CEventPacket",
             "GP_SERV_COMMAND_EVENT",17000002,43,66,json.dumps({"UniqueNo":"17000002","MessageNumber":"66"})),
            (cid,"Test Zone",2,"2026-09-28 10:00:10","<<","0x034","CEventPacket",
             "GP_SERV_COMMAND_EVENT",17000003,44,77,json.dumps({"UniqueNo":"17000003","MessageNumber":"77"})),
        ]
        con.executemany(
            """INSERT INTO capture_eventview
               (capture_id,zone_db,seq,ts,direction,opcode,packet_class,gp_command,
                entity_id,mes_num,message_number,fields_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            ev_rows,
        )

        # IDView has no timestamp; only shared decoded entity/message fields may correlate it.
        con.execute(
            """INSERT INTO capture_events
               (capture_id,zone_db,seq,direction,opcode,opcode_name,entity_id,entity_name,
                event_hex,option,message_id,params_raw)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid,"Test Zone",0,"Incoming","0x034","CS Event",17000001,"NPC A",
             "0x0100",0,55,"{}"),
        )

        # Video packet at video t=20; explicit anchors map it to capture-relative t=0 in both
        # independent logger clocks.
        con.execute(
            """INSERT INTO capture_video_observations
               (capture_id,observation_id,ocr_run_id,section,frame,video_ts,source_url,
                observation_type,direction,opcode,gp_command,packet_class,fields_json,
                raw_text,corrected_text,ocr_confidence,provenance_json)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid,"v0","abcdefghijk","packet","f0.png",20.0,"https://youtu.be/abcdefghijk",
             "PACKET","<<","0x034","GP_SERV_COMMAND_EVENT","CEventPacket",
             json.dumps({"MessageNumber":"55"}),"x",None,95.0,"{}"),
        )
        con.commit()

        ta.add_anchor(
            con,cid,video_ts=20.0,capture_ts=0.0,
            clock_kind=ta.CLOCK_RAW_PACKET_RELATIVE,source_type="PACKET",
        )
        ta.add_anchor(
            con,cid,video_ts=20.0,capture_ts=0.0,
            clock_kind=ta.CLOCK_EVENTVIEW_RELATIVE,source_type="PACKET",
        )

        summary=pc.correlate_capture(con,cid)
        assert summary["source_counts"]=={
            pc.RAW:4,pc.EVENTVIEW:3,pc.IDVIEW:1,pc.VIDEO:1
        },summary
        assert summary["matched"]==5,summary
        assert summary["ambiguous"]==2,summary

        rows=pc.list_correlations(con,cid)
        raw0=[r for r in rows if r["source_kind"]==pc.RAW and r["source_ref"]=="raw-packet:0"
              and r["target_kind"]==pc.EVENTVIEW]
        assert len(raw0)==1 and raw0[0]["status"]==pc.STATUS_MATCHED,raw0
        assert raw0[0]["time_delta_seconds"]==0.0,raw0

        ambiguous=[r for r in rows if r["status"]==pc.STATUS_AMBIGUOUS]
        assert len(ambiguous)==2,ambiguous
        assert {r["source_ref"] for r in ambiguous}=={"raw-packet:2","raw-packet:3"},ambiguous
        assert {r["target_ref"] for r in ambiguous}=={"eventview:Test Zone:2"},ambiguous

        idmatch=[r for r in rows if r["source_kind"]==pc.IDVIEW]
        assert len(idmatch)==1 and idmatch[0]["status"]==pc.STATUS_MATCHED,idmatch
        assert idmatch[0]["target_ref"]=="eventview:Test Zone:0",idmatch
        assert set(idmatch[0]["details"]["shared_fields"])=={"entity_id","message_id"},idmatch

        video=[r for r in rows if r["source_kind"]==pc.VIDEO]
        assert len(video)==2,video
        assert {r["target_kind"] for r in video}=={pc.RAW,pc.EVENTVIEW},video
        assert all(r["status"]==pc.STATUS_MATCHED for r in video),video
        assert all(abs(r["time_delta_seconds"])<1e-9 for r in video),video

        # Related Evidence consumes only non-temporal, unique MATCHED correlations.
        id_explicit=pc.list_non_temporal_matches(con,cid,pc.IDVIEW,"idview:Test Zone:0")
        assert len(id_explicit)==1,id_explicit
        assert id_explicit[0]["peer_kind"]==pc.EVENTVIEW,id_explicit
        assert id_explicit[0]["peer_ref"]=="eventview:Test Zone:0",id_explicit
        assert id_explicit[0]["basis"]=="opcode+direction+shared_decoded_fields",id_explicit
        assert pc.list_non_temporal_matches(con,cid,pc.RAW,"raw-packet:0")==[],rows
        assert pc.list_non_temporal_matches(con,cid,pc.VIDEO,"video-ocr:v0")==[],video

        # Rebuild is deterministic and clears obsolete correlations.
        con.execute("DELETE FROM capture_raw_packets WHERE capture_id=? AND seq=3",(cid,))
        con.commit()
        summary2=pc.correlate_capture(con,cid)
        assert summary2["ambiguous"]==0,summary2
        rows2=pc.list_correlations(con,cid)
        assert not any(r["source_ref"]=="raw-packet:3" for r in rows2),rows2

        # Runtime graph generation refreshes correlation state automatically.
        graph.init_db(graph_db).close()
        connected=connect_capture_graph(db,graph_db,capture_id=cid)
        assert connected["counts"]["packet_correlations"]==summary2["matched"],connected
        assert connected["counts"]["packet_correlations_ambiguous"]==0,connected

        con.close()

        tpl=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"capture_alignment.html").read_text(encoding="utf-8")
        assert "Cross-source packet correlation" in tpl
        assert "Rebuild packet correlations" in tpl
        assert "AMBIGUOUS" in tpl

    print("Cross-source packet correlation regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
