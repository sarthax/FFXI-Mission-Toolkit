"""Shared in-process coordination for scheduled Wiki jobs.

Manual imports remain source-specific. Scheduler defers its next tick while
another source is actively using the Wiki cache.
"""
from __future__ import annotations
from . import wiki_bulk_jobs, wiki_bg_dump_jobs, wiki_jp_crawl_jobs

def active_sources():
    active=[]
    for name,module in (("FFXIclopedia",wiki_bulk_jobs),
                        ("BGWiki",wiki_bg_dump_jobs),
                        ("WikiWikiJP",wiki_jp_crawl_jobs)):
        with module._LOCK:
            if module._RUNNING:
                active.append({"source":name,"jobs":sorted(module._RUNNING)})
    return active

def scheduler_can_start():
    running=active_sources()
    return {"allowed":not running,"running":running}
