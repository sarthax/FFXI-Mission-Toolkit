#!/usr/bin/env python3
"""Focused package-migration smoke for the Salvage reconstruction CLI."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.captures.cli import salvage_reconstruct as canonical
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT


def _load_root_launcher():
    path = REPO_ROOT / "salvage_reconstruct.py"
    spec = importlib.util.spec_from_file_location("salvage_reconstruct", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return sys.modules[spec.name]


def main() -> None:
    legacy = _load_root_launcher()
    assert legacy is canonical
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
