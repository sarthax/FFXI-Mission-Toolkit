#!/usr/bin/env python3
import sqlite3
import tempfile
from pathlib import Path

from workbench.core.services.map_confidence_graph import import_map_confidence_results


def main():
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        result=import_map_confidence_results(
            [{
                "family":"mobMod",
                "confirmed":[("STR","MOBMOD_STR")],
                "missing":[("FAKE","MOBMOD_FAKE")],
            }],
            db,
            source="topaz",
            target="dsp",
            source_snapshot_id="topaz:test",
            target_snapshot_id="dsp:test",
        )
        assert result["confirmed"]==1,result
        assert result["missing"]==1,result

        con=sqlite3.connect(db)
        rows=con.execute(
            "SELECT subject_id,status,confidence FROM findings "
            "WHERE analysis_id=? ORDER BY subject_id",
            (result["analysis_id"],),
        ).fetchall()
        assert ("namespace-map:mobMod:STR","VERIFIED","INFERRED") in rows,rows
        assert ("namespace-map:mobMod:FAKE","CONTRADICTED","INFERRED") in rows,rows
        notes=con.execute(
            "SELECT notes FROM evidence WHERE evidence_id LIKE 'evidence:map-confidence:%' ORDER BY evidence_id"
        ).fetchall()
        assert len(notes)==2,notes
        con.close()

    print("map confidence canonical graph bridge self-test: PASS")


if __name__=="__main__":
    main()
