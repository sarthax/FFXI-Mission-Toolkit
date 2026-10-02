#!/usr/bin/env python3
"""Focused migration smoke for the canonical dialog reference services."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_root():
    name = "dialog_drift_overview"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "dialog_drift_overview.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    from workbench.devtools.reference.dialog import drift_overview as canonical

    legacy = _load_root()
    assert legacy is canonical
    assert callable(canonical.detect_offset)
    assert callable(canonical.overview)
    assert callable(canonical.summary)

    real = {i: canonical.normalize(f"Line number {i} of the dialog") for i in range(100)}
    shifted = [(i + 1, f"Line number {i} of the dialog") for i in range(10, 20)]
    result = canonical.detect_offset(shifted, real)
    assert result["offset"] == -1
    assert result["explained"] == 10

    code = r'''
from workbench.devtools.reference.dialog import drift_overview as d
real = {i: d.normalize(f"Line number {i} of the dialog") for i in range(100)}
shifted = [(i + 1, f"Line number {i} of the dialog") for i in range(10, 20)]
r = d.detect_offset(shifted, real)
assert r["offset"] == -1 and r["explained"] == 10
'''
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "test_fixtures" / "test_dialog_index_package_migration.py")],
        check=True,
    )
    print("dialog reference package migrations: OK")


if __name__ == "__main__":
    main()
