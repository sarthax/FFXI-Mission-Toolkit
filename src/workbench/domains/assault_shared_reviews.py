"""Audited review and explicit mission links for Assault shared infrastructure topics."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from workbench.domains.assault_reviews import DB

STAGES = ("topaz", "dsp_port", "dsp_validation")
STATES = ("unreviewed", "open", "in_progress", "fixed", "blocked", "not_applicable")


def connect(path=DB):
    path=Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(path)
    c.row_factory=sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS assault_shared_reviews(
       topic TEXT NOT NULL, stage TEXT NOT NULL, state TEXT NOT NULL,
       note TEXT NOT NULL, evidence TEXT NOT NULL, updated_at TEXT NOT NULL,
       PRIMARY KEY(topic,stage));
    CREATE TABLE IF NOT EXISTS assault_shared_history(
       id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL,
       stage TEXT NOT NULL, state TEXT NOT NULL, note TEXT NOT NULL,
       evidence TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS assault_shared_zones(topic TEXT NOT NULL, zone TEXT NOT NULL, evidence TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(topic,zone));
    CREATE TABLE IF NOT EXISTS assault_shared_missions(
       topic TEXT NOT NULL, mission INTEGER NOT NULL,
       PRIMARY KEY(topic,mission));
    """)
    c.commit()
    return c


def read(path=DB):
    c=connect(path)
    try:
        return {
          "reviews":[dict(r) for r in c.execute("SELECT * FROM assault_shared_reviews")],
          "history":[dict(r) for r in c.execute("SELECT * FROM assault_shared_history ORDER BY id DESC")],
          "links":[dict(r) for r in c.execute("SELECT * FROM assault_shared_missions ORDER BY mission")],
          "zones":[dict(r) for r in c.execute("SELECT * FROM assault_shared_zones ORDER BY zone")]}
    finally:
        c.close()


def update(topic, stage, state, note="", evidence="", *, topics, path=DB):
    if topic not in topics: raise ValueError("Unknown shared topic")
    if stage not in STAGES or state not in STATES: raise ValueError("Invalid stage/state")
    note,evidence=(note or "").strip(),(evidence or "").strip()
    if len(note)>4000 or len(evidence)>2000: raise ValueError("Input too long")
    if state=="fixed" and not evidence: raise ValueError("Fixed requires evidence")
    now=datetime.now(timezone.utc).isoformat()
    row=(topic,stage,state,note,evidence,now)
    c=connect(path)
    try:
        with c:
            c.execute("""INSERT INTO assault_shared_reviews VALUES(?,?,?,?,?,?)
                ON CONFLICT(topic,stage) DO UPDATE SET state=excluded.state,
                note=excluded.note,evidence=excluded.evidence,updated_at=excluded.updated_at""",row)
            c.execute("""INSERT INTO assault_shared_history(topic,stage,state,note,evidence,updated_at)
                VALUES(?,?,?,?,?,?)""",row)
    finally:c.close()


def link(topic, mission, *, topics, path=DB, unlink=False):
    if topic not in topics:raise ValueError("Unknown shared topic")
    if not isinstance(mission,int) or not 1<=mission<=50:raise ValueError("Invalid mission")
    c=connect(path)
    try:
        with c:
            if unlink:
                c.execute("DELETE FROM assault_shared_missions WHERE topic=? AND mission=?",(topic,mission))
            else:
                c.execute("INSERT OR IGNORE INTO assault_shared_missions VALUES(?,?)",(topic,mission))
    finally:c.close()


def set_zone(topic, zone, evidence="", *, topics, zones, path=DB, unlink=False):
    """Explicitly confirm or remove zone-level dependency, without mutating mission links."""
    if topic not in topics: raise ValueError("Unknown shared topic")
    if zone not in zones: raise ValueError("Unknown Assault zone")
    evidence=(evidence or "").strip()
    if len(evidence)>2000: raise ValueError("Evidence too long")
    if not unlink and not evidence: raise ValueError("Zone scope requires evidence")
    c=connect(path)
    try:
        with c:
            if unlink:
                c.execute("DELETE FROM assault_shared_zones WHERE topic=? AND zone=?",(topic,zone))
            else:
                c.execute("""INSERT INTO assault_shared_zones VALUES(?,?,?,?)
                    ON CONFLICT(topic,zone) DO UPDATE SET evidence=excluded.evidence,
                    updated_at=excluded.updated_at""",
                    (topic,zone,evidence,datetime.now(timezone.utc).isoformat()))
    finally:c.close()
