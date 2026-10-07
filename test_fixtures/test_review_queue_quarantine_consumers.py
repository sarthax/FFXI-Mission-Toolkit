#!/usr/bin/env python3
"""Aggregate readers must skip captures with a pending BLOCKING review item; non-blocking items don't exclude."""
from __future__ import annotations
import sqlite3, tempfile
from pathlib import Path
from workbench.captures import review_queue as rq
from workbench.captures.correlation.graph_connect import connect
from workbench.core import graph


def main():
    con = sqlite3.connect(":memory:")
    assert rq.exclude_sql(con) == ""            # no queue table yet -> no filter, no crash
    con.execute("CREATE TABLE captures(capture_id INTEGER PRIMARY KEY, source_path TEXT)")
    for i in (1, 2, 3):
        con.execute("INSERT INTO captures VALUES(?,?)", (i, f"s{i}"))
    rq.raise_item(con, "empty_ingest", "s2", 2, "", {"reason": "x"})            # blocking
    rq.raise_item(con, "unrecognized_file", "s3", 3, "", {"reason": "x"})       # non-blocking
    ids = [r[0] for r in con.execute("SELECT capture_id FROM captures WHERE 1=1" + rq.exclude_sql(con))]
    assert ids == [1, 3], ids
    rq.decide(con, 1 + 0 if False else con.execute("SELECT review_id FROM review_queue WHERE kind='empty_ingest'").fetchone()[0], "dismiss", None, "ok")
    ids = [r[0] for r in con.execute("SELECT capture_id FROM captures WHERE 1=1" + rq.exclude_sql(con))]
    assert ids == [1, 2, 3], ids

    with tempfile.TemporaryDirectory() as td:
        root = Path(td); src = sqlite3.connect(root / "c.db")
        src.execute("""CREATE TABLE capture_events(capture_id INTEGER, zone_db TEXT, seq INTEGER, direction TEXT,
            opcode TEXT, opcode_name TEXT, entity_id INTEGER, entity_name TEXT, event_hex TEXT, option INTEGER,
            message_id INTEGER, params_raw TEXT)""")
        for cid in (1, 2):
            src.execute("INSERT INTO capture_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, "Bastok_Mines", 1, "S2C", "02A", "event packet", 17000001, "N", None, None, None, None))
        rq.ensure(src)
        rq.raise_item(src, "empty_ingest", "s2", 2, "", {"reason": "x"})
        src.commit(); src.close()
        counts = connect(root / "c.db", root / "g.db")
        assert counts["counts"]["capture_events"] == 1, counts
    print("ok")


if __name__ == "__main__":
    main()
