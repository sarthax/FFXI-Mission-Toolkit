"""Audited decisions for individual imported Assault issue bullets."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from workbench.domains.assault_reviews import DB

STAGES = ("topaz", "dsp_port", "dsp_validation")
STATES = ("unreviewed", "open", "in_progress", "fixed", "blocked", "not_applicable")


def _connect(path=DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS assault_issue_reviews(
            mission INTEGER NOT NULL, issue INTEGER NOT NULL, stage TEXT NOT NULL,
            state TEXT NOT NULL, note TEXT NOT NULL, evidence TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(mission, issue, stage));
        CREATE TABLE IF NOT EXISTS assault_issue_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT, mission INTEGER NOT NULL,
            issue INTEGER NOT NULL, stage TEXT NOT NULL, state TEXT NOT NULL,
            note TEXT NOT NULL, evidence TEXT NOT NULL, updated_at TEXT NOT NULL);
    """)
    con.commit()
    return con


def read(path=DB):
    con = _connect(path)
    try:
        return ([dict(r) for r in con.execute("SELECT * FROM assault_issue_reviews")],
                [dict(r) for r in con.execute("SELECT * FROM assault_issue_history ORDER BY id DESC")])
    finally:
        con.close()


def mark(mission, issue, stage, state, note="", evidence="", *, path=DB, issue_count=None):
    if not isinstance(mission, int) or not 1 <= mission <= 50:
        raise ValueError("Invalid mission")
    if not isinstance(issue, int) or issue < 1 or (issue_count is not None and issue > issue_count):
        raise ValueError("Invalid issue index")
    if stage not in STAGES or state not in STATES:
        raise ValueError("Invalid review stage/state")
    note, evidence = (note or "").strip(), (evidence or "").strip()
    if len(note) > 4000 or len(evidence) > 2000:
        raise ValueError("Review input exceeds allowed length")
    if state == "fixed" and not evidence:
        raise ValueError("A fixed status requires supporting evidence")
    now = datetime.now(timezone.utc).isoformat()
    row = (mission, issue, stage, state, note, evidence, now)
    con = _connect(path)
    try:
        with con:
            con.execute("""INSERT INTO assault_issue_reviews VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(mission,issue,stage) DO UPDATE SET
                state=excluded.state,note=excluded.note,evidence=excluded.evidence,
                updated_at=excluded.updated_at""", row)
            con.execute("""INSERT INTO assault_issue_history
                (mission,issue,stage,state,note,evidence,updated_at) VALUES(?,?,?,?,?,?,?)""", row)
    finally:
        con.close()
    return dict(zip(("mission","issue","stage","state","note","evidence","updated_at"), row))
