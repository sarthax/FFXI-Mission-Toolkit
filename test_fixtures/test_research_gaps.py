#!/usr/bin/env python3
"""research_gaps: unresolved requirement, orphan and empty-table detection on a tiny graph."""
import sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import research_gaps as rg


def main():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "g.db"
        c = sqlite3.connect(p)
        c.executescript("""
        create table capability_requirements(feature_id,capability_id,required);
        create table capability_observations(capability_id,status);
        create table entities(entity_id,entity_type);
        create table entity_relationships(source_node,target_node,status);
        create table findings(x);
        insert into capability_requirements values('f1','capA',1),('f1','capB',1),('f1','capC',0);
        insert into capability_observations values('capA','VERIFIED'),('capB','UNKNOWN');
        insert into entities values('e1','NPC'),('e2','NPC');
        insert into entity_relationships values('e1','x','DISCOVERED');
        """)
        c.commit(); c.close()
        r = rg.detect(p)
        req = {g["detail"]: g["status"] for g in r["gaps"] if g["kind"] == "UNRESOLVED_REQUIREMENT"}
        assert req == {"capB": "UNKNOWN", "capC": "NONE"}, req
        assert r["counts"]["ORPHAN_ENTITIES"] == 1 and r["counts"]["EMPTY_TABLE"] == 1, r["counts"]
    print("Research gaps self-test: PASS")


if __name__ == "__main__":
    main()
