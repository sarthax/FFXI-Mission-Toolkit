#!/usr/bin/env python3
"""Focused migration smoke for Development research gap detection."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from workbench.devtools.research import gaps

    assert not (REPO_ROOT / "research_gaps.py").exists()
    assert callable(gaps.detect)

    code = r'''
import sqlite3, tempfile
from pathlib import Path
from workbench.devtools.research import gaps

with tempfile.TemporaryDirectory() as td:
    db = Path(td) / "graph.db"
    con = sqlite3.connect(db)
    con.executescript("""
    create table capability_requirements(feature_id, capability_id, required);
    create table capability_observations(capability_id, status);
    create table entities(entity_id, entity_type);
    create table entity_relationships(source_node, target_node, status);
    create table findings(x);
    insert into capability_requirements values('f1','capA',1),('f1','capB',1);
    insert into capability_observations values('capA','VERIFIED'),('capB','UNKNOWN');
    insert into entities values('e1','NPC'),('e2','NPC');
    insert into entity_relationships values('e1','x','DISCOVERED');
    """)
    con.commit(); con.close()
    result = gaps.detect(db)
    assert result["counts"]["UNRESOLVED_REQUIREMENT"] == 1
    assert result["counts"]["ORPHAN_ENTITIES"] == 1
    assert result["counts"]["UNVERIFIED_RELATIONSHIPS"] == 1
    assert result["counts"]["EMPTY_TABLE"] == 1
'''
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("research gaps package migration: PASS")


if __name__ == "__main__":
    main()
