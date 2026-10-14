"""Local read/write review state; independent of imported Topaz issue history."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from workbench.domains.assault_tracker import TRACKER

DB = TRACKER.parent / "assault_reviews.db"
STAGES = ("implementation", "port", "validation")
STATES = ("unverified", "pending", "in_progress", "blocked", "ready_for_test", "validated", "not_applicable")


def _connect(path=DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS reviews (
        mission INTEGER NOT NULL, stage TEXT NOT NULL, state TEXT NOT NULL,
        note TEXT NOT NULL, evidence TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(mission,stage)
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS review_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, mission INTEGER NOT NULL,
        stage TEXT NOT NULL, state TEXT NOT NULL, note TEXT NOT NULL,
        evidence TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")
    con.commit()
    return con


def all_reviews(path=DB):
    con = _connect(path)
    try:
        rows = [dict(r) for r in con.execute("SELECT * FROM reviews ORDER BY mission,stage")]
        history = [dict(r) for r in con.execute("SELECT * FROM review_history ORDER BY id DESC")]
        return rows, history
    finally:
        con.close()


def mark(mission: int, stage: str, state: str, note: str, evidence: str = "", path=DB):
    if not isinstance(mission, int) or not 1 <= mission <= 50:
        raise ValueError("Mission must be between 1 and 50")
    if stage not in STAGES or state not in STATES:
        raise ValueError("Invalid stage or state")
    note, evidence = (note or "").strip(), (evidence or "").strip()
    if len(note) > 4000 or len(evidence) > 2000:
        raise ValueError("Review note or evidence too long")
    if state == "validated" and not evidence:
        raise ValueError("Validated requires an evidence reference")
    timestamp = datetime.now(timezone.utc).isoformat()
    con = _connect(path)
    try:
        with con:
            args = (mission, stage, state, note, evidence, timestamp)
            con.execute("""INSERT INTO reviews VALUES(?,?,?,?,?,?)
                ON CONFLICT(mission,stage) DO UPDATE SET state=excluded.state,
                note=excluded.note,evidence=excluded.evidence,updated_at=excluded.updated_at""", args)
            con.execute("""INSERT INTO review_history(mission,stage,state,note,evidence,updated_at)
                VALUES(?,?,?,?,?,?)""", args)
        return {"mission": mission, "stage": stage, "state": state, "note": note,
                "evidence": evidence, "updated_at": timestamp}
    finally:
        con.close()
