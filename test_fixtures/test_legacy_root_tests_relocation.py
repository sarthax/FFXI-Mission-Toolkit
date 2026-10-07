#!/usr/bin/env python3
"""Regression contract for legacy script-style tests relocated out of repository root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MOVED = {
    "test_backport_lua_convert.py": "tests/legacy/test_backport_lua_convert.py",
    "test_backport_sql_convert.py": "tests/legacy/test_backport_sql_convert.py",
    "test_capture_ingestion.py": "tests/legacy/test_capture_ingestion.py",
}


def main() -> None:
    for old, new in MOVED.items():
        assert not (ROOT / old).exists(), old
        assert (ROOT / new).is_file(), new

    capture = (ROOT / MOVED["test_capture_ingestion.py"]).read_text(encoding="utf-8")
    assert "from workbench.runtime.paths import REPO_ROOT" in capture
    assert 'FIXTURES_DIR = REPO_ROOT / "test_fixtures" / "captures"' in capture
    assert "TOOLS_ROOT = Path(__file__).parent" not in capture

    lua = (ROOT / MOVED["test_backport_lua_convert.py"]).read_text(encoding="utf-8")
    sql = (ROOT / MOVED["test_backport_sql_convert.py"]).read_text(encoding="utf-8")
    assert "from workbench.packages.migration import lua_convert as blc" in lua
    assert "from workbench.packages.migration import sql_convert as bsc" in sql

    print("legacy root test relocation: PASS")


if __name__ == "__main__":
    main()
