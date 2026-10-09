"""Unified read-only Wiki synchronization dashboard.

Keep source behavior explicit: BG imports local archives; JP crawls a selected
subtree; FFXIclopedia supports changed-page refresh. No implicit network runs.
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from . import wiki_bulk_jobs, wiki_bg_dump_jobs, wiki_jp_crawl_jobs, wiki_sync_schedule

def _verified_checkpoint(db, source, job_id):
    """Inspect persisted queue metadata without launching a worker or fetching pages."""
    table={"FFXIclopedia":"wiki_bulk_jobs","BGWiki":"wiki_bg_dump_jobs",
           "WikiWikiJP":"wiki_jp_crawl_jobs"}[source]
    try:
        with sqlite3.connect(str(db),timeout=5) as con:
            if source=="BGWiki":
                row=con.execute(
                    "SELECT dump_path,dump_signature FROM wiki_bg_dump_jobs WHERE id=?",
                    (job_id,)).fetchone()
                if not row:
                    return "verify-archive"
                path=Path(row[0])
                if not path.is_file():
                    return "archive-missing"
                stat=path.stat()
                return ("available" if f"{stat.st_size}:{stat.st_mtime_ns}"==row[1]
                        else "archive-changed")
            field="pending_json" if source=="FFXIclopedia" else "queue_json"
            row=con.execute(f"SELECT {field} FROM {table} WHERE id=?",(job_id,)).fetchone()
            if row is None:
                return "unverified"
            values=json.loads(row[0])
            if not isinstance(values,list) or not all(isinstance(x,str) for x in values):
                return "invalid-checkpoint"
            return "available" if values else "empty-checkpoint"
    except (sqlite3.Error,OSError,ValueError,TypeError):
        return "unverified"


def overview(db):
    ffx=wiki_bulk_jobs.status(db)
    bg=wiki_bg_dump_jobs.status(db)
    jp=wiki_jp_crawl_jobs.status(db)
    schedule=wiki_sync_schedule.settings(db)
    history=wiki_bulk_jobs.sync_summary(db)
    def summarize(source,capability,jobs):
        current=jobs[0] if jobs else None
        active=next((job for job in jobs if job.get("state") in
                     ("queued","running","discovering","pausing")),None)
        attention=[{"id":job["id"],"state":job["state"],
                    "error":job.get("last_error")}
                   for job in jobs if job.get("state") in
                   ("error","interrupted","paused")]
        # An interrupted/paused/error job is an operator action, not a
        # successful synchronization. Expose conservative recovery hints.
        recovery=[]
        for job in jobs:
            state=job.get("state")
            if state not in ("error","interrupted","paused"):
                continue
            checkpoint=_verified_checkpoint(db,source,job["id"])
            # Older test stubs and legacy installations may expose only
            # status metadata; never infer a verified checkpoint from them.
            if checkpoint=="unverified" and source=="BGWiki":
                checkpoint="verify-archive"
            if checkpoint=="unverified" and source=="WikiWikiJP":
                pending=job.get("pending")
                checkpoint=("available" if isinstance(pending,int) and pending>0
                            else "empty-or-unknown")
            recovery.append({"id":job["id"],"state":state,
                             "checkpoint":checkpoint,"error":job.get("last_error")})
        return {"source":source,"capability":capability,"latest":current,
                "active":active,"attention":attention[:5],
                "recovery":recovery[:5],"needs_attention":bool(attention),
                "recent":jobs}
    return {
        "sources":[
            dict(summarize("FFXIclopedia","recent-changes-api",ffx),
                 schedule=schedule,history=history["last_success"]),
            dict(summarize("BGWiki","local-compressed-dump",bg),
                 schedule=None,history=None),
            dict(summarize("WikiWikiJP","targeted-subtree-crawl",jp),
                 schedule=None,history=None)
        ],
        "notice":"BG Wiki imports a local archive; FFXIclopedia supports changed-page refresh. "
                 "Japanese Wiki supports bounded targeted crawl and cached-page refresh. "
                 "Recoveries and any scheduling remain source-specific and opt-in."
    }
