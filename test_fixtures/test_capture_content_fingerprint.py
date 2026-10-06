#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import build_capture_index
from workbench.core.services import capture_integrity


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = root / "capture.db"
        con = sqlite3.connect(db)
        build_capture_index.init_db(con)
        capture_integrity.init_db(con)

        a = build_capture_index.create_manual_capture(con, "fingerprint-a", "instances", None)
        b = build_capture_index.create_manual_capture(con, "fingerprint-b", "instances", None)

        first = b"Defeated Same_Mob: 100~120 HP\n"
        second = b"another unknown source payload\n"

        # Same evidence under different filenames must produce the same whole-capture identity.
        build_capture_index.ingest_single_file(con, a, "A Zone.log", first)
        build_capture_index.ingest_single_file(con, b, "Renamed Zone.log", first)
        ia = capture_integrity.content_identity(con, a)
        ib = capture_integrity.content_identity(con, b)
        assert ia["sha256"] == ib["sha256"], (ia, ib)
        assert ia["file_count"] == ib["file_count"] == 1
        assert [r["capture_id"] for r in capture_integrity.find_exact_capture_duplicates(con, a)] == [b]

        # A second equal source under unrelated names retains path independence and multiplicity.
        build_capture_index.ingest_single_file(con, a, "extra.bin", second)
        build_capture_index.ingest_single_file(con, b, "different-name.dat", second)
        ia2 = capture_integrity.content_identity(con, a)
        ib2 = capture_integrity.content_identity(con, b)
        assert ia2["sha256"] == ib2["sha256"], (ia2, ib2)
        assert ia2["file_count"] == 2
        assert [r["capture_id"] for r in capture_integrity.find_exact_capture_duplicates(con, a)] == [b]

        # Changed bytes under one existing filename change current identity but preserve both
        # content versions in append-safe source history.
        changed = b"Defeated Same_Mob: 130~150 HP\n"
        old_hash = capture_integrity.sha256_bytes(first)
        new_hash = capture_integrity.sha256_bytes(changed)
        build_capture_index.ingest_single_file(con, a, "A Zone.log", changed)

        latest = con.execute(
            """SELECT sha256 FROM capture_source_manifest
               WHERE capture_id=? AND filename='A Zone.log'""",
            (a,),
        ).fetchone()[0]
        assert latest == new_hash

        versions = con.execute(
            """SELECT sha256 FROM capture_source_artifacts
               WHERE capture_id=? AND filename='A Zone.log'""",
            (a,),
        ).fetchall()
        assert {r[0] for r in versions} == {old_hash, new_hash}, versions

        ia3 = capture_integrity.content_identity(con, a)
        assert ia3["sha256"] != ib2["sha256"], (ia3, ib2)
        assert capture_integrity.find_exact_capture_duplicates(con, a) == []

        # Once B receives the equivalent changed source under its own filename, exact identity
        # converges again despite the path/name difference.
        build_capture_index.ingest_single_file(con, b, "Renamed Zone.log", changed)
        ib3 = capture_integrity.content_identity(con, b)
        assert ia3["sha256"] == ib3["sha256"], (ia3, ib3)
        assert [r["capture_id"] for r in capture_integrity.find_exact_capture_duplicates(con, a)] == [b]

        health = capture_integrity.capture_health(con, a)
        identity_dim = health["dimensions"]["capture_identity"]
        assert identity_dim["status"] == "ISSUES", identity_dim
        assert identity_dim["exact_duplicates"][0]["capture_id"] == b, identity_dim
        assert health["source_artifact_count"] >= 3, health

        # Auxiliary metadata must not perturb gameplay/source-set identity.
        before = capture_integrity.content_identity(con, a)["sha256"]
        capture_integrity.record_source_file(
            con, a, "manifest.txt", b"Version='different packaging metadata'",
            format_detected="manifest", parser_name="manifest", row_count=0,
        )
        after = capture_integrity.content_identity(con, a)["sha256"]
        assert before == after

        # New tables are capture-owned and dynamic deletion removes them without special-case SQL.
        schema_tables = set(capture_integrity.schema_capture_tables(con))
        assert "capture_source_artifacts" in schema_tables
        assert "capture_content_manifest" in schema_tables
        deleted = build_capture_index.delete_capture(con, a)
        assert deleted["captures"] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM capture_source_artifacts WHERE capture_id=?", (a,)
        ).fetchone()[0] == 0
        assert con.execute(
            "SELECT COUNT(*) FROM capture_content_manifest WHERE capture_id=?", (a,)
        ).fetchone()[0] == 0

        repo_root = Path(__file__).resolve().parents[1]
        gui = (repo_root / "gui" / "templates" / "capture_detail.html").read_text(encoding="utf-8")
        assert "Capture content fingerprint" in gui
        assert "source history" in gui

        server = (repo_root / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
        assert 'parser_name="archive_open"' in server
        con.close()

    print("Capture content fingerprint regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
