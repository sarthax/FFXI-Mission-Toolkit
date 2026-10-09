#!/usr/bin/env python3
"""Synchronize the offline BG Wiki JSONL dump used by reference tooling."""
from __future__ import annotations

import argparse
import gzip
import json
import time
import urllib.parse
import urllib.request

from workbench.runtime.paths import VENDOR_ROOT

DUMP_PATH = VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"
API_URL = "https://www.bg-wiki.com/api.php"
USER_AGENT = "mission-toolkit-bgwiki-sync/1.0 (local FFXI/Topaz private-server toolkit; incremental sync bot)"
CRAWL_DELAY_SECONDS = 30
BATCH_SIZE = 50


def _api_get(params: dict) -> dict:
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise RuntimeError("BG Wiki API returned a non-object response")
        if data.get("error"):
            raise RuntimeError("BG Wiki API error: " + str(data["error"])[:400])
        return data


def _page_to_row(page: dict) -> dict | None:
    revisions = page.get("revisions") or []
    if not revisions:
        return None
    rev = revisions[0]
    title = page["title"]
    categories = [c["title"].removeprefix("Category:") for c in (page.get("categories") or [])]
    wikitext = rev.get("content")
    if wikitext is None:
        wikitext = (rev.get("slots") or {}).get("main", {}).get("content")
    if wikitext is None:
        raise RuntimeError(f"BG Wiki revision content unavailable for {title}: check API slot/content permissions")
    return {
        "title": title,
        "pageid": page["pageid"],
        "ns": page["ns"],
        "url": f"https://www.bg-wiki.com/ffxi/{urllib.parse.quote(title.replace(' ', '_'))}",
        "revid": rev.get("revid"),
        "timestamp": rev.get("timestamp"),
        "categories": categories,
        "wikitext": wikitext,
    }


def fetch_all_pages(limit: int | None = None):
    gapcontinue = None
    fetched = 0
    while True:
        params = {
            "action": "query",
            "generator": "allpages",
            "gapnamespace": 0,
            "gaplimit": BATCH_SIZE,
            "prop": "revisions|categories",
            "rvprop": "content|timestamp|ids",
            "rvslots": "main",
            "formatversion": 2,
            "format": "json",
        }
        if gapcontinue:
            params["gapcontinue"] = gapcontinue
        data = _api_get(params)
        for page in data.get("query", {}).get("pages", []):
            row = _page_to_row(page)
            if row:
                yield row
                fetched += 1
                if limit and fetched >= limit:
                    return
        cont = data.get("continue")
        if not cont:
            return
        gapcontinue = cont.get("gapcontinue")
        time.sleep(CRAWL_DELAY_SECONDS)


def fetch_pages_by_title(titles: list[str]):
    for i in range(0, len(titles), BATCH_SIZE):
        chunk = titles[i:i + BATCH_SIZE]
        data = _api_get({
            "action": "query",
            "titles": "|".join(chunk),
            "prop": "revisions|categories",
            "rvprop": "content|timestamp|ids",
            "rvslots": "main",
            "formatversion": 2,
            "format": "json",
        })
        for page in data.get("query", {}).get("pages", []):
            row = _page_to_row(page)
            if row:
                yield row
        if i + BATCH_SIZE < len(titles):
            time.sleep(CRAWL_DELAY_SECONDS)


def fetch_changed_titles_since(since_timestamp: str) -> list[str]:
    titles: list[str] = []
    rccontinue = None
    while True:
        params = {
            "action": "query",
            "list": "recentchanges",
            "rcnamespace": 0,
            "rcstart": since_timestamp,
            "rcdir": "newer",
            "rcprop": "title|timestamp",
            "rclimit": 500,
            "format": "json",
            "formatversion": 2,
        }
        if rccontinue:
            params["rccontinue"] = rccontinue
        data = _api_get(params)
        for change in data.get("query", {}).get("recentchanges", []):
            titles.append(change["title"])
        cont = data.get("continue")
        if not cont:
            break
        rccontinue = cont.get("rccontinue")
        time.sleep(CRAWL_DELAY_SECONDS)
    seen = set()
    return [t for t in titles if not (t in seen or seen.add(t))]


def load_existing_dump() -> dict[str, dict]:
    if not DUMP_PATH.exists():
        return {}
    rows = {}
    with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            rows[row["title"]] = row
    return rows


def write_dump(rows: dict[str, dict]):
    DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = DUMP_PATH.with_suffix(".tmp")
    with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
        for row in rows.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp_path.replace(DUMP_PATH)


def run_full(limit: int | None) -> int:
    rows: dict[str, dict] = {}
    for i, row in enumerate(fetch_all_pages(limit=limit), 1):
        rows[row["title"]] = row
        if i % 50 == 0:
            print(f"  ...{i} pages fetched")
    write_dump(rows)
    print(f"Full crawl complete: {len(rows)} pages written to {DUMP_PATH}")
    return len(rows)


def run_incremental(limit: int | None) -> tuple[int, int]:
    existing = load_existing_dump()
    if not existing:
        print("No existing dump found -- incremental mode needs a base dump. Run with --full first.")
        return 0, 0
    newest_timestamp = max(row["timestamp"] for row in existing.values() if row.get("timestamp"))
    print(f"Existing dump: {len(existing)} pages, newest known edit at {newest_timestamp}")
    changed_titles = fetch_changed_titles_since(newest_timestamp)
    if limit:
        changed_titles = changed_titles[:limit]
    print(f"{len(changed_titles)} page(s) changed since then")
    if not changed_titles:
        return len(existing), 0
    updated = 0
    for row in fetch_pages_by_title(changed_titles):
        existing[row["title"]] = row
        updated += 1
    write_dump(existing)
    print(f"Incremental sync complete: {updated} page(s) updated, {len(existing)} total in dump")
    return len(existing), updated


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="full crawl from scratch (slow, ~8 hours for the whole wiki)")
    ap.add_argument("--limit", type=int, default=None, help="cap pages processed this run (for testing)")
    args = ap.parse_args()
    if args.full:
        run_full(args.limit)
    else:
        run_incremental(args.limit)


if __name__ == "__main__":
    main()
