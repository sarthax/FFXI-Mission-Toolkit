#!/usr/bin/env python3
"""Regression coverage for retiring the root gear_tables compatibility shim."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from workbench.client.models import gear_tables

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    assert not (ROOT / "gear_tables.py").exists()
    assert gear_tables.model_id_to_file_id("ElvaanFemale", "head", 20) == 16660
    assert "ElvaanFemale" in gear_tables.GEAR_TABLES

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from workbench.client.models import gear_tables; "
                "assert gear_tables.model_id_to_file_id('ElvaanFemale', 'head', 20) == 16660; "
                "print(gear_tables.__file__)"
            ),
        ],
        cwd=Path.home(),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "workbench/client/models/gear_tables.py" in proc.stdout.replace("\\", "/"), proc.stdout

    print("gear tables package migration: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
