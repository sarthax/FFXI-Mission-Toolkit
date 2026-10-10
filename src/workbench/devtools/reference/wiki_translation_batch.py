"""Resumable, explicitly started local translation of already cached JP wiki pages.

No scraping or automatic startup. Checkpoints are stored in the Wiki SQLite DB.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path

from . import wiki_document, wiki_ollama_translate, wiki_translation_cache

_LOCK = threading.Lock()
_RUNNING: set[str] = set()
_CANCEL: set[str] = set()
DDL = """CREATE TABLE IF NOT EXISTS reference_wiki_translation_jobs (
 id TEXT PRIMARY KEY, state TEXT NOT NULL, model TEXT NOT NULL,
 pending_json TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
 failed INTEGER NOT NULL DEFAULT 0, failures_json TEXT NOT NULL DEFAULT '[]',
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""


def _connect(db):
    con = sqlite3.connect(str(db), timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(DDL)
    con.commit()
    return con


def _update(db, job_id, **values):
    allowed = {"state", "pending_json", "completed", "failed", "failures_json"}
    if not values.keys() <= allowed:
        raise ValueError("Unexpected status field")
    with _connect(db) as con:
        con.execute("UPDATE reference_wiki_translation_jobs SET " +
                    ",".join(k + "=?" for k in values) +
                    ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (*values.values(), job_id))


def start(db, *, limit=10, retry_job=None):
    if limit not in (10, 50):
        raise ValueError("Batch translation limit must be 10 or 50")
    model = wiki_ollama_translate.configured_model()
    if not model:
        raise ValueError("Configure WIKI_TRANSLATE_OLLAMA_MODEL before starting")
    with _LOCK:
        if _RUNNING:
            raise ValueError("A translation batch is already running")
        with _connect(db) as con:
            if retry_job:
                row = con.execute("SELECT model,failures_json,state FROM reference_wiki_translation_jobs WHERE id=?",
                                  (retry_job,)).fetchone()
                if not row or row[2] not in {"finished", "cancelled", "interrupted"} or row[0] != model:
                    raise ValueError("Retry requires an existing stopped job and matching model")
                pending = json.loads(row[1])[:limit]
            else:
                if not con.execute("SELECT 1 FROM sqlite_master WHERE name='reference_wiki_pages'").fetchone():
                    raise ValueError("No cached Wiki pages table")
                pending = [[str(pid),str(title)] for pid,title in con.execute(
                    "SELECT page_id,title FROM reference_wiki_pages WHERE source_id='WikiWikiJP' ORDER BY title LIMIT ?",
                    (limit,)).fetchall()]
            if not pending:
                raise ValueError("No cached JP pages selected")
            job_id = uuid.uuid4().hex[:12]
            con.execute("INSERT INTO reference_wiki_translation_jobs(id,state,model,pending_json) VALUES(?,?,?,?)",
                        (job_id, "queued", model, json.dumps(pending,ensure_ascii=False)))
        _RUNNING.add(job_id)
        threading.Thread(target=_run,args=(str(db),job_id,model),daemon=True).start()
        return job_id


def _run(db, job_id, model):
    try:
        _update(db,job_id,state="running")
        with _connect(db) as con:
            remaining = json.loads(con.execute("SELECT pending_json FROM reference_wiki_translation_jobs WHERE id=?",(job_id,)).fetchone()[0])
        completed, failures = 0, []
        for idx, (page_id, title) in enumerate(remaining):
            if job_id in _CANCEL:
                _update(db,job_id,state="cancelled")
                return
            try:
                with _connect(db) as con:
                    blocks = wiki_document.stored_blocks(con,"WikiWikiJP",page_id)
                    if not blocks:
                        raise ValueError("No structured article blocks for " + title)
                    result = wiki_translation_cache.translate_cached_blocks(
                        con,source_id="WikiWikiJP",page_id=page_id,blocks=blocks,model=model)
                    if result["status"] != "OK":
                        raise ValueError(result.get("error", "Unknown translation failure"))
                completed += 1
            except Exception as exc:
                failures.append([page_id,title])
            _update(db,job_id,pending_json=json.dumps(remaining[idx+1:],ensure_ascii=False),
                    completed=completed,failed=len(failures),failures_json=json.dumps(failures,ensure_ascii=False))
        _update(db,job_id,state="finished")
    except Exception:
        _update(db,job_id,state="interrupted")
    finally:
        with _LOCK:
            _RUNNING.discard(job_id)
            _CANCEL.discard(job_id)


def cancel(job_id):
    with _LOCK:
        if job_id not in _RUNNING:
            return False
        _CANCEL.add(job_id)
        return True


def status(db):
    with _connect(db) as con:
        # Jobs abandoned by a previous process are never silently restarted.
        with _LOCK:
            active = set(_RUNNING)
        for ident, in con.execute("SELECT id FROM reference_wiki_translation_jobs WHERE state IN ('queued','running')"):
            if ident not in active:
                con.execute("UPDATE reference_wiki_translation_jobs SET state='interrupted' WHERE id=?",(ident,))
        rows=con.execute("""SELECT id,state,model,pending_json,completed,failed,failures_json,updated_at
                            FROM reference_wiki_translation_jobs ORDER BY updated_at DESC LIMIT 10""").fetchall()
    return [{"id":r[0],"state":r[1],"model":r[2],"remaining":len(json.loads(r[3])),
             "completed":r[4],"failed":r[5],"failures":json.loads(r[6]),"updated_at":r[7]} for r in rows]
