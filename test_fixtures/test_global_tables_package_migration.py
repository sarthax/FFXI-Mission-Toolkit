#!/usr/bin/env python3
"""Focused migration regression for global client DAT table ingestion."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from workbench.client.dat import global_tables as canonical
    from workbench.client.dat import extractor_bin
    from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT as RUNTIME_ROOT

    assert not (REPO_ROOT / "ingest_global_tables.py").exists()
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.MASS_EXTRACTOR_DIR == RUNTIME_ROOT / "MassExtractor_output"
    assert canonical.DAT_EXTRACTOR_EXE == extractor_bin.EXE
    assert canonical.normalize_name("Kindred's Crest") == "kindredscrest"

    con = sqlite3.connect(":memory:")
    canonical.init_db(con)
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "assault_missions" in tables
    assert "key_items" in tables

    con.execute("CREATE TABLE keyitems_ours (id INTEGER, const_name TEXT, norm_name TEXT)")
    con.executemany(
        "INSERT INTO keyitems_ours VALUES (?, ?, ?)",
        [
            (10, "ZERUHN_REPORT", "zeruhnreport"),
            (20, "KINDRED_CREST", "kindredcrest"),
            (30, "SOMETHING_ELSE", "somethingelse"),
        ],
    )
    assert canonical.resolve_keyitem_readiness(con, 10, "Zeruhn report")["status"] == "clean"
    assert canonical.resolve_keyitem_readiness(con, 99, "Kindred crest")["status"] == "drifted"
    assert canonical.resolve_keyitem_readiness(con, 30, "Unknown item")["status"] == "wrong_name"
    assert canonical.resolve_keyitem_readiness(con, 77, "Missing item")["status"] == "missing"
    con.close()

    code = r'''
from pathlib import Path
from workbench.client.dat import global_tables as g, extractor_bin as e
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT
assert g.DB_PATH == DATABASE_PATH
assert g.MASS_EXTRACTOR_DIR == REPO_ROOT / "MassExtractor_output"
assert g.DAT_EXTRACTOR_EXE == e.EXE
assert "src" in Path(g.__file__).resolve().parts
assert g.normalize_name("Kindred's Crest") == "kindredscrest"
'''
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("global DAT tables package migration: OK")


if __name__ == "__main__":
    main()
