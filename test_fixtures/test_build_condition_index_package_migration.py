#!/usr/bin/env python3
"""Focused migration smoke for the Development build-condition indexer."""
from __future__ import annotations

import importlib.util
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
    from workbench.devtools.server import condition_index

    legacy = _load_root("build_condition_index", "build_condition_index.py")
    assert legacy is condition_index

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "sample.cpp").write_text("#ifdef ENABLE_SAMPLE\nint x = 1;\n#endif\n", encoding="utf-8")
        (root / "CMakeLists.txt").write_text("configure_file(input.h output.h)\n", encoding="utf-8")
        findings = condition_index.index(root)
        fields = [f.field for f in findings]
        assert fields.count("compile_condition") == 2, fields
        assert fields.count("generation_marker") == 1, fields

    code = r'''
from pathlib import Path
import tempfile
from workbench.devtools.server import condition_index
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "x.h").write_text("#ifndef X_H\n#define X_H\n#endif\n", encoding="utf-8")
    fs = condition_index.index(root)
    assert [f.field for f in fs] == ["compile_condition", "compile_condition"]
'''
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("build condition index package migration: PASS")


if __name__ == "__main__":
    main()
