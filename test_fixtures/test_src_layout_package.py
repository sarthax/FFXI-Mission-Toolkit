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
    assert (SRC_PACKAGE / "client" / "binary_index.py").is_file()
    assert (SRC_PACKAGE / "client" / "identity_snapshot.py").is_file()
    assert not (ROOT / "workbench" / "client" / "binary_index.py").exists()
    # Two client modules still have repo-relative vendor lookups and intentionally remain on the
    # compatibility side until their path normalization slice.
    assert (ROOT / "workbench" / "client" / "event_fingerprint.py").is_file()
    assert (ROOT / "workbench" / "client" / "identity_extract.py").is_file()
    assert BRIDGE.is_file()

    bridge_text = BRIDGE.read_text(encoding="utf-8")
    assert "src" in bridge_text and "workbench" in bridge_text
    assert "__path__.append" in bridge_text

    # Editable installation in CI must make the canonical src package importable even when
    # neither the repository root nor PYTHONPATH participates in import resolution. Domain
    # resources must load from the canonical package while repository-owned vendor data remains
    # anchored at the repository root via workbench.runtime.paths. The transitional client
    # namespace must likewise resolve moved modules from src and the two isolated path-sensitive
    # modules from the root compatibility path.
    with tempfile.TemporaryDirectory() as td:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        code = (
            "from pathlib import Path; "
            "import workbench, workbench.runtime.paths as p; "
            "from workbench.domains import service as d; "
            "import workbench.client.binary_index as bi; "
            "import workbench.client.event_fingerprint as ef; "
            "pkg=Path(workbench.__file__).resolve(); "
            "assert 'src' in pkg.parts, pkg; "
            "assert p.REPO_ROOT.name == 'FFXI-Mission-Toolkit', p.REPO_ROOT; "
            "assert d.DEF_PATH.parent == pkg.parent / 'domains', d.DEF_PATH; "
            "assert d.WIKI_DUMP == p.repo_path('vendor','ffxi-wiki-dumps-dist','bg-wiki.jsonl.gz'), d.WIKI_DUMP; "
            "assert d.load(), 'domain catalog must load'; "
            "assert 'src' in Path(bi.__file__).resolve().parts, bi.__file__; "
            "assert Path(ef.__file__).resolve() == p.repo_path('workbench','client','event_fingerprint.py'), ef.__file__; "
            "print(pkg)"
        )
        subprocess.run([sys.executable, "-c", code], cwd=td, env=env, check=True)

    print("src-layout package self-test: PASS")


if __name__ == "__main__":
    main()
