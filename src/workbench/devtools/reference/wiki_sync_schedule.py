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
    result=dict(zip(("enabled","interval_hours","page_limit","next_due",
                     "last_attempt","last_job_id","last_error"),row))
    result["recoverable"]=wiki_bulk_jobs.latest_recoverable(db,job_id=result["last_job_id"]) if result["last_job_id"] else None
    return result

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
        # Never overlap a running import or quietly replace a paused job.
        if wiki_bulk_jobs._RUNNING:
            return {"status":"busy"}
        prior = config.get("last_job_id")
        if prior:
            with wiki_bulk_jobs._connect(db) as con:
                row=con.execute("SELECT state,last_error FROM wiki_bulk_jobs WHERE id=?",(prior,)).fetchone()
            if row and row[0] in ("paused","pausing","error"):
                return {"status":"needs_attention","job_id":prior,"state":row[0]}
            if row and row[0]=="interrupted":
                checkpoint=wiki_bulk_jobs.latest_recoverable(db,job_id=prior)
                if checkpoint:
                    try:
                        wiki_bulk_jobs.resume(db,prior)
                    except ValueError as exc:
                        return {"status":"busy","error":str(exc)}
                    with _db(db) as con:
                        con.execute("""UPDATE wiki_sync_schedule SET last_attempt=?,last_error=NULL,
                            next_due=? WHERE source='FFXIclopedia'""",
                            (_format(now),_format(now+timedelta(hours=config["interval_hours"]))))
                    return {"status":"resumed","job_id":prior}
                return {"status":"needs_attention","job_id":prior,"state":"no_checkpoint"}
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
    # State reconciliation is not a network operation; never auto-resume an
    # interrupted job until its persisted next-due time and checkpoint pass.
    wiki_bulk_jobs.recover_interrupted(db)
    def runner():
        while True:
            try:
                tick(db)
            except Exception:
                # Scheduling must never crash the main toolkit server.
                pass
            time.sleep(60)
    threading.Thread(target=runner,daemon=True,name="wiki-sync-scheduler").start()
