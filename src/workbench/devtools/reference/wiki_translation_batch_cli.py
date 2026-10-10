"""CLI for explicit local batch translation of cached WikiWikiJP pages.

Usage:
 python -m workbench.devtools.reference.wiki_translation_batch_cli wiki.db start --limit 10
 python -m workbench.devtools.reference.wiki_translation_batch_cli wiki.db status
 python -m workbench.devtools.reference.wiki_translation_batch_cli wiki.db retry JOB_ID
 python -m workbench.devtools.reference.wiki_translation_batch_cli wiki.db cancel JOB_ID

Note: batch threads live in the hosting process. Use the toolkit service for
long-running execution; a one-shot CLI process cannot host detached batches.
"""
from __future__ import annotations
import argparse
import json
import time
from . import wiki_translation_batch as batch


def main():
    parser=argparse.ArgumentParser(description="Local-only WikiWikiJP translation batch")
    parser.add_argument("db")
    parser.add_argument("action",choices=("start","status","retry","cancel"))
    parser.add_argument("job_id",nargs="?")
    parser.add_argument("--limit",type=int,default=10,choices=(10,50))
    args=parser.parse_args()
    if args.action=="status":
        print(json.dumps(batch.status(args.db),ensure_ascii=False,indent=2))
    elif args.action=="cancel":
        if not args.job_id: parser.error("cancel needs JOB_ID")
        print(json.dumps({"cancel_requested":batch.cancel(args.job_id)}))
    else:
        if args.action=="retry" and not args.job_id: parser.error("retry needs JOB_ID")
        job=batch.start(args.db,limit=args.limit,retry_job=args.job_id if args.action=="retry" else None)
        print("Started",job)
        while True:
            current=next((r for r in batch.status(args.db) if r["id"]==job),None)
            if not current or current["state"] in ("finished","cancelled","interrupted"):
                print(json.dumps(current,ensure_ascii=False,indent=2));break
            time.sleep(.5)


if __name__=="__main__":
    main()
