"""Conservative opt-in Japanese Wiki cached-page refresh scheduling.

Only already imported titles under an explicitly configured subtree are refreshed.
Errors, interrupted jobs and source restrictions require manual intervention.
"""
from __future__ import annotations
import sqlite3
import threading
import time
from datetime import datetime,timezone,timedelta
from . import wiki_jp_crawl_jobs, wiki_sync_coordination

_LOCK=threading.Lock()
_STARTED=False
_SCHEMA="""CREATE TABLE IF NOT EXISTS wiki_jp_refresh_schedule(
 source TEXT PRIMARY KEY,
 enabled INTEGER NOT NULL DEFAULT 0,
 seed TEXT NOT NULL DEFAULT '',
 interval_hours INTEGER NOT NULL DEFAULT 168,
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
    con=sqlite3.connect(str(path),timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_SCHEMA)
    con.execute("""INSERT OR IGNORE INTO wiki_jp_refresh_schedule
                   (source) VALUES ('WikiWikiJP')""")
    con.commit()
    return con

def settings(db):
    with _db(db) as con:
        row=con.execute("""SELECT enabled,seed,interval_hours,page_limit,next_due,
                       last_attempt,last_job_id,last_error FROM wiki_jp_refresh_schedule
                       WHERE source='WikiWikiJP'""").fetchone()
    return dict(zip(("enabled","seed","interval_hours","page_limit","next_due",
                     "last_attempt","last_job_id","last_error"),row))

def configure(db,*,enabled,seed,interval_hours=168,page_limit=50):
    seed=str(seed or "").strip().strip("/")
    if type(enabled) is not bool or interval_hours not in (24,48,168) or page_limit not in (50,250):
        raise ValueError("Invalid Japanese Wiki schedule settings")
    if enabled and (not seed or seed.startswith(("http:", "https:", ".")) or
                    "?" in seed or ".." in seed.split("/")):
        raise ValueError("Select a Japanese Wiki subtree page path before enabling refresh")
    with _db(db) as con:
        con.execute("""UPDATE wiki_jp_refresh_schedule
                       SET enabled=?,seed=?,interval_hours=?,page_limit=?,
                       next_due=?,last_error=NULL WHERE source='WikiWikiJP'""",
                    (int(enabled),seed,interval_hours,page_limit,
                     _format(_now()) if enabled else None))
    return settings(db)

def tick(db,now=None):
    now=now or _now()
    with _LOCK:
        config=settings(db)
        if not config["enabled"]:
            return {"status":"disabled"}
        if config["next_due"] and datetime.fromisoformat(config["next_due"])>now:
            return {"status":"not_due"}
        coordinated=wiki_sync_coordination.scheduler_can_start()
        if not coordinated["allowed"]:
            return {"status":"busy","running":coordinated["running"]}
        if config["last_job_id"]:
            with wiki_jp_crawl_jobs._db(db) as con:
                prior=con.execute("""SELECT state FROM wiki_jp_crawl_jobs
                    WHERE id=?""",(config["last_job_id"],)).fetchone()
            if prior and prior[0] not in ("completed",):
                return {"status":"needs_attention","job_id":config["last_job_id"],
                        "state":prior[0]}
        try:
            job=wiki_jp_crawl_jobs.start(db,config["seed"],config["page_limit"],mode="refresh")
        except (ValueError,sqlite3.Error,OSError) as exc:
            with _db(db) as con:
                con.execute("""UPDATE wiki_jp_refresh_schedule
                    SET last_attempt=?,last_error=?,next_due=?
                    WHERE source='WikiWikiJP'""",
                    (_format(now),str(exc)[:400],_format(now+timedelta(hours=1))))
            return {"status":"error","error":str(exc)[:400]}
        with _db(db) as con:
            con.execute("""UPDATE wiki_jp_refresh_schedule
                SET last_attempt=?,last_job_id=?,last_error=NULL,next_due=?
                WHERE source='WikiWikiJP'""",
                (_format(now),job,_format(now+timedelta(hours=config["interval_hours"]))))
        return {"status":"started","job_id":job}

def start_background(db):
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED=True
    def loop():
        while True:
            try:
                tick(db)
            except Exception:
                pass
            time.sleep(60)
    threading.Thread(target=loop,daemon=True,name="wiki-jp-refresh-scheduler").start()
