#!/usr/bin/env python3
"""Regression check that lexical enum use does not overstate function ownership confidence."""
from __future__ import annotations
import tempfile
from pathlib import Path
from cpp_dependency_index import index

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        (root/"sample.cpp").write_text(
            "enum class State { READY };\n"
            "void handler() { State::READY; }\n",
            encoding="utf-8",
        )
        edges=index(root)
        uses=[e for e in edges if e.relationship=="USES_ENUM" and e.target_node=="State::READY"]
        assert len(uses)==1,uses
        edge=uses[0]
        assert edge.confidence=="INFERRED",edge
        assert any("Exact symbol identity" in note for note in edge.notes),edge.notes
    print("C++ enum dependency confidence self-test: PASS")

if __name__=="__main__":
    main()
