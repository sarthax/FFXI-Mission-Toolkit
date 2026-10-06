#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.devtools.reference.dialog import audit_drift
from workbench.reference.dialog import audit_drift as legacy_audit_drift
from workbench.runtime.paths import REPO_ROOT, VENDOR_ROOT


def main() -> None:
    assert legacy_audit_drift is audit_drift
    assert not (REPO_ROOT / "audit_dialog_drift.py").exists()

    assert audit_drift.dat_id_for_zone(0) == 6420
    assert audit_drift.dat_id_for_zone(255) == 6675
    assert audit_drift.dat_id_for_zone(256) == 85590
    assert audit_drift.dat_id_for_zone(511) == 85845
    try:
        audit_drift.dat_id_for_zone(512)
    except ValueError:
        pass
    else:
        raise AssertionError("zone ids above 511 must be rejected")

    assert audit_drift.normalize("Hello, <Player Name>!") == "hello"
    assert audit_drift.normalize("Hello ${name-player}!") == "hello"
    assert audit_drift.normalize("[apple/apples] found") == "found"

    with tempfile.TemporaryDirectory() as td:
        sample = Path(td) / "dialog.yml"
        sample.write_text("  10: 'Hello''s'\n  11: |-\n    First line\n    Second line\n", encoding="utf-8")
        assert audit_drift.parse_real_dialog(sample) == {10: "Hello's", 11: "First line Second line"}

    assert audit_drift.XI_TINKERER_EXE == VENDOR_ROOT / "xi-tinkerer/target/release/xi-tinkerer-cli.exe"
    assert REPO_ROOT in audit_drift.XI_TINKERER_EXE.parents

    with tempfile.TemporaryDirectory() as td:
        code = (
            "from workbench.devtools.reference.dialog import audit_drift as a; "
            "from workbench.reference.dialog import audit_drift as legacy; "
            "from workbench.runtime.paths import REPO_ROOT; "
            "assert legacy is a; "
            "assert a.XI_TINKERER_EXE.is_absolute(); "
            "assert REPO_ROOT in a.XI_TINKERER_EXE.parents; "
            "assert a.dat_id_for_zone(256) == 85590"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, check=True)

    subprocess.run(
        [sys.executable, "-m", "workbench.devtools.reference.dialog.audit_drift", "--help"],
        cwd=tempfile.gettempdir(),
        check=True,
        stdout=subprocess.DEVNULL,
    )

    print("dialog drift audit package migration: PASS")


if __name__ == "__main__":
    main()
