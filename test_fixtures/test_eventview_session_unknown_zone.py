#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path

from workbench.captures.ingestion import build_index as bci


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "test_fixtures" / "captures" / "tacocat_leujaoam_sanctum" / "Tacocat"


def main():
    con = sqlite3.connect(":memory:")
    bci.init_db(con)
    cid = bci.create_manual_capture(con, "eventview session scope", "Research", None)

    src = bci.Source(SOURCE)
    results = []
    try:
        counts = bci.ingest_from_source(con, cid, src, file_results=results)
    finally:
        src.close()

    failures = [row for row in results if row.get("error")]
    assert failures == [], failures

    unknown = con.execute(
        """SELECT seq,direction,opcode,entity_id,event_hex,option,message_id
           FROM capture_events
           WHERE capture_id=? AND zone_db=?
           ORDER BY seq""",
        (cid, bci.ZONE_UNKNOWN),
    ).fetchall()
    assert unknown, "whole-session simple.log produced no zone-unknown decoded events"

    known = con.execute(
        """SELECT COUNT(*) FROM capture_events
           WHERE capture_id=? AND zone_db='Leujaoam Sanctum'""",
        (cid,),
    ).fetchone()[0]
    assert known > 0, "per-zone EventView/simple evidence was lost"

    raw = con.execute(
        """SELECT ts,direction,opcode,zone_id,source_format,source_native_id,raw_hex
           FROM capture_raw_packets
           WHERE capture_id=? AND source_format='eventview_session_raw'
           ORDER BY seq""",
        (cid,),
    ).fetchall()
    assert raw, "whole-session raw.log produced no raw packet evidence"
    assert all(row[0] is None for row in raw), raw
    assert all(row[3] is None for row in raw), raw
    assert all(row[4] == "eventview_session_raw" for row in raw), raw
    assert all(row[5] and ":block:" in row[5] for row in raw), raw
    assert all(row[6] for row in raw), raw

    formats = {
        filename: fmt
        for filename, fmt in con.execute(
            """SELECT filename,format_detected FROM capture_source_manifest
               WHERE capture_id=?""",
            (cid,),
        )
    }
    assert formats["eventview/simple.log"] == "eventview_session_simple", formats
    assert formats["eventview/raw.log"] == "eventview_session_raw", formats

    simple_locators = con.execute(
        """SELECT target_table,locator_basis,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename='eventview/simple.log'
           ORDER BY target_table,row_key""",
        (cid,),
    ).fetchall()
    assert simple_locators
    assert all(row[0] == "capture_events" for row in simple_locators)
    assert all(row[1] == "block" for row in simple_locators)

    raw_locators = con.execute(
        """SELECT target_table,locator_basis,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename='eventview/raw.log'
           ORDER BY row_key""",
        (cid,),
    ).fetchall()
    assert raw_locators
    assert all(row[0] == "capture_raw_packets" for row in raw_locators)
    assert all(row[1] == "block" for row in raw_locators)
    assert all('"zone_attribution": "unknown"' in row[2] for row in raw_locators)

    assert counts["events"] >= len(unknown)
    assert counts["raw_packets"] >= len(raw)

    con.close()
    print("Whole-session EventView unknown-zone regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
