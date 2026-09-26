#!/usr/bin/env python3
"""Regression for portable xi-tinkerer client identity snapshot imports."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.client.identity_snapshot import (
    ClientIdentityManifest,
    ingest_dialog_export,
    parse_dialog_export,
    read_manifest,
    write_manifest,
)
from workbench.core.services.identity_resolver import resolve_identity


SAMPLE = """entries:
  10: 'The seal bears the crest of the Republic.'
  11: |-
    You hand over
    the supplies.
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        export = root / "dialog.yml"
        export.write_text(SAMPLE, encoding="utf-8")

        parsed = parse_dialog_export(export)
        assert parsed[10] == "The seal bears the crest of the Republic.", parsed
        assert parsed[11] == "You hand over the supplies.", parsed

        manifest_path = root / "manifest.json"
        manifest = ClientIdentityManifest(
            snapshot_id="client:test",
            build="30191204_1",
            source_path=str(root),
            files=({"zone_key": "NORTH_GUSTABERG_S", "path": str(export)},),
        )
        write_manifest(manifest_path, manifest)
        loaded = read_manifest(manifest_path)
        assert loaded.snapshot_id == "client:test", loaded
        assert loaded.build == "30191204_1", loaded
        assert len(loaded.files) == 1, loaded

        con = sqlite3.connect(root / "workbench.db")
        result = ingest_dialog_export(
            con,
            snapshot_id="client:test",
            zone_key="NORTH_GUSTABERG_S",
            export_path=export,
            build="30191204_1",
        )
        con.commit()
        assert result["entry_count"] == 2, result
        snap = con.execute(
            "SELECT snapshot_type,family,version,fingerprint FROM identity_snapshots WHERE snapshot_id=?",
            ("client:test",),
        ).fetchone()
        assert snap[0:3] == ("CLIENT", "RETAIL", "30191204_1"), snap
        assert len(snap[3]) == 64, snap

        same = resolve_identity(
            con,
            source_snapshot_id="client:test",
            target_snapshot_id="client:test",
            namespace="EVENT",
            source_numeric_id=10,
            zone_key="NORTH_GUSTABERG_S",
        )
        assert same.status == "EXACT", same
        assert same.target_numeric_id == "10", same
        con.close()

    print("client identity snapshot self-test: PASS")


if __name__ == "__main__":
    main()
