"""Restart-resumable, bounded import from a *local* BG Wiki JSONL.GZ snapshot.

No website requests are made here. This complements the online FFXIclopedia
batch runner and retains the original compressed snapshot for portability.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
import uuid
from pathlib import Path

from . import wiki_document, wiki_jobs

_LOCK = threading.Lock()
_RUNNING: set[str] = set()
_DDL = """CREATE TABLE IF NOT EXISTS wiki_bg_dump_jobs(
  id TEXT PRIMARY KEY, state TEXT NOT NULL, dump_path TEXT NOT NULL,
  dump_signature TEXT NOT NULL, page_limit INTEGER NOT NULL,
  cursor INTEGER NOT NULL DEFAULT 0, processed INTEGER NOT NULL DEFAULT 0,
  imported INTEGER NOT NULL DEFAULT 0, skipped INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0, auto_continue INTEGER NOT NULL DEFAULT 0, last_error TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"""


def _db(db):
    con = sqlite3.connect(str(db), timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_DDL)
    columns = {row[1] for row in con.execute("PRAGMA table_info(wiki_bg_dump_jobs)")}
    if "auto_continue" not in columns:
        con.execute("ALTER TABLE wiki_bg_dump_jobs ADD COLUMN auto_continue INTEGER NOT NULL DEFAULT 0")
    con.commit()
    return con


def _signature(path):
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _update(db, job_id, **values):
    if not values:
        return
    with _db(db) as con:
        con.execute(
            "UPDATE wiki_bg_dump_jobs SET " + ",".join(f"{name}=?" for name in values)
            + ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*values.values(), job_id),
        )


def status(db):
    with _db(db) as con:
        # Mark jobs from a previous process as interrupted without changing
        # the status of a currently executing worker.
        if not _RUNNING:
            con.execute("""UPDATE wiki_bg_dump_jobs SET state='interrupted'
                WHERE state IN ('queued','running','pausing')""")
        rows = con.execute("""SELECT id,state,page_limit,cursor,processed,imported,
            skipped,failed,last_error FROM wiki_bg_dump_jobs
            ORDER BY updated_at DESC LIMIT 8""").fetchall()
    names = ("id","state","page_limit","cursor","processed","imported","skipped","failed","last_error")
    return [dict(zip(names, row)) for row in rows]



def dump_refresh_status(db, dump_path):
    """Compare the configured local archive with prior import signatures, offline."""
    path=Path(dump_path).resolve()
    if not path.is_file():
        return {"available":False,"path":str(path),"changed":False,
                "reason":"Local BG dump not found"}
    signature=_signature(path)
    with _db(db) as con:
        latest=con.execute("""SELECT id,state,dump_signature,processed,imported,skipped,
                updated_at FROM wiki_bg_dump_jobs WHERE dump_path=?
                ORDER BY updated_at DESC LIMIT 1""",(str(path),)).fetchone()
        matching=con.execute("""SELECT id,state FROM wiki_bg_dump_jobs
                WHERE dump_path=? AND dump_signature=? ORDER BY updated_at DESC LIMIT 1""",
                (str(path),signature)).fetchone()
    return {"available":True,"path":str(path),"signature":signature,
            "changed":bool(latest and latest[2]!=signature),
            "never_imported":latest is None,
            "latest":dict(zip(("id","state","signature","processed","imported",
                               "skipped","updated_at"),latest)) if latest else None,
            "matching":dict(zip(("id","state"),matching)) if matching else None,
            "reason":("No previous import" if latest is None else
                      "Archive changed since previous import" if latest[2]!=signature
                      else "Archive matches previous import")}

def start(db, dump_path, limit=50, auto_continue=False):
    if limit not in (50, 250):
        raise ValueError("Batch size must be 50 or 250")
    path = Path(dump_path).resolve()
    if not path.is_file():
        raise ValueError(f"BG Wiki dump not found: {path}")
    signature = _signature(path)
    with _LOCK:
        if _RUNNING:
            raise ValueError("A BG dump import is already running")
        job_id = uuid.uuid4().hex[:12]
        with _db(db) as con:
            con.execute("""INSERT INTO wiki_bg_dump_jobs
                (id,state,dump_path,dump_signature,page_limit,auto_continue) VALUES(?,?,?,?,?,?)""",
                (job_id,"queued",str(path),signature,limit,int(bool(auto_continue))))
        _RUNNING.add(job_id)
    threading.Thread(target=_worker,args=(str(db),job_id),daemon=True).start()
    return job_id


def pause(db, job_id):
    with _db(db) as con:
        con.execute("""UPDATE wiki_bg_dump_jobs SET state='pausing'
            WHERE id=? AND state IN ('queued','running')""",(job_id,))


def resume(db, job_id):
    with _LOCK:
        if _RUNNING:
            raise ValueError("A BG dump import is already running")
        with _db(db) as con:
            row=con.execute("SELECT state FROM wiki_bg_dump_jobs WHERE id=?",(job_id,)).fetchone()
            if not row or row[0] not in ("paused","interrupted","error","pausing"):
                raise ValueError("BG dump job is not resumable")
            con.execute("UPDATE wiki_bg_dump_jobs SET state='queued' WHERE id=?",(job_id,))
        _RUNNING.add(job_id)
    threading.Thread(target=_worker,args=(str(db),job_id),daemon=True).start()


def _import_row(db, row):
    title = row["title"]
    text = row["wikitext"]
    page_id = str(row["pageid"])
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    norm = re.sub(r"[^a-z0-9]","",title.lower())
    page = ("BGWiki",page_id,title,norm,str(row.get("revid") or ""),
            row.get("timestamp") or "",text,digest)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(prefix="wiki_bg_batch_",suffix=".db",delete=False) as t:
            temp_name=t.name
        with sqlite3.connect(temp_name) as con:
            con.execute(wiki_jobs._PAGES_DDL)
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",page)
        wiki_jobs._merge(str(db),temp_name,lambda _:None)
        with sqlite3.connect(str(db),timeout=30) as con:
            document={"page_id":page_id,"title":title,"page_text":text}
            parsed_id,source_format,blocks=wiki_document.build_blocks(
                document,source_format="mediawiki",raw_source=text)
            wiki_document.store_document(con,source_id="BGWiki",page_id=parsed_id,
                source_format=source_format,raw_source=text,blocks=blocks)
            wiki_document.ensure_title_alias(con,"BGWiki",parsed_id,title)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _worker(db, job_id):
    try:
        with _db(db) as con:
            path_str,signature,limit,cursor,processed,auto_continue=con.execute(
                """SELECT dump_path,dump_signature,page_limit,cursor,processed,auto_continue
                FROM wiki_bg_dump_jobs WHERE id=?""",(job_id,)).fetchone()
        path=Path(path_str)
        if _signature(path)!=signature:
            raise RuntimeError("BG Wiki dump changed since checkpoint; start a new batch")
        _update(db,job_id,state="running")
        with gzip.open(path,"rt",encoding="utf-8") as stream:
            for index,line in enumerate(stream):
                if index<cursor:
                    continue
                with _db(db) as con:
                    state=con.execute("SELECT state FROM wiki_bg_dump_jobs WHERE id=?",(job_id,)).fetchone()[0]
                if state=="pausing":
                    _update(db,job_id,state="paused")
                    return
                if not auto_continue and processed>=limit:
                    _update(db,job_id,state="completed")
                    return
                # Never progress past a malformed line without recording the failure.
                try:
                    record=json.loads(line)
                    title=record.get("title")
                    text=record.get("wikitext")
                    page_id=record.get("pageid")
                    if not title or not isinstance(text,str) or page_id is None:
                        raise ValueError("Missing title/pageid/wikitext in dump record")
                    with _db(db) as con:
                        exists=con.execute(
                            """SELECT title,norm_title,revision_id,revision_timestamp,page_hash
                            FROM reference_wiki_pages
                            WHERE source_id='BGWiki' AND page_id=?""",(str(page_id),)
                        ).fetchone() if con.execute(
                            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_wiki_pages'"
                        ).fetchone() else None
                    if exists == (
                        title, re.sub(r"[^a-z0-9]", "", title.lower()),
                        str(record.get("revid") or ""), record.get("timestamp") or "",
                        hashlib.sha256(text.encode("utf-8")).hexdigest()
                    ):
                        _update(db,job_id,skipped=_counter(db,job_id,"skipped")+1)
                    else:
                        _import_row(db,record)
                        _update(db,job_id,imported=_counter(db,job_id,"imported")+1)
                except Exception as exc:
                    _update(db,job_id,failed=_counter(db,job_id,"failed")+1,
                            last_error=f"Record {index+1}: {exc}"[:400])
                processed+=1
                _update(db,job_id,cursor=index+1,processed=processed)
        _update(db,job_id,state="completed")
    except Exception as exc:
        _update(db,job_id,state="error",last_error=str(exc)[:400])
    finally:
        with _LOCK:
            _RUNNING.discard(job_id)


def _counter(db,job_id,column):
    if column not in ("skipped","imported","failed"):
        raise ValueError("Unsupported counter")
    with _db(db) as con:
        return con.execute(f"SELECT {column} FROM wiki_bg_dump_jobs WHERE id=?",(job_id,)).fetchone()[0]
