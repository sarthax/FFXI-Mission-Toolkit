#!/usr/bin/env python3
"""Migration smoke for Development wiki evidence graph persistence."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from workbench.core.services import wiki_evidence_graph as legacy_graph
from workbench.devtools.reference import wiki_claim_compare, wiki_evidence, wiki_evidence_graph as canonical_graph


def main() -> None:
    assert legacy_graph is canonical_graph
    assert canonical_graph.wiki_evidence is wiki_evidence
    assert canonical_graph.wiki_claim_compare is wiki_claim_compare
    assert legacy_graph.import_wiki_evidence is canonical_graph.import_wiki_evidence
    assert legacy_graph.import_wiki_alignment is canonical_graph.import_wiki_alignment

    with tempfile.TemporaryDirectory() as tmp:
        env=dict(os.environ)
        env.pop("PYTHONPATH",None)
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from workbench.devtools.reference import wiki_evidence, wiki_claim_compare, wiki_evidence_graph; "
                "assert wiki_evidence_graph.wiki_evidence is wiki_evidence; "
                "assert wiki_evidence_graph.wiki_claim_compare is wiki_claim_compare; "
                "print(wiki_evidence_graph.import_wiki_evidence.__name__)",
            ],
            cwd=tmp,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    print("wiki evidence graph package migration: OK")


if __name__ == "__main__":
    main()
