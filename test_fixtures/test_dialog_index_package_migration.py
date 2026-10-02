#!/usr/bin/env python3
"""Focused regression for the packaged dialog index builder."""
from __future__ import annotations

import importlib.util
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from workbench.client.dat import extractor_bin
    from workbench.devtools.reference.dialog import build_index as canonical
    from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT

    assert canonical.TOOLS_ROOT == REPO_ROOT
    assert canonical.DB_PATH == DATABASE_PATH
    assert canonical.DAT_EXTRACTOR_EXE == extractor_bin.EXE
    assert "src" in Path(canonical.__file__).resolve().parts

    assert canonical.dat_id_for_zone(0) == 6420
    assert canonical.dat_id_for_zone(77) == 6497
    assert canonical.dat_id_for_zone(255) == 6675
    assert canonical.dat_id_for_zone(256) == 85590
    assert canonical.dat_id_for_zone(511) == 85845
    try:
        canonical.dat_id_for_zone(512)
    except ValueError:
        pass
    else:
        raise AssertionError("out-of-range zone IDs must fail closed")

    assert canonical.normalize("Hello <item>!") == "hello"
    assert canonical.normalize("Hello ≺Numeric Parameter 0≻!") == "hello"

    con = sqlite3.connect(":memory:")
    canonical.init_db(con)
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert "dialog_text" in tables
    assert "dialog_drift_report" in tables
    assert "dialog_text_fts" in tables
    con.close()

    wrapper_path = ROOT / "build_dialog_index.py"
    wrapper_text = wrapper_path.read_text(encoding="utf-8")
    assert "workbench.devtools.reference.dialog" in wrapper_text
    assert "sqlite3.connect" not in wrapper_text
    assert "Path(__file__)" not in wrapper_text

    spec = importlib.util.spec_from_file_location("_dialog_index_root_compat", wrapper_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert sys.modules[spec.name] is canonical

    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from pathlib import Path; "
            "from workbench.devtools.reference.dialog import build_index as b; "
            "from workbench.client.dat import extractor_bin as de; "
            "from workbench.runtime.paths import REPO_ROOT, DATABASE_PATH; "
            "assert b.TOOLS_ROOT == REPO_ROOT; "
            "assert b.DB_PATH == DATABASE_PATH; "
            "assert b.DAT_EXTRACTOR_EXE == de.EXE; "
            "assert b.dat_id_for_zone(77) == 6497; "
            "assert 'src' in Path(b.__file__).resolve().parts; "
            "print(b.__file__)"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("dialog index package migration: PASS")


if __name__ == "__main__":
    main()
