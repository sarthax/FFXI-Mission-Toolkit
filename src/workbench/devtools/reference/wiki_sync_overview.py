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
        return {"source":source,"capability":capability,"latest":current,
                "active":active,"attention":attention[:5],"recent":jobs}
    return {
        "sources":[
            dict(summarize("FFXIclopedia","recent-changes-api",ffx),
                 schedule=schedule,history=history["last_success"]),
            dict(summarize("BGWiki","local-compressed-dump",bg),
                 schedule=None,history=None),
            dict(summarize("WikiWikiJP","targeted-subtree-crawl",jp),
                 schedule=None,history=None)
        ],
        "notice":"Only FFXIclopedia supports scheduled changed-page refresh. "
                 "BG Wiki uses a local dump; Japanese Wiki requires a targeted crawl."
    }
