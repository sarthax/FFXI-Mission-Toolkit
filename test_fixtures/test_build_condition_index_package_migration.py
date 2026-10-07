#!/usr/bin/env python3
"""Focused migration smoke for the Development build-condition indexer."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent



def main() -> None:
    from workbench.devtools.server import condition_index

    assert not (REPO_ROOT / "build_condition_index.py").exists()

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
