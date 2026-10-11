#!/usr/bin/env python3
"""Regression for human-authored capture review flags and explicit quarantine."""
from __future__ import annotations

import sqlite3

from workbench.captures import review_queue as rq


def _capture_schema(con):
    con.execute("""CREATE TABLE captures (
        capture_id INTEGER PRIMARY KEY,
        capture_label TEXT,
        source_path TEXT
    )""")
    con.execute("INSERT INTO captures VALUES (1,'Fixture Capture','fixture/source.zip')")


def main():
    # Migrate a legacy review_queue that predates per-item blocking.
    con=sqlite3.connect(":memory:")
    _capture_schema(con)
    con.execute("""CREATE TABLE review_queue (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, source_path TEXT, capture_id INTEGER,
        key TEXT NOT NULL DEFAULT '', detail TEXT, status TEXT NOT NULL DEFAULT 'pending',
        resolution TEXT, note TEXT, created_at TEXT, reviewed_at TEXT, UNIQUE(kind, source_path, key)
    )""")
    con.execute(
        "INSERT INTO review_queue(kind,source_path,capture_id,key,detail,status) VALUES (?,?,?,?,?,?)",
        ("empty_ingest","fixture/source.zip",1,"",'{"reason":"legacy"}',"pending"),
    )
    rq.ensure(con)
    assert con.in_transaction is False
    cols={row[1] for row in con.execute("PRAGMA table_info(review_queue)")}
    assert "blocking" in cols,cols
    legacy=con.execute("SELECT blocking FROM review_queue WHERE kind='empty_ingest'").fetchone()
    assert legacy==(1,),legacy
    assert rq.is_quarantined(con,1) is True

    # Close the automated blocker so manual behavior can be tested independently.
    legacy_id=con.execute("SELECT review_id FROM review_queue WHERE kind='empty_ingest'").fetchone()[0]
    rq.decide(con,legacy_id,"dismiss",note="fixture acknowledges empty ingest")
    assert rq.is_quarantined(con,1) is False

    missing=rq.create_manual(
        con,1,"manual_missing_data",
        "Missing final event finish packet",
        "Capture another clean completion and attach it.",
        blocking=False,
    )
    assert missing["status"]=="pending"
    assert missing["blocking"]==0
    assert missing["detail"]["summary"]=="Missing final event finish packet"
    assert rq.is_quarantined(con,1) is False

    invalid=rq.create_manual(
        con,1,"manual_invalid_data",
        "Entity position is suspect",
        "Observed coordinate jump after zoning.",
        blocking=True,
    )
    assert invalid["blocking"]==1
    assert rq.is_quarantined(con,1) is True
    assert rq.pending_count(con,blocking_only=True)==1

    pending=rq.items(con,"pending",capture_id=1)
    assert {row["kind"] for row in pending}=={"manual_missing_data","manual_invalid_data"},pending

    rq.decide(con,invalid["review_id"],"resolve",note="re-captured and verified")
    assert rq.is_quarantined(con,1) is False
    resolved=next(row for row in rq.items(con,"all",capture_id=1) if row["review_id"]==invalid["review_id"])
    assert resolved["status"]=="resolved"
    assert resolved["note"]=="re-captured and verified"

    followup=rq.create_manual(con,1,"manual_followup","Verify drop rate source")
    assert followup["blocking"]==0

    try:
        rq.create_manual(con,1,"zone","not allowed")
        raise AssertionError("non-manual review kind was accepted")
    except ValueError:
        pass

    try:
        rq.create_manual(con,1,"manual_missing_data","   ")
        raise AssertionError("blank manual summary was accepted")
    except ValueError:
        pass

    sql=rq.exclude_sql(con)
    assert "blocking=1" in sql,sql
    con.close()
    print("capture manual review flags self-test: PASS")


if __name__=="__main__":
    main()
