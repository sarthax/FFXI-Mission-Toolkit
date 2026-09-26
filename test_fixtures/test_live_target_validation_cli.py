#!/usr/bin/env python3
"""Regression coverage for the read-only live target validation CLI."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from workbench.cli import live_target_validation as cli


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        (root/"sql").mkdir()
        db=root/"live.db"
        con=sqlite3.connect(db)
        con.execute(
            "CREATE TABLE item_armor("
            "itemid INTEGER, name TEXT, level INTEGER, ilevel INTEGER, jobs INTEGER, "
            "shieldsize INTEGER, slot INTEGER, rslot INTEGER)"
        )
        con.execute(
            "INSERT INTO item_armor VALUES(?,?,?,?,?,?,?,?)",
            (1,"Verified",99,None,None,None,None,None),
        )
        con.commit()
        con.close()

        expected=root/"expected.json"
        expected.write_text(json.dumps({
            "logical_type":"item_equipment",
            "source_snapshot_id":"src:test",
            "target_snapshot_id":"live:dsp:test",
            "records":[{
                "logical_type":"item_equipment",
                "identity":[["item_id",1]],
                "fields":{
                    "item_id":1,
                    "name":"Verified",
                    "level":99,
                    "item_level":None,
                    "jobs":None,
                    "shield_size":None,
                    "slot":None,
                    "rslot":None,
                },
                "source_family":"DSP",
                "source_table":"item_armor",
                "notes":[],
            }],
        }),encoding="utf-8")

        output=root/"result.json"
        graph_db=root/"workbench.db"
        code=cli.main([
            "--expected",str(expected),
            "--target-family","DSP",
            "--target-root",str(root),
            "--sqlite-db",str(db),
            "--target-snapshot-id","live:dsp:test",
            "--graph-db",str(graph_db),
            "--run-id","run:cli:live-target",
            "--feature-id","feature:test",
            "--json",str(output),
        ])
        assert code==0,code
        payload=json.loads(output.read_text(encoding="utf-8"))
        assert payload["status"]=="VERIFIED",payload
        assert payload["connection_backend"]=="sqlite",payload
        assert payload["credentials_persisted"] is False,payload
        assert payload["canonical_validation"]["validation_run"]["status"]=="VERIFIED",payload

        con=sqlite3.connect(db)
        assert con.execute("SELECT COUNT(*) FROM item_armor").fetchone()[0]==1
        con.close()

    print("live target validation CLI self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
