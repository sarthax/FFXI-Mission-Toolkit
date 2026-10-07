#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3

from workbench.captures.ingestion import build_index as build_capture_index


def main():
    con = sqlite3.connect(":memory:")
    build_capture_index.init_db(con)
    cid = build_capture_index.create_manual_capture(con, "windower logger", "Research", None)

    timestamped = (
        "19:35:34A home point can be set here.\n"
        "19:35:40It costs 100 gil to teleport.\n"
    ).encode("utf-8")
    result = build_capture_index.ingest_single_file(
        con, cid, "Testchar_2026.09.28.log", timestamped
    )
    assert result["format"] == "windower_logger", result
    assert result["rows"] == 2 and result["error"] is None, result

    rows = con.execute(
        """SELECT ts,direction,zone_id,zone_db,text,source_format,source_native_id
           FROM capture_chat_observations
           WHERE capture_id=? AND source_format='windower_logger'
           ORDER BY seq""",
        (cid,),
    ).fetchall()
    assert rows == [
        (
            "2026-09-28 19:35:34", None, None, None,
            "A home point can be set here.", "windower_logger",
            "Testchar_2026.09.28.log:line:1",
        ),
        (
            "2026-09-28 19:35:40", None, None, None,
            "It costs 100 gil to teleport.", "windower_logger",
            "Testchar_2026.09.28.log:line:2",
        ),
    ], rows

    locators = con.execute(
        """SELECT locator_basis,start_line,end_line,start_offset,end_offset,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename='Testchar_2026.09.28.log'
             AND target_table='capture_chat_observations'
           ORDER BY start_line""",
        (cid,),
    ).fetchall()
    assert len(locators) == 2, locators
    assert all(row[0] == "line" for row in locators), locators
    assert all(row[1] == row[2] for row in locators), locators
    assert all(row[3] is not None and row[4] > row[3] for row in locators), locators
    details = json.loads(locators[0][5])
    assert details["player_from_filename"] == "Testchar", details
    assert details["date_from_filename"] == "2026-09-28", details
    assert details["timestamp_present"] is True, details

    # Logger defaults to no timestamp; preserve those lines without inventing one.
    cid2 = build_capture_index.create_manual_capture(con, "windower logger no ts", "Research", None)
    plain = b"Welcome to Vana'diel.\nAnother line.\n"
    result2 = build_capture_index.ingest_single_file(
        con, cid2, "Alt_2015.01.02.log", plain
    )
    assert result2["format"] == "windower_logger", result2
    rows2 = con.execute(
        """SELECT ts,text FROM capture_chat_observations
           WHERE capture_id=? AND source_format='windower_logger'
           ORDER BY seq""",
        (cid2,),
    ).fetchall()
    assert rows2 == [(None, "Welcome to Vana'diel."), (None, "Another line.")], rows2

    # Reingest replaces exact line identities instead of duplicating observations.
    again = build_capture_index.ingest_single_file(
        con, cid, "Testchar_2026.09.28.log", timestamped
    )
    assert again["rows"] == 2, again
    assert con.execute(
        """SELECT COUNT(*) FROM capture_chat_observations
           WHERE capture_id=? AND source_format='windower_logger'""",
        (cid,),
    ).fetchone()[0] == 2

    con.close()
    print("Windower Logger canonical chat regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
