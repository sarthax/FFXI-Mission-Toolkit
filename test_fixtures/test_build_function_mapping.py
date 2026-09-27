#!/usr/bin/env python3
"""Regression checks for exact vs ambiguous basename function build mapping."""
from __future__ import annotations
import tempfile
from pathlib import Path
from build_integration_index import index

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        (root/"src").mkdir(); (root/"other").mkdir()
        (root/"src"/"worker.cpp").write_text("void alpha() {}\n",encoding="utf-8")
        (root/"other"/"worker.cpp").write_text("void beta() {}\n",encoding="utf-8")
        (root/"CMakeLists.txt").write_text("add_executable(app src/worker.cpp)\n",encoding="utf-8")
        _builders,_findings,_targets,edges=index(root)
        fn_edges=[e for e in edges if e.relationship=="BUILDS_INTO" and str(e.source_node).startswith("cpp:")]
        assert fn_edges,edges
        assert all(e.confidence=="VERIFIED" for e in fn_edges),fn_edges

        (root/"CMakeLists.txt").write_text("add_executable(app worker.cpp)\n",encoding="utf-8")
        _builders,_findings,_targets,edges=index(root)
        ambiguous=[e for e in edges if e.relationship=="BUILDS_INTO" and str(e.source_node).startswith("cpp:")]
        assert ambiguous==[],ambiguous
    print("build function mapping self-test: PASS")

if __name__=="__main__":
    main()
