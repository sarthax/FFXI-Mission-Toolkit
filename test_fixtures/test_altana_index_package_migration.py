#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.client.models import build_altana_index as canonical
from workbench.runtime.paths import REPO_ROOT


def load_root_alias():
    spec = importlib.util.spec_from_file_location("_altana_index_legacy", REPO_ROOT / "build_altana_index.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return sys.modules[spec.name]


def main() -> None:
    legacy = load_root_alias()
    assert legacy is canonical
    assert canonical.DB_PATH == REPO_ROOT / "altana_view_index.db"

    assert canonical.parse_location_refs("1/2/3") == [(1, 2, 3, 3)]
    assert canonical.parse_location_refs("1/2/3-5; 4/6/7") == [(1, 2, 3, 5), (4, 6, 7, 7)]
    assert canonical.parse_location_refs("garbage;1/2/3") == [(1, 2, 3, 3)]

    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "List"
        nested = root / "NPC" / "HumeM"
        nested.mkdir(parents=True)
        (nested / "sample.csv").write_text(
            "@Idle\n1/2/3,First\n1/2/4-5;2/7/8,Second, With Comma\n",
            encoding="utf-8",
        )
        conn = sqlite3.connect(":memory:")
        canonical.build(root, conn)
        rows = conn.execute(
            "select category,subcategory,section,row_order,raw_locations,name,source_csv "
            "from altana_rows order by id"
        ).fetchall()
        assert rows == [
            ("NPC", "HumeM", "Idle", 1, "1/2/3", "First", "NPC/HumeM/sample.csv"),
            ("NPC", "HumeM", "Idle", 2, "1/2/4-5;2/7/8", "Second, With Comma", "NPC/HumeM/sample.csv"),
        ]
        locations = conn.execute(
            "select row_id,region,dir,file_start,file_end from altana_locations order by row_id,region,dir,file_start"
        ).fetchall()
        assert locations == [(1, 1, 2, 3, 3), (2, 1, 2, 4, 5), (2, 2, 7, 8, 8)]
        conn.close()

    with tempfile.TemporaryDirectory() as td:
        code = (
            "from workbench.client.models import build_altana_index as m; "
            "from workbench.runtime.paths import REPO_ROOT; "
            "assert m.DB_PATH == REPO_ROOT / 'altana_view_index.db'; "
            "assert m.parse_location_refs('1/2/3-4') == [(1,2,3,4)]"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, check=True)

    print("altana index package migration: PASS")


if __name__ == "__main__":
    main()
