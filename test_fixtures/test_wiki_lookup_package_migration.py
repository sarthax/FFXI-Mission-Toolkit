#!/usr/bin/env python3
"""Migration smoke for Development-owned wiki lookup tooling."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
from workbench.devtools.reference import wiki_lookup as canonical
from workbench.runtime.paths import VENDOR_ROOT


def main() -> None:
    assert not (REPO_ROOT / "wiki_lookup.py").exists()
    assert canonical.DUMP_PATH == VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"
    with tempfile.TemporaryDirectory() as tmp:
        env=dict(os.environ)
        env.pop("PYTHONPATH",None)
        subprocess.run(
            [sys.executable,"-c","from workbench.devtools.reference.wiki_lookup import DUMP_PATH, clean_wikitext; print(DUMP_PATH); print(clean_wikitext('[[Foo|Bar]]'))"],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    print("wiki lookup package migration: OK")


if __name__ == "__main__":
    main()
