"""Checkpointed, polite WikiWikiJP crawl using the shared Wiki import pipeline."""
from __future__ import annotations
import json
import sqlite3
import tempfile
import os
import threading
import time
import urllib.error
import uuid
import hashlib
from pathlib import Path
from . import wiki_jobs, wiki_document, scrape_wikiwiki_jp as jp

_LOCK = threading.Lock()
_RUNNING = set()
_SCHEMA = """CREATE TABLE IF NOT EXISTS wiki_jp_crawl_jobs(
 id TEXT PRIMARY KEY, state TEXT NOT NULL, seed TEXT NOT NULL, page_limit INTEGER NOT NULL,
 mode TEXT NOT NULL DEFAULT 'crawl',
 queue_json TEXT NOT NULL, seen_json TEXT NOT NULL DEFAULT '[]',
 processed INTEGER NOT NULL DEFAULT 0, imported INTEGER NOT NULL DEFAULT 0,
 failed INTEGER NOT NULL DEFAULT 0, last_error TEXT,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""


def _db(path):
    con=sqlite3.connect(str(path),timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_SCHEMA)
    if 'mode' not in {r[1] for r in con.execute('PRAGMA table_info(wiki_jp_crawl_jobs)')}:
        con.execute("ALTER TABLE wiki_jp_crawl_jobs ADD COLUMN mode TEXT NOT NULL DEFAULT 'crawl'")
    con.commit()
    return con


def _update(db, job_id, **changes):
    with _db(db) as con:
        sql=", ".join(k+"=?" for k in changes)
        con.execute("UPDATE wiki_jp_crawl_jobs SET "+sql+", updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (*changes.values(),job_id))


def status(db):
    with _db(db) as con:
        if not _RUNNING:
            con.execute("UPDATE wiki_jp_crawl_jobs SET state='interrupted' WHERE state IN ('queued','running','pausing')")
        rows=con.execute("""SELECT id,state,seed,page_limit,processed,imported,failed,mode,
                           last_error,queue_json FROM wiki_jp_crawl_jobs
                           ORDER BY updated_at DESC LIMIT 8""").fetchall()
    return [dict(id=r[0],state=r[1],seed=r[2],page_limit=r[3],processed=r[4],
                 imported=r[5],failed=r[6],mode=r[7],last_error=r[8],pending=len(json.loads(r[9]))) for r in rows]


def _in_subtree(title, seed):
    """Match the seed itself or descendants separated by a path slash."""
    return title == seed or title.startswith(seed + "/")


def start(db,seed,limit=50,mode="crawl"):
    seed=str(seed).strip().strip("/")
    if not seed or seed.startswith(("http:", "https:", ".")) or "?" in seed or ".." in seed.split("/"):
        raise ValueError("Enter a Japanese Wiki page path, not a URL or query string")
    if limit not in (50,250):
        raise ValueError("Batch size must be 50 or 250")
    if mode not in ("crawl","refresh"):
        raise ValueError("Invalid Japanese Wiki mode")
    with _LOCK:
        if _RUNNING:
            raise ValueError("A Japanese Wiki crawl is already running")
        ident=uuid.uuid4().hex[:12]
        with _db(db) as con:
            if mode == "refresh":
                if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_wiki_pages'").fetchone():
                    raise ValueError("Import Japanese Wiki pages before refreshing them")
                titles=[r[0] for r in con.execute(
                    "SELECT title FROM reference_wiki_pages WHERE source_id='WikiWikiJP' AND (title=? OR title LIKE ? ESCAPE '^' ) ORDER BY title LIMIT ?",
                    (seed,seed.replace("^", "^^").replace("%", "^%").replace("_", "^_")+"/%",limit)).fetchall()]
                if not titles:
                    raise ValueError("No cached Japanese Wiki pages match this seed")
            else:
                titles=[seed]
            con.execute("""INSERT INTO wiki_jp_crawl_jobs
                (id,state,seed,page_limit,mode,queue_json) VALUES(?,?,?,?,?,?)""",
                (ident,"queued",seed,limit,mode,json.dumps(titles,ensure_ascii=False)))
        _RUNNING.add(ident)
    threading.Thread(target=_worker,args=(str(db),ident),daemon=True).start()
    return ident


def pause(db,ident):
    with _db(db) as con:
        con.execute("""UPDATE wiki_jp_crawl_jobs SET state='pausing'
                       WHERE id=? AND state IN ('queued','running')""",(ident,))


def resume(db,ident):
    with _LOCK:
        if _RUNNING:
            raise ValueError("A Japanese Wiki crawl is already running")
        with _db(db) as con:
            row=con.execute("SELECT state FROM wiki_jp_crawl_jobs WHERE id=?",(ident,)).fetchone()
            if not row or row[0] not in ("paused","interrupted","error","pausing"):
                raise ValueError("Job is not resumable")
            con.execute("UPDATE wiki_jp_crawl_jobs SET state='queued' WHERE id=?",(ident,))
        _RUNNING.add(ident)
    threading.Thread(target=_worker,args=(str(db),ident),daemon=True).start()


def _save_page(db,title,raw):
    text=jp.to_text(raw)
    if not text.strip():
        raise ValueError("Japanese Wiki article has no readable content")
    digest=hashlib.sha256(text.encode("utf-8")).hexdigest()
    record=("WikiWikiJP",title,title,title,"","",text,digest)
    filename=None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db",prefix="wiki_jp_",delete=False) as handle:
            filename=handle.name
        with sqlite3.connect(filename) as con:
            con.execute(wiki_jobs._PAGES_DDL)
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",record)
        wiki_jobs._merge(str(db),filename,lambda msg:None)
        with sqlite3.connect(str(db),timeout=30) as con:
            page={"page_id":title,"title":title,"page_text":text}
            page_id,fmt,blocks=wiki_document.build_blocks(page,source_format="html",raw_source=raw)
            wiki_document.store_document(con,source_id="WikiWikiJP",page_id=page_id,
                                        source_format=fmt,raw_source=raw,blocks=blocks)
            wiki_document.ensure_title_alias(con,"WikiWikiJP",page_id,title)
    finally:
        if filename and os.path.exists(filename):
            os.unlink(filename)


def _worker(db,ident):
    try:
        with _db(db) as con:
            seed,limit,queue_raw,seen_raw,processed,imported,failed,mode=con.execute(
                """SELECT seed,page_limit,queue_json,seen_json,processed,imported,failed,mode
                   FROM wiki_jp_crawl_jobs WHERE id=?""",(ident,)).fetchone()
        queue=json.loads(queue_raw)
        seen=set(json.loads(seen_raw))
        _update(db,ident,state="running")
        run_target=processed+limit
        while queue and processed<run_target:
            with _db(db) as con:
                state=con.execute("SELECT state FROM wiki_jp_crawl_jobs WHERE id=?",(ident,)).fetchone()[0]
            if state=="pausing":
                _update(db,ident,state="paused")
                return
            title=queue[0]
            if title in seen:
                queue.pop(0)
                _update(db,ident,queue_json=json.dumps(queue,ensure_ascii=False))
                continue
            try:
                raw=jp.get(title)
                _save_page(db,title,raw)
                imported+=1
                if mode == "crawl":
                    for linked in jp.links(raw):
                        if _in_subtree(linked, seed) and linked not in seen and linked not in queue:
                            queue.append(linked)
            except urllib.error.HTTPError as exc:
                # Keep the current page queued and report failed attempts.
                # Challenges/rate limits always require explicit manual resume.
                failed+=1
                _update(db,ident,state="error",failed=failed,
                        last_error=f"{title}: HTTP {exc.code}"[:400])
                return
            except Exception as exc:
                failed+=1
                _update(db,ident,state="error",failed=failed,last_error=f"{title}: {exc}"[:400])
                return
            seen.add(title)
            queue.pop(0)
            processed+=1
            _update(db,ident,processed=processed,imported=imported,
                    queue_json=json.dumps(queue,ensure_ascii=False),
                    seen_json=json.dumps(sorted(seen),ensure_ascii=False),last_error=None)
            if queue:
                time.sleep(4)
        _update(db,ident,state="completed" if not queue else "paused")
    except Exception as exc:
        _update(db,ident,state="error",last_error=str(exc)[:400])
    finally:
        with _LOCK:
            _RUNNING.discard(ident)
