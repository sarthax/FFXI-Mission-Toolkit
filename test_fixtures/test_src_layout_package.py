#!/usr/bin/env python3
"""Regression checks for the transitional src-layout package foundation."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_PACKAGE = ROOT / "src" / "workbench"
BRIDGE = ROOT / "workbench" / "__init__.py"


def main() -> None:
    assert (ROOT / "pyproject.toml").is_file()
    assert (SRC_PACKAGE / "__init__.py").is_file()
    assert (SRC_PACKAGE / "core").is_dir()
    assert (SRC_PACKAGE / "runtime" / "paths.py").is_file()
    assert (SRC_PACKAGE / "domains" / "service.py").is_file()
    assert (SRC_PACKAGE / "domains" / "definitions.json").is_file()
    assert not (ROOT / "workbench" / "domains").exists()
    assert BRIDGE.is_file()

    bridge_text = BRIDGE.read_text(encoding="utf-8")
    assert "src" in bridge_text and "workbench" in bridge_text
    assert "__path__.append" in bridge_text

    # Editable installation in CI must make the canonical src package importable even when
    # neither the repository root nor PYTHONPATH participates in import resolution. Domain
    # resources must load from the canonical package while repository-owned vendor data remains
    # anchored at the repository root via workbench.runtime.paths.
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from pathlib import Path; "
            "import workbench, workbench.runtime.paths as p; "
            "from workbench.domains import service as d; "
            "pkg=Path(workbench.__file__).resolve(); "
            "assert 'src' in pkg.parts, pkg; "
            "assert p.REPO_ROOT.name == 'FFXI-Mission-Toolkit', p.REPO_ROOT; "
            "assert d.DEF_PATH.parent == pkg.parent / 'domains', d.DEF_PATH; "
            "assert d.WIKI_DUMP == p.repo_path('vendor','ffxi-wiki-dumps-dist','bg-wiki.jsonl.gz'), d.WIKI_DUMP; "
            "assert d.load(), 'domain catalog must load'; "
            "print(pkg)"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("src-layout package self-test: PASS")


if __name__ == "__main__":
    main()
