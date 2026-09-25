#!/usr/bin/env python3
import sqlite3
import tempfile
from pathlib import Path

from workbench.core.services.validation_run import ValidationSpec, run_validation_suite


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        ok=root/"ok.py"
        bad=root/"bad.py"
        ok.write_text("print('ok')\n",encoding="utf-8")
        bad.write_text("raise SystemExit(2)\n",encoding="utf-8")
        db=root/"workbench.db"

        out=run_validation_suite(
            (
                ValidationSpec(
                    "v:lua","LUA_SANITY","artifact:lua",str(ok),
                    dimension="lua",required=True,
                ),
                ValidationSpec(
                    "v:sql","SQL_COLLISION","artifact:sql",str(bad),
                    dimension="sql",required=True,
                ),
                ValidationSpec(
                    "v:optional","REFERENCE_CHECK","artifact:ref",str(bad),
                    dimension="reference",required=False,
                ),
            ),
            run_id="run:test",
            name="synthetic validation suite",
            source_snapshot_id="src:test",
            target_snapshot_id="dst:test",
            feature_id="feature:test",
            graph_db=db,
        )
        assert out["validation_run"]["status"]=="FAILED",out
        assert out["dimensions"]["lua"]["status"]=="VERIFIED",out
        assert out["dimensions"]["sql"]["status"]=="FAILED",out
        assert out["dimensions"]["reference"]["status"]=="FAILED",out

        con=sqlite3.connect(db)
        assert con.execute("SELECT status FROM validation_runs WHERE run_id='run:test'").fetchone()[0]=="FAILED"
        results=con.execute(
            "SELECT validation_id,status FROM validation_results WHERE run_id='run:test' ORDER BY validation_id"
        ).fetchall()
        assert ("v:lua","VERIFIED") in results,results
        assert ("v:sql","FAILED") in results,results
        assert con.execute(
            "SELECT COUNT(*) FROM entity_relationships WHERE relationship='VALIDATED_BY'"
        ).fetchone()[0]==3
        con.close()

    print("validation suite orchestration self-test: PASS")


if __name__=="__main__":
    main()
