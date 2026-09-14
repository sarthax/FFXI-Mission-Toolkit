#!/usr/bin/env python3
"""
scrape_bg_wiki.py -- real automated replacement for the manual "AI model pulls the BG Wiki dump"
step. Talks directly to BG Wiki's own MediaWiki API (confirmed live this session: bg-wiki.com runs
MediaWiki 1.43.9, api.php is real and reachable, robots.txt does not disallow api.php -- only a
handful of index.php query patterns like ?diff=/?action=edit) and writes the exact same
ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz format wiki_lookup.py/wiki_compile.py/build_wiki_index.py
already read (one JSON object per line: title, pageid, ns, url, revid, timestamp, categories,
wikitext) -- confirmed byte-for-byte against the existing bundled dump, so nothing downstream needs
to change.

robots.txt sets `Crawl-Delay: 30` for generic user agents -- honored here as a real sleep between
every HTTP request, using a real, honest, self-identifying User-Agent. At 30s/request and up to 50
pages/request (the real anonymous per-request cap for a combined revisions+categories query,
confirmed live), a FULL crawl of all ~47,600 namespace-0 pages is ~950 requests, ~8 hours -- a real
one-time cost, not something to run casually. Everyday use should be the INCREMENTAL mode instead
(default): reads the existing dump's newest per-page timestamp, asks the wiki's own recentchanges
feed for what's changed since then, and only re-fetches those pages -- typically seconds to a few
minutes.

Usage:
    py -3 scrape_bg_wiki.py                  # incremental: only pages changed since the last dump
    py -3 scrape_bg_wiki.py --full           # full crawl from scratch (slow, see above)
    py -3 scrape_bg_wiki.py --limit 25       # cap pages processed this run (testing)
"""
import argparse
import gzip
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

TOOLS_ROOT = Path(__file__).parent
DUMP_PATH = TOOLS_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"
API_URL = "https://www.bg-wiki.com/api.php"
USER_AGENT = "mission-toolkit-bgwiki-sync/1.0 (local FFXI/Topaz private-server toolkit; incremental sync bot)"
CRAWL_DELAY_SECONDS = 30  # real value from https://www.bg-wiki.com/robots.txt's `User-agent: *` block
BATCH_SIZE = 50  # real per-request cap for an anonymous combined revisions+categories query


def _api_get(params: dict) -> dict:
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _page_to_row(page: dict) -> dict | None:
    """Converts one MediaWiki API page object into this project's real dump row shape -- same
    keys/types as the existing bundled bg-wiki.jsonl.gz, confirmed byte-for-byte this session."""
    revisions = page.get("revisions") or []
    if not revisions:
        return None
    rev = revisions[0]
    title = page["title"]
    categories = [c["title"].removeprefix("Category:") for c in (page.get("categories") or [])]
    return {
        "title": title,
        "pageid": page["pageid"],
        "ns": page["ns"],
        "url": f"https://www.bg-wiki.com/ffxi/{urllib.parse.quote(title.replace(' ', '_'))}",
        "revid": rev.get("revid"),
        "timestamp": rev.get("timestamp"),
        "categories": categories,
        "wikitext": rev.get("content", ""),
    }


def fetch_all_pages(limit: int | None = None):
    """Yields every real namespace-0 (main/article) page via generator=allpages, paginating with
    the API's own gapcontinue token -- a real full crawl, not a guessed page list."""
    gapcontinue = None
    fetched = 0
    while True:
        params = {
            "action": "query", "generator": "allpages", "gapnamespace": 0,
            "gaplimit": BATCH_SIZE, "prop": "revisions|categories",
            "rvprop": "content|timestamp|ids", "formatversion": 2, "format": "json",
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
    """Yields real page rows for an explicit title list, chunked to BATCH_SIZE per request --
    used by incremental mode to re-fetch only what recentchanges says actually changed."""
    for i in range(0, len(titles), BATCH_SIZE):
        chunk = titles[i:i + BATCH_SIZE]
        data = _api_get({
            "action": "query", "titles": "|".join(chunk), "prop": "revisions|categories",
            "rvprop": "content|timestamp|ids", "formatversion": 2, "format": "json",
        })
        for page in data.get("query", {}).get("pages", []):
            row = _page_to_row(page)
            if row:
                yield row
        if i + BATCH_SIZE < len(titles):
            time.sleep(CRAWL_DELAY_SECONDS)


def fetch_changed_titles_since(since_timestamp: str) -> list[str]:
    """Real recentchanges query -- every namespace-0 page edited since since_timestamp, paginated.
    This is what makes incremental sync fast: most runs find zero or a handful of real changes,
    not a full 47,000-page re-crawl."""
    titles: list[str] = []
    rccontinue = None
    while True:
        params = {
            "action": "query", "list": "recentchanges", "rcnamespace": 0,
            "rcstart": since_timestamp, "rcdir": "newer", "rcprop": "title|timestamp",
            "rclimit": 500, "format": "json", "formatversion": 2,
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
    # dedupe, preserving order -- a page edited multiple times since `since` only needs one refetch
    seen = set()
    return [t for t in titles if not (t in seen or seen.add(t))]


def load_existing_dump() -> dict[str, dict]:
    """Returns {title: row} for the current dump, or {} if none exists yet."""
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
