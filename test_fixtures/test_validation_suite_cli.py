#!/usr/bin/env python3
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    repo=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        ok=root/"ok.py"
        ok.write_text("print('ok')\n",encoding="utf-8")
        suite=root/"suite.json"
        suite.write_text(json.dumps({
            "run_id":"run:cli-test",
            "name":"CLI validation suite",
            "feature_id":"feature:test",
            "validators":[
                {
                    "validation_id":"v:lua",
                    "validation_type":"LUA_SANITY",
                    "subject_id":"artifact:lua",
                    "dimension":"lua",
                    "script":str(ok),
                    "required":True,
                },
                {
                    "validation_id":"v:sql",
                    "validation_type":"SQL_SANITY",
                    "subject_id":"artifact:sql",
                    "dimension":"sql",
                    "script":str(ok),
                    "required":True,
                },
            ],
        }),encoding="utf-8")
        db=root/"workbench.db"
        proc=subprocess.run(
            [
                sys.executable,
                str(repo/"validation_pipeline.py"),
                "--suite",str(suite),
                "--graph-db",str(db),
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )
        assert proc.returncode==0,(proc.stdout,proc.stderr)
        payload=json.loads(proc.stdout)
        assert payload["validation_run"]["status"]=="VERIFIED",payload
        assert payload["dimensions"]["lua"]["status"]=="VERIFIED",payload
        assert payload["dimensions"]["sql"]["status"]=="VERIFIED",payload

        con=sqlite3.connect(db)
        assert con.execute(
            "SELECT status FROM validation_runs WHERE run_id='run:cli-test'"
        ).fetchone()[0]=="VERIFIED"
        assert con.execute(
            "SELECT COUNT(*) FROM validation_results WHERE run_id='run:cli-test'"
        ).fetchone()[0]==2
        con.close()

    print("validation suite CLI self-test: PASS")


if __name__=="__main__":
    main()
