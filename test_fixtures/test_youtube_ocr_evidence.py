#!/usr/bin/env python3
"""Regression for timestamped/provenance-aware video OCR capture evidence."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.correlation import graph_connect as capture_graph_connect
import youtube_chat_ocr
from workbench.captures.ingestion import build_index as build_capture_index
from workbench.core import graph as workbench_graph


def _expect_system_exit(fn):
    try:
        fn()
    except SystemExit:
        return
    raise AssertionError("expected SystemExit")


def main():
    original_runs_root = youtube_chat_ocr.RUNS_ROOT
    original_timing = youtube_chat_ocr.OCR_TIMING_PATH
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            runs.mkdir()
            youtube_chat_ocr.RUNS_ROOT = runs
            youtube_chat_ocr.OCR_TIMING_PATH = runs / "_ocr_timing.json"

            run_id = "abcdefghijk"
            run = runs / run_id
            section = "packet_overlay"
            sdir = run / "sections" / section
            sdir.mkdir(parents=True)
            (run / "source_url.txt").write_text(
                "https://www.youtube.com/watch?v=abcdefghijk", encoding="utf-8"
            )
            (sdir / "meta.json").write_text(
                json.dumps({
                    "label": "Packet Overlay",
                    "crop": "10,20,300,120",
                    "fps": 2.0,
                    "capture_profile": youtube_chat_ocr.CAPTURE_PROFILE_PACKETLOGGER,
                }),
                encoding="utf-8",
            )

            assert youtube_chat_ocr.frame_index("f_000005.png") == 5
            assert youtube_chat_ocr.frame_video_timestamp("f_000005.png", 2.0) == 2.0

            provenance = youtube_chat_ocr.observation_provenance(
                run_id, section, "f_000005.png"
            )
            assert provenance["source_kind"] == "VIDEO_OCR", provenance
            assert provenance["video_timestamp_seconds"] == 2.0, provenance
            assert provenance["timestamp_resolution_seconds"] == 0.5, provenance
            assert provenance["timestamp_uncertainty_seconds"] == 0.25, provenance
            assert provenance["frame_index"] == 5, provenance
            assert provenance["crop"] == "10,20,300,120", provenance

            _expect_system_exit(lambda: youtube_chat_ocr.run_dir("../escape"))
            _expect_system_exit(lambda: youtube_chat_ocr.section_dir(run_id, "../escape"))
            _expect_system_exit(lambda: youtube_chat_ocr.section_dir(run_id, "bad/section"))

            matched = {
                "frame": "f_000005.png",
                "frame_index": 5,
                "video_timestamp_seconds": 2.0,
                "raw_text": "<< [0x036] GP_SERV_COMMAND_TALKNUM UniqueNo: 123",
                "display_text": "<< [0x036] GP_SERV_COMMAND_TALKNUM / UniqueNo: 123",
                "confidence": 93.0,
                "direction": "<<",
                "opcode": "0x036",
                "gp_command": "GP_SERV_COMMAND_TALKNUM",
                "packet_class": None,
                "fields": {"UniqueNo": "123"},
                "provenance": provenance,
            }
            (sdir / "ocr_matched.jsonl").write_text(
                json.dumps(matched) + "\n", encoding="utf-8"
            )

            observations = youtube_chat_ocr.capture_observations(run_id)
            assert len(observations) == 1, observations
            obs = observations[0]
            assert obs["observation_type"] == "PACKET", obs
            assert obs["opcode"] == "0x036", obs
            assert obs["video_timestamp_seconds"] == 2.0, obs

            capture_db = root / "capture.db"
            con = sqlite3.connect(capture_db)
            build_capture_index.init_db(con)
            capture_id = build_capture_index.create_manual_capture(
                con,
                "OCR evidence test",
                "instances",
                None,
                video_url=provenance["source_url"],
                ocr_run_id=run_id,
            )
            inserted = build_capture_index.replace_video_ocr_observations(
                con, capture_id, run_id, observations
            )
            assert inserted == 1
            row = con.execute(
                """SELECT video_ts,opcode,gp_command,ocr_confidence,provenance_json
                   FROM capture_video_observations WHERE capture_id=?""",
                (capture_id,),
            ).fetchone()
            assert row[:4] == (2.0, "0x036", "GP_SERV_COMMAND_TALKNUM", 93.0), row
            assert json.loads(row[4])["source_kind"] == "VIDEO_OCR"
            assert con.execute(
                "SELECT COUNT(*) FROM capture_raw_packets WHERE capture_id=?", (capture_id,)
            ).fetchone()[0] == 0
            con.close()

            graph_db = root / "graph.db"
            result = capture_graph_connect.connect(
                capture_db, graph_db, capture_id=capture_id
            )
            assert result["status"] == "OK", result
            assert result["counts"]["video_ocr_observations"] == 1, result
            assert result["counts"]["packet_observations"] == 1, result

            graph = workbench_graph.init_db(graph_db)
            rel = graph.execute(
                """SELECT relationship,confidence,metadata_json,evidence_id
                   FROM entity_relationships
                   WHERE source_node=? AND target_node='packet:0x036'""",
                (f"capture:{capture_id}",),
            ).fetchone()
            assert rel is not None, list(graph.execute("SELECT * FROM entity_relationships"))
            assert rel[0] == "OBSERVES" and rel[1] == "INFERRED", rel
            metadata = json.loads(rel[2])
            assert metadata["source_kind"] == "VIDEO_OCR", metadata
            assert metadata["video_timestamp_seconds"] == 2.0, metadata
            evidence = graph.execute(
                "SELECT evidence_type,source,notes FROM evidence WHERE evidence_id=?",
                (rel[3],),
            ).fetchone()
            assert evidence[0] == "VIDEO_OCR", evidence
            assert "no packet bytes" in evidence[2].lower(), evidence
            graph.close()

            template = (
                Path(__file__).resolve().parents[1]
                / "gui" / "templates" / "ocr_run.html"
            ).read_text(encoding="utf-8")
            assert "video_timestamp_seconds" in template
            assert "VIDEO_OCR" in template

    finally:
        youtube_chat_ocr.RUNS_ROOT = original_runs_root
        youtube_chat_ocr.OCR_TIMING_PATH = original_timing

    print("YouTube OCR evidence regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
