#!/usr/bin/env python3
"""Focused package migration smoke for mission event reconciliation."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent



def main() -> None:
    from workbench.devtools.missions import event_reconcile
    from workbench.plugins.domain import mission_event_reconcile as legacy_package

    assert legacy_package is event_reconcile
    assert not (REPO_ROOT / "mission_event_reconcile.py").exists()

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
