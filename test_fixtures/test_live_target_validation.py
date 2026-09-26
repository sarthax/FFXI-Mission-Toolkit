#!/usr/bin/env python3
"""Regression coverage for adapter-aware live target validation."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.adapters.servers import DSPAdapter
from workbench.migrations.live_target_validation import (
    DBAPITargetReader,
    persist_live_validation,
    validate_live_records,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        (root/"sql").mkdir()
        adapter=DSPAdapter(root)

        live=sqlite3.connect(":memory:")
        live.execute(
            "CREATE TABLE item_equipment("
            "itemid INTEGER, name TEXT, level INTEGER, ilevel INTEGER, jobs INTEGER, "
            "shieldsize INTEGER, slot INTEGER, rslot INTEGER)"
        )
        live.execute(
            "INSERT INTO item_equipment VALUES(?,?,?,?,?,?,?,?)",
            (1,"Verified",99,None,None,None,None,None),
        )
        live.execute(
            "INSERT INTO item_equipment VALUES(?,?,?,?,?,?,?,?)",
            (2,"LiveDifferent",95,None,None,None,None,None),
        )
        live.commit()

        expected=[
            adapter.normalize_row("item_equipment",{"itemid":1,"name":"Verified","level":99}),
            adapter.normalize_row("item_equipment",{"itemid":2,"name":"Expected","level":99}),
            adapter.normalize_row("item_equipment",{"itemid":3,"name":"Missing","level":50}),
        ]

        reader=DBAPITargetReader(live,paramstyle="qmark")
        payload=validate_live_records(
            adapter,
            reader,
            "item_equipment",
            expected,
            target_snapshot_id="live:dsp:test",
        )

        assert payload["status"]=="CONTRADICTED",payload
        by_id={dict(row["identity"])["item_id"]:row for row in payload["results"]}
        assert by_id[1]["status"]=="VERIFIED",by_id
        assert by_id[2]["status"]=="CONTRADICTED",by_id
        assert {d["field"] for d in by_id[2]["differences"]}=={"level","name"},by_id[2]
        assert by_id[3]["status"]=="MISSING",by_id

        graph_db=root/"workbench.db"
        persisted=persist_live_validation(
            payload,
            graph_db,
            run_id="run:live-target:test",
            feature_id="feature:test",
            source_snapshot_id="source:snapshot",
            target_snapshot_id="live:dsp:test",
            source="expected logical records",
            target="live DSP database",
        )
        assert persisted["validation_run"]["status"]=="FAILED",persisted
        assert persisted["validation_run"]["metadata"]["credentials_persisted"] is False,persisted
        assert len(persisted["validation_results"])==3,persisted

        con=sqlite3.connect(graph_db)
        run=con.execute(
            "SELECT status,metadata_json FROM validation_runs WHERE run_id=?",
            ("run:live-target:test",),
        ).fetchone()
        assert run is not None and run[0]=="FAILED",run
        assert con.execute(
            "SELECT COUNT(*) FROM validation_results WHERE run_id=?",
            ("run:live-target:test",),
        ).fetchone()[0]==3
        con.close()
        live.close()

    print("live target validation self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
