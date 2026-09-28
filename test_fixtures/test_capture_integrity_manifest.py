#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import build_capture_index
from workbench.core.services import timeline_alignment


def _capture_owned_tables(con: sqlite3.Connection) -> set[str]:
    tables = {
        r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'capture_%'"
        ).fetchall()
    }
    owned = set()
    for table in tables:
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if "capture_id" in cols:
            owned.add(table)
    return owned


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = root / "capture.db"
        con = sqlite3.connect(db)
        build_capture_index.init_db(con)
        timeline_alignment.init_db(con)

        # Schema ownership audit: any future capture_id child table must be explicitly owned.
        actual = _capture_owned_tables(con)
        expected = set(build_capture_index.CAPTURE_CHILD_TABLES)
        missing = actual - expected
        assert not missing, f"capture child tables missing from cleanup ownership: {sorted(missing)}"

        cid = build_capture_index.create_manual_capture(con, "integrity-one", "Research", None)
        cid2 = build_capture_index.create_manual_capture(con, "integrity-two", "Research", None)

        # Content identity is path/name independent.
        data1 = b"same capture source bytes\n"
        r1 = build_capture_index.ingest_single_file(con, cid, "first-name.unknown", data1)
        r2 = build_capture_index.ingest_single_file(con, cid2, "renamed-source.unknown", data1)
        assert r1["sha256"] == r2["sha256"]
        m1 = con.execute(
            "SELECT source_manifest_sha256,source_file_count FROM captures WHERE capture_id=?", (cid,)
        ).fetchone()
        m2 = con.execute(
            "SELECT source_manifest_sha256,source_file_count FROM captures WHERE capture_id=?", (cid2,)
        ).fetchone()
        assert m1 == m2 and m1[1] == 1, (m1, m2)
        dupes = build_capture_index.find_capture_manifest_duplicates(con, cid)
        assert [d["capture_id"] for d in dupes] == [cid2], dupes

        # Adding the same second content under different names keeps aggregate manifests equal.
        data2 = b"second source file\n"
        build_capture_index.ingest_single_file(con, cid, "two.log", data2)
        assert not build_capture_index.find_capture_manifest_duplicates(con, cid)
        build_capture_index.ingest_single_file(con, cid2, "totally-different-name.txt", data2)
        dupes = build_capture_index.find_capture_manifest_duplicates(con, cid)
        assert [d["capture_id"] for d in dupes] == [cid2], dupes

        source_row = con.execute(
            """SELECT sha256,byte_size,parser_id,parser_version,source_kind
               FROM capture_source_files
               WHERE capture_id=? AND filename='first-name.unknown'""",
            (cid,),
        ).fetchone()
        assert source_row[0] == r1["sha256"], source_row
        assert source_row[1] == len(data1), source_row
        assert source_row[2] == "single:unrecognized", source_row
        assert source_row[3] == build_capture_index.CAPTURE_PARSER_VERSION, source_row
        assert source_row[4] == "single_file", source_row

        # Same filename with changed bytes updates the latest view but preserves both artifacts.
        changed = b"changed bytes under the same filename\n"
        build_capture_index.ingest_single_file(con, cid, "first-name.unknown", changed)
        latest = con.execute(
            "SELECT sha256 FROM capture_source_files WHERE capture_id=? AND filename=?",
            (cid, "first-name.unknown"),
        ).fetchone()[0]
        assert latest != r1["sha256"]
        artifact_rows = con.execute(
            """SELECT sha256 FROM capture_source_artifacts
               WHERE capture_id=? AND filename=? ORDER BY sha256""",
            (cid, "first-name.unknown"),
        ).fetchall()
        assert len(artifact_rows) == 2, artifact_rows
        assert {r[0] for r in artifact_rows} == {
            r1["sha256"], build_capture_index._content_fingerprint(changed)[0]
        }

        # Bundle manifest is independent of relative filenames.
        dir1 = root / "bundle1"
        dir2 = root / "bundle2"
        dir1.mkdir(); dir2.mkdir()
        (dir1 / "a.log").write_bytes(b"A")
        (dir1 / "b.log").write_bytes(b"B")
        (dir2 / "renamed-one.dat").write_bytes(b"B")
        (dir2 / "different-two.txt").write_bytes(b"A")
        src1 = build_capture_index.Source(dir1)
        src2 = build_capture_index.Source(dir2)
        try:
            assert build_capture_index.source_manifest(src1)["sha256"] == build_capture_index.source_manifest(src2)["sha256"]
        finally:
            src1.close(); src2.close()

        # Populate the newer optional evidence tables that previously escaped deletion.
        con.execute(
            """INSERT INTO capture_video_observations
               (capture_id,observation_id,observation_type)
               VALUES (?,?,?)""",
            (cid, "ocr-test", "PACKET"),
        )
        timeline_alignment.add_anchor(
            con, cid, video_ts=1.0, capture_ts=2.0,
            clock_kind=timeline_alignment.CLOCK_CAPTURE_RELATIVE,
            label="alignment test",
        )
        timeline_alignment.add_key_evidence(
            con, cid, evidence_type="KEY_EVENT", label="evidence test", video_ts=1.0
        )

        before = build_capture_index.capture_child_row_counts(con, cid)
        assert before["capture_video_observations"] == 1
        assert before["capture_alignment_anchors"] == 1
        assert before["capture_key_evidence"] == 1

        deleted = build_capture_index.delete_capture(con, cid)
        assert deleted["captures"] == 1
        assert con.execute("SELECT 1 FROM captures WHERE capture_id=?", (cid,)).fetchone() is None
        after = build_capture_index.capture_child_row_counts(con, cid)
        assert all(v == 0 for v in after.values()), after

        con.close()

        # GUI deletion also owns screenshot files under the per-capture evidence root.
        gui_text = (Path(__file__).resolve().parents[1] / "gui_server.py").read_text(encoding="utf-8")
        assert "shutil.rmtree(KEY_EVIDENCE_ROOT / str(int(capture_id)), ignore_errors=True)" in gui_text

    print("Capture integrity/content manifest regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
