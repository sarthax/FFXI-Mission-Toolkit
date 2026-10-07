#!/usr/bin/env python3
from __future__ import annotations
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.core.services import timeline_alignment as ta


def main():
    with TemporaryDirectory() as tmp:
        db=Path(tmp)/"capture.db"
        con=sqlite3.connect(db)
        build_capture_index.init_db(con)
        cid=build_capture_index.create_manual_capture(con,"align test","instances",None,video_url="https://youtu.be/abcdefghijk",ocr_run_id="abcdefghijk")

        con.execute("""INSERT INTO capture_video_observations
            (capture_id,observation_id,ocr_run_id,section,frame,video_ts,source_url,observation_type,direction,opcode,gp_command,packet_class,fields_json,raw_text,corrected_text,ocr_confidence,provenance_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid,"v1","abcdefghijk","packet","f_000021.png",10.0,"https://youtu.be/abcdefghijk","PACKET","<<","0x036","GP_SERV_COMMAND_TALKNUM",None,None,"x",None,95.0,"{}"))
        con.execute("""INSERT INTO capture_raw_packets(capture_id,seq,ts,direction,opcode,raw_hex)
                       VALUES (?,?,?,?,?,?)""",(cid,1,"2026-09-28 01:00:05","incoming","0x036","00"))
        con.execute("""INSERT INTO capture_raw_packets(capture_id,seq,ts,direction,opcode,raw_hex)
                       VALUES (?,?,?,?,?,?)""",(cid,2,"2026-09-28 01:00:25","incoming","0x034","00"))
        con.commit()

        landmarks=ta.shared_packet_landmarks(con,cid)
        assert len(landmarks)==1 and landmarks[0]["opcode"]=="0x036",landmarks
        assert landmarks[0]["unique_pair"] is True,landmarks

        aid1=ta.add_anchor(con,cid,video_ts=10.0,capture_ts=0.0,clock_kind=ta.CLOCK_RAW_PACKET_RELATIVE,source_type="PACKET")
        model=ta.fit_alignment(con,cid,ta.CLOCK_RAW_PACKET_RELATIVE)
        assert model.anchor_count==1 and model.intercept==-10.0 and model.slope==1.0,model
        assert model.video_to_capture(20.0)==10.0
        assert model.capture_to_video(10.0)==20.0

        aid2=ta.add_anchor(con,cid,video_ts=30.0,capture_ts=20.002,clock_kind=ta.CLOCK_RAW_PACKET_RELATIVE,source_type="PACKET")
        model=ta.fit_alignment(con,cid,ta.CLOCK_RAW_PACKET_RELATIVE)
        assert model.anchor_count==2
        assert abs(model.slope-1.0001)<1e-9,model
        assert abs(model.drift_ppm-100.0)<0.01,model
        assert model.rms_error_seconds<1e-8,model

        ta.add_anchor(con,cid,video_ts=5.0,capture_ts=999.0,clock_kind=ta.CLOCK_EVENTVIEW_RELATIVE)
        model2=ta.fit_alignment(con,cid,ta.CLOCK_EVENTVIEW_RELATIVE)
        assert model2.anchor_count==1
        assert ta.fit_alignment(con,cid,ta.CLOCK_RAW_PACKET_RELATIVE).anchor_count==2

        summary=ta.alignment_summary(con,cid)
        assert len(summary["anchors"])==3
        assert set(summary["models"])=={ta.CLOCK_RAW_PACKET_RELATIVE,ta.CLOCK_EVENTVIEW_RELATIVE}

        assert ta.delete_anchor(con,cid,aid1)
        assert ta.delete_anchor(con,cid,aid2)
        con.close()

        tpl=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"capture_alignment.html").read_text(encoding="utf-8")
        assert "Shared packet landmarks" in tpl
        assert "use as anchor" in tpl

    print("Capture/video timeline alignment regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
