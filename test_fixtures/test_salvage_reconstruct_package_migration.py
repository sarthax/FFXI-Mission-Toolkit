#!/usr/bin/env python3
"""Focused package-migration smoke for the Salvage reconstruction CLI."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.captures.cli import salvage_reconstruct as canonical
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT



def main() -> None:
    assert not (REPO_ROOT / "salvage_reconstruct.py").exists()
    assert canonical.DB_PATH == DATABASE_PATH
    assert callable(canonical.main)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from workbench.captures.cli import salvage_reconstruct as m; "
                "from workbench.runtime.paths import DATABASE_PATH; "
                "assert m.DB_PATH == DATABASE_PATH; assert callable(m.main)",
            ],
            cwd=td,
            check=True,
        )
    print("salvage reconstruct package migration: PASS")


if __name__ == "__main__":
    main()
