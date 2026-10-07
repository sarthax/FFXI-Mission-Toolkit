#!/usr/bin/env python3
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.captures.correlation import graph_connect as capture_graph_connect
from workbench.core import graph as workbench_graph
from workbench.core.services import timeline_alignment as ta


def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        capture_db=root/"capture.db"
        con=sqlite3.connect(capture_db)
        build_capture_index.init_db(con)
        cid=build_capture_index.create_manual_capture(con,"key evidence test","instances",None,video_url="https://youtu.be/abcdefghijk",ocr_run_id="abcdefghijk")

        anchor=ta.add_anchor(
            con,cid,video_ts=100.0,capture_ts=40.0,
            clock_kind=ta.CLOCK_RAW_PACKET_RELATIVE,
            source_type="PACKET",label="packet landmark",
        )
        eid=ta.add_key_evidence(
            con,cid,
            evidence_type="SCREENSHOT",
            label="CS starts",
            anchor_id=anchor,
            source_ref="raw-packet:7",
            file_ref="mission_reports_v2/_key_evidence/1/keyev-test.png",
            mime_type="image/png",
            notes="Screenshot of the CS opening frame.",
            evidence_id="keyev-test",
        )
        assert eid=="keyev-test"
        rows=ta.list_key_evidence(con,cid)
        assert len(rows)==1,rows
        row=rows[0]
        assert row["video_ts"]==100.0 and row["capture_ts"]==40.0,row
        assert row["clock_kind"]==ta.CLOCK_RAW_PACKET_RELATIVE,row
        assert row["anchor_id"]==anchor,row

        ta.add_anchor(
            con,cid,video_ts=200.0,capture_ts=140.02,
            clock_kind=ta.CLOCK_RAW_PACKET_RELATIVE,
            source_type="PACKET",label="second packet landmark",
        )
        eid2=ta.add_key_evidence(
            con,cid,
            evidence_type="KEY_EVENT",
            label="Objective complete",
            video_ts=150.0,
            clock_kind=ta.CLOCK_RAW_PACKET_RELATIVE,
            evidence_id="keyev-event",
        )
        summary=ta.alignment_summary(con,cid)
        item=next(x for x in summary["key_evidence"] if x["evidence_id"]==eid2)
        assert item["capture_ts"] is None,item
        assert abs(item["capture_ts_aligned"]-90.01)<0.001,item

        graph_db=root/"graph.db"
        result=capture_graph_connect.connect(capture_db,graph_db,capture_id=cid)
        assert result["status"]=="OK",result
        assert result["counts"]["key_evidence"]==2,result

        graph=workbench_graph.init_db(graph_db)
        rel=graph.execute(
            """SELECT relationship,confidence,metadata_json,evidence_id
               FROM entity_relationships
               WHERE source_node=? AND target_node=?""",
            (f"capture:{cid}",f"key-evidence:{cid}:keyev-test"),
        ).fetchone()
        assert rel is not None
        assert rel[0]=="HAS_EVIDENCE" and rel[1]=="VERIFIED",rel
        meta=json.loads(rel[2])
        assert meta["evidence_type"]=="SCREENSHOT",meta
        evidence=graph.execute(
            "SELECT evidence_type,source,notes FROM evidence WHERE evidence_id=?",
            (rel[3],),
        ).fetchone()
        assert evidence[0]=="KEY_EVIDENCE",evidence
        graph.close()
        con.close()

        tpl=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"capture_alignment.html").read_text(encoding="utf-8")
        assert "Key evidence" in tpl
        assert 'enctype="multipart/form-data"' in tpl
        assert "view screenshot" in tpl

    print("Key evidence layer regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
