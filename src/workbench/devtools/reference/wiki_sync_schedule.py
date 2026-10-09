"""Opt-in, local-server-only FFXIclopedia incremental refresh scheduler.

Default off. Persisted UTC next-due timestamp, bounded jobs, and retry backoff.
Only one scheduler loop is launched per toolkit process.
"""
from __future__ import annotations
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from . import wiki_bulk_jobs

_LOCK = threading.Lock()
_STARTED = False
_DDL = """CREATE TABLE IF NOT EXISTS wiki_sync_schedule (
 source TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
 interval_hours INTEGER NOT NULL DEFAULT 24,
 page_limit INTEGER NOT NULL DEFAULT 50,
 next_due TEXT,
 last_attempt TEXT,
 last_job_id TEXT,
 last_error TEXT
)"""

def _now():
    return datetime.now(timezone.utc)

def _format(value):
    return value.isoformat(timespec="seconds")

def _db(path):
    con = sqlite3.connect(str(path), timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_DDL)
    con.execute("""INSERT OR IGNORE INTO wiki_sync_schedule
                 (source,enabled,interval_hours,page_limit)
                 VALUES ('FFXIclopedia',0,24,50)""")
    con.commit()
    return con

def settings(db):
    with _db(db) as con:
        row=con.execute("""SELECT enabled,interval_hours,page_limit,next_due,
                           last_attempt,last_job_id,last_error FROM wiki_sync_schedule
                           WHERE source='FFXIclopedia'""").fetchone()
    return dict(zip(("enabled","interval_hours","page_limit","next_due",
                     "last_attempt","last_job_id","last_error"),row))

def configure(db, *, enabled, interval_hours=24, page_limit=50):
    if type(enabled) is not bool or interval_hours not in (6,12,24,48,168) or page_limit not in (50,250):
        raise ValueError("Invalid Wiki schedule settings")
    due=_format(_now()) if enabled else None
    with _db(db) as con:
        con.execute("""UPDATE wiki_sync_schedule SET enabled=?,interval_hours=?,
                       page_limit=?,next_due=?,last_error=NULL
                       WHERE source='FFXIclopedia'""",
                    (int(enabled),interval_hours,page_limit,due))
    return settings(db)

def tick(db, now=None):
    """Try one due run. Never starts jobs unless the schedule is enabled."""
    now=now or _now()
    with _LOCK:
        config=settings(db)
        if not config["enabled"]:
            return {"status":"disabled"}
        if config["next_due"] and datetime.fromisoformat(config["next_due"])>now:
            return {"status":"not_due"}
        # Avoid overlap with any local running page batch.
        if wiki_bulk_jobs._RUNNING:
            return {"status":"busy"}
        next_due=_format(now+timedelta(hours=config["interval_hours"]))
        try:
            job_id=wiki_bulk_jobs.start(db,config["page_limit"],mode="changed")
        except (ValueError,OSError,sqlite3.Error) as exc:
            with _db(db) as con:
                con.execute("""UPDATE wiki_sync_schedule SET last_attempt=?,last_error=?,
                               next_due=? WHERE source='FFXIclopedia'""",
                            (_format(now),str(exc)[:400],_format(now+timedelta(hours=1))))
            return {"status":"error","error":str(exc)[:400]}
        with _db(db) as con:
            con.execute("""UPDATE wiki_sync_schedule SET last_attempt=?,last_job_id=?,
                           last_error=NULL,next_due=? WHERE source='FFXIclopedia'""",
                        (_format(now),job_id,next_due))
        return {"status":"started","job_id":job_id}

def start_background(db):
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED=True
    def runner():
        while True:
            try:
                tick(db)
            except Exception:
                # Scheduling must never crash the main toolkit server.
                pass
            time.sleep(60)
    threading.Thread(target=runner,daemon=True,name="wiki-sync-scheduler").start()
