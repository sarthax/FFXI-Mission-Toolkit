#!/usr/bin/env python3
"""Migration smoke for Development-owned map-confidence graph persistence."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.core.services.map_confidence_graph import import_map_confidence_results as legacy_import
from workbench.devtools.server.map_confidence_graph import import_map_confidence_results as canonical_import


def main() -> None:
    assert legacy_import is canonical_import
    with tempfile.TemporaryDirectory() as tmp:
        env=dict(os.environ)
        env.pop("PYTHONPATH",None)
        subprocess.run(
            [sys.executable,"-c","from workbench.devtools.server.map_confidence_graph import import_map_confidence_results; print(import_map_confidence_results.__name__)"],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    print("map confidence graph package migration: OK")


if __name__ == "__main__":
    main()
