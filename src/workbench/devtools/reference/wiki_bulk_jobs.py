"""Bounded, restart-resumable FFXIclopedia batch importer.

Uses the existing per-page Wiki fetch/merge/structure pipeline. No automatic
full-site background crawler is launched without an explicit user request.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from . import wiki_jobs

_RUNNING: set[str] = set()
_LOCK = threading.Lock()
_DDL = """CREATE TABLE IF NOT EXISTS wiki_bulk_jobs(
    id TEXT PRIMARY KEY, source TEXT NOT NULL, state TEXT NOT NULL,
    page_limit INTEGER NOT NULL, discovered INTEGER NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0, imported INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0, pending_json TEXT NOT NULL DEFAULT '[]',
    last_error TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""


def _connect(db):
    con = sqlite3.connect(str(db), timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_DDL)
    con.commit()
    return con


def _change(db, job_id, **fields):
    with _connect(db) as con:
        if fields:
            sql = ", ".join(f"{field}=?" for field in fields)
            con.execute(f"UPDATE wiki_bulk_jobs SET {sql}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (*fields.values(), job_id))


def status(db):
    with _connect(db) as con:
        if not _RUNNING:
            con.execute("UPDATE wiki_bulk_jobs SET state='interrupted' WHERE state IN ('queued','discovering','running','pausing')")
        rows = con.execute("""SELECT id,source,state,page_limit,discovered,processed,imported,failed,last_error
            FROM wiki_bulk_jobs ORDER BY updated_at DESC LIMIT 8""").fetchall()
    cols = ("id","source","state","page_limit","discovered","processed","imported","failed","last_error")
    return [dict(zip(cols, row)) for row in rows]


def start(db, limit=50):
    if limit not in (50, 250):
        raise ValueError("Batch size must be 50 or 250")
    with _LOCK:
        if _RUNNING:
            raise ValueError("A Wiki batch is already running")
        job_id = uuid.uuid4().hex[:12]
        with _connect(db) as con:
            con.execute("INSERT INTO wiki_bulk_jobs(id,source,state,page_limit) VALUES(?,?,?,?)",
                        (job_id, "FFXIclopedia", "queued", limit))
        _RUNNING.add(job_id)
    threading.Thread(target=_worker, args=(str(db), job_id), daemon=True).start()
    return job_id


def pause(db, job_id):
    with _connect(db) as con:
        row = con.execute("SELECT state FROM wiki_bulk_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError("Unknown batch job")
        if row[0] in ("queued", "discovering", "running"):
            con.execute("UPDATE wiki_bulk_jobs SET state='pausing' WHERE id=?", (job_id,))


def resume(db, job_id):
    with _LOCK:
        if _RUNNING:
            raise ValueError("A Wiki batch is already running")
        with _connect(db) as con:
            row = con.execute("SELECT state FROM wiki_bulk_jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row[0] not in ("paused", "interrupted", "error", "pausing"):
                raise ValueError("Job is not resumable")
            con.execute("UPDATE wiki_bulk_jobs SET state='queued' WHERE id=?", (job_id,))
        _RUNNING.add(job_id)
    threading.Thread(target=_worker, args=(str(db), job_id), daemon=True).start()


def _worker(db, job_id):
    try:
        from . import scrape_ffxiclopedia as fx
        with _connect(db) as con:
            row = con.execute("SELECT page_limit,pending_json,processed FROM wiki_bulk_jobs WHERE id=?",
                              (job_id,)).fetchone()
        limit, pending_raw, processed = row
        pending = json.loads(pending_raw)
        if not pending and not processed:
            _change(db, job_id, state="discovering")
            # Enumerate lazily; ignore titles already imported locally.
            with _connect(db) as con:
                cached = {x[0] for x in con.execute(
                    "SELECT title FROM reference_wiki_pages WHERE source_id='FFXIclopedia'"
                )} if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_wiki_pages'").fetchone() else set()
            for title in fx.all_titles():
                if title not in cached:
                    pending.append(title)
                if len(pending) >= limit:
                    break
            _change(db, job_id, pending_json=json.dumps(pending), discovered=len(pending))
        _change(db, job_id, state="running")
        while pending:
            with _connect(db) as con:
                state = con.execute("SELECT state FROM wiki_bulk_jobs WHERE id=?", (job_id,)).fetchone()[0]
            if state == "pausing":
                _change(db, job_id, state="paused")
                break
            title = pending[0]
            subjob = {"id": uuid.uuid4().hex[:10], "source": "FFXIclopedia", "title": title,
                      "state": "queued", "log": [], "error": None}
            wiki_jobs._run(subjob, db)
            # Save the queue after each page, so a restart never discards progress.
            pending.pop(0)
            fields = {"pending_json": json.dumps(pending), "processed": processed + 1}
            processed += 1
            if subjob["state"] == "done":
                with _connect(db) as con:
                    n = con.execute("SELECT imported FROM wiki_bulk_jobs WHERE id=?", (job_id,)).fetchone()[0]
                fields["imported"] = n + 1
            else:
                with _connect(db) as con:
                    n = con.execute("SELECT failed FROM wiki_bulk_jobs WHERE id=?", (job_id,)).fetchone()[0]
                fields["failed"] = n + 1
                fields["last_error"] = f"{title}: {subjob.get('error') or subjob['state']}"[:400]
            _change(db, job_id, **fields)
            if pending:
                time.sleep(2)
        else:
            _change(db, job_id, state="completed")
    except Exception as exc:
        _change(db, job_id, state="error", last_error=str(exc)[:400])
    finally:
        with _LOCK:
            _RUNNING.discard(job_id)
