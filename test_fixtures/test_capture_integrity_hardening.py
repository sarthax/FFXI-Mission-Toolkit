#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.core.services import capture_integrity, timeline_alignment


def count(con, table, capture_id):
    return con.execute(f'SELECT COUNT(*) FROM "{table}" WHERE capture_id=?', (capture_id,)).fetchone()[0]


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = root / "capture.db"
        con = sqlite3.connect(db)
        build_capture_index.init_db(con)
        timeline_alignment.init_db(con)

        cid = build_capture_index.create_manual_capture(con, "integrity test", "instances", None)
        payload = b"Defeated Integrity_Mob: 100~120 HP\n"
        result = build_capture_index.ingest_single_file(con, cid, "Integrity Zone.log", payload)
        assert result["format"] == "hptrack", result

        manifest = con.execute(
            """SELECT sha256,byte_size,format_detected,parser_name,parser_version,
                      row_count,ingest_status,error
               FROM capture_source_manifest WHERE capture_id=? AND filename=?""",
            (cid, "Integrity Zone.log"),
        ).fetchone()
        assert manifest is not None
        assert manifest[0] == hashlib.sha256(payload).hexdigest(), manifest
        assert manifest[1] == len(payload), manifest
        assert manifest[2] == "hptrack" and manifest[3] == "hptrack", manifest
        assert manifest[4] == capture_integrity.PARSER_VERSION, manifest
        assert manifest[6] == "RECOGNIZED" and manifest[7] is None, manifest

        lineage = con.execute(
            """SELECT target_table,locator_basis,parser_version
               FROM capture_ingest_lineage WHERE capture_id=? AND filename=?""",
            (cid, "Integrity Zone.log"),
        ).fetchall()
        assert ("capture_hp_events", "line", capture_integrity.PARSER_VERSION) in lineage, lineage

        # Bundle/folder ingestion must also content-address files even when caller doesn't request file_results.
        cid_bundle = build_capture_index.create_manual_capture(con, "bundle integrity", "instances", None)
        bundle = root / "bundle"
        (bundle / "HPTrack").mkdir(parents=True)
        bundle_payload = b"Defeated Bundle_Mob: 200~240 HP\n"
        (bundle / "HPTrack" / "Bundle Zone.log").write_bytes(bundle_payload)
        src = build_capture_index.Source(bundle)
        try:
            counts = build_capture_index.ingest_from_source(con, cid_bundle, src)
        finally:
            src.close()
        assert counts["hp"] >= 1, counts
        bundle_manifest = con.execute(
            """SELECT sha256,format_detected,ingest_status
               FROM capture_source_manifest
               WHERE capture_id=? AND filename='HPTrack/Bundle Zone.log'""",
            (cid_bundle,),
        ).fetchone()
        assert bundle_manifest == (
            hashlib.sha256(bundle_payload).hexdigest(), "hptrack", "RECOGNIZED"
        ), bundle_manifest

        # Newer evidence tables plus a future table omitted from the explicit registry.
        con.execute(
            """INSERT INTO capture_video_observations
               (capture_id,observation_id,observation_type,opcode,provenance_json)
               VALUES (?,?,?,?,?)""",
            (cid, "obs-1", "PACKET", "0x036", "{}"),
        )
        timeline_alignment.add_anchor(
            con, cid, video_ts=10.0, capture_ts=5.0,
            clock_kind=timeline_alignment.CLOCK_RAW_PACKET_RELATIVE,
            source_type="PACKET", label="anchor one",
        )
        timeline_alignment.add_anchor(
            con, cid, video_ts=20.0, capture_ts=15.0,
            clock_kind=timeline_alignment.CLOCK_RAW_PACKET_RELATIVE,
            source_type="PACKET", label="anchor two",
        )
        timeline_alignment.add_key_evidence(
            con, cid, evidence_type="KEY_EVENT", label="objective complete",
            video_ts=20.0, clock_kind=timeline_alignment.CLOCK_RAW_PACKET_RELATIVE,
        )
        con.execute("CREATE TABLE capture_future_rows(capture_id INTEGER,value TEXT)")
        con.execute("INSERT INTO capture_future_rows VALUES (?,?)", (cid, "future child"))
        con.commit()

        health = capture_integrity.capture_health(con, cid)
        assert health["status"] == "OK", health
        assert health["dimensions"]["source_integrity"]["status"] == "COMPLETE", health
        assert health["dimensions"]["parser_coverage"]["status"] == "COMPLETE", health
        assert health["dimensions"]["lineage"]["status"] == "COMPLETE", health
        assert health["dimensions"]["timeline_alignment"]["status"] == "COMPLETE", health

        # Same bytes in another capture should be reported as a duplicate source, not silently conflated.
        cid2 = build_capture_index.create_manual_capture(con, "duplicate test", "instances", None)
        build_capture_index.ingest_single_file(con, cid2, "Renamed Integrity.log", payload)
        health2 = capture_integrity.capture_health(con, cid2)
        assert health2["dimensions"]["duplicate_source"]["status"] == "ISSUES", health2
        assert health2["dimensions"]["duplicate_source"]["duplicate_hashes"], health2

        schema_tables = capture_integrity.schema_capture_tables(con)
        assert "capture_video_observations" in schema_tables
        assert "capture_alignment_anchors" in schema_tables
        assert "capture_key_evidence" in schema_tables
        assert "capture_future_rows" in schema_tables

        deleted = build_capture_index.delete_capture(con, cid)
        assert deleted["captures"] == 1, deleted
        for table in (
            "capture_source_manifest", "capture_ingest_lineage",
            "capture_video_observations", "capture_alignment_anchors",
            "capture_key_evidence", "capture_future_rows",
        ):
            assert count(con, table, cid) == 0, (table, deleted)
        assert con.execute("SELECT 1 FROM captures WHERE capture_id=?", (cid,)).fetchone() is None

        template = (
            Path(__file__).resolve().parents[1] / "gui" / "templates" / "capture_detail.html"
        ).read_text(encoding="utf-8")
        assert "Capture integrity" in template
        assert "source manifest / parser provenance" in template

        con.close()

    print("Capture integrity hardening regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
