#!/usr/bin/env python3
"""Migration smoke for Development wiki evidence and claim-comparison tooling."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
from workbench.devtools.reference import wiki_evidence as canonical_evidence
from workbench.devtools.reference import wiki_claim_compare as canonical_compare
from workbench.devtools.reference import wiki_lookup as canonical_lookup
from workbench.runtime.paths import DATABASE_PATH, VENDOR_ROOT


def main() -> None:
    assert not (REPO_ROOT / "wiki_evidence.py").exists()
    assert not (REPO_ROOT / "wiki_claim_compare.py").exists()
    assert canonical_evidence.wiki_lookup is canonical_lookup
    assert canonical_compare.wiki_evidence is canonical_evidence
    assert canonical_evidence.DB_PATH == DATABASE_PATH
    assert canonical_evidence.BG_DUMP_PATH == VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"

    original = canonical_evidence.find_reference_page
    marker = lambda *_args, **_kwargs: None
    canonical_evidence.find_reference_page = marker
    try:
        assert canonical_evidence.find_reference_page is marker
        assert canonical_evidence.ingest_page.__globals__["find_reference_page"] is marker
    finally:
        canonical_evidence.find_reference_page = original

    with tempfile.TemporaryDirectory() as tmp:
        env=dict(os.environ)
        env.pop("PYTHONPATH",None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from workbench.devtools.reference import wiki_evidence, wiki_claim_compare; "
                "from workbench.runtime.paths import DATABASE_PATH; "
                "assert wiki_evidence.DB_PATH == DATABASE_PATH; "
                "assert wiki_claim_compare.wiki_evidence is wiki_evidence; "
                "print(wiki_evidence.title_from_query('Foo_Bar'))",
            ],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    print("wiki evidence package migration: OK")


if __name__ == "__main__":
    main()
