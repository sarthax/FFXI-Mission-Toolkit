#!/usr/bin/env python3
"""Focused package migration smoke for mission event reconciliation."""
from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_root(name: str, path: str):
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    from workbench.devtools.missions import event_reconcile
    from workbench.plugins.domain import mission_event_reconcile as legacy_package

    legacy_root = _load_root("mission_event_reconcile", "mission_event_reconcile.py")
    assert legacy_package is event_reconcile
    assert legacy_root is event_reconcile

    con = sqlite3.connect(":memory:")
    try:
        assert event_reconcile.reconcile_feature_events(con, "mission:test") == ()
    finally:
        con.close()

    code = """
import sqlite3
from workbench.devtools.missions import event_reconcile
from workbench.plugins.domain import mission_event_reconcile
assert mission_event_reconcile is event_reconcile
con = sqlite3.connect(':memory:')
try:
    assert event_reconcile.reconcile_feature_events(con, 'mission:test') == ()
finally:
    con.close()
print('outside-repo mission event reconciliation import: PASS')
"""
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("mission event reconciliation package migration: PASS")


if __name__ == "__main__":
    main()
