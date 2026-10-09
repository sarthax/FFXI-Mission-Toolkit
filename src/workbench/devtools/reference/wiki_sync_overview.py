"""Unified read-only Wiki synchronization dashboard.

Keep source behavior explicit: BG imports local archives; JP crawls a selected
subtree; FFXIclopedia supports changed-page refresh. No implicit network runs.
"""
from __future__ import annotations
from . import wiki_bulk_jobs, wiki_bg_dump_jobs, wiki_jp_crawl_jobs, wiki_sync_schedule

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
            pending=job.get("pending")
            if source=="FFXIclopedia":
                # Status does not expose pending_json, so avoid asserting
                # a resumable checkpoint when one has not been verified.
                checkpoint="unverified"
            elif source=="BGWiki":
                checkpoint="verify-archive"
            else:
                checkpoint="available" if isinstance(pending,int) and pending>0 else "empty-or-unknown"
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
