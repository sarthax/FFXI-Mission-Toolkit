#!/usr/bin/env python3
"""Offline-runnable FFXIclopedia scraper (MediaWiki API) -> reference_wiki_pages (source_id FFXIclopedia).

Same tables as ffxiclopedia.py's XML import, so existing evidence/compare tools read it unchanged.
Zero token cost: run it unattended. Resumable (INSERT OR REPLACE by page id; --skip-existing to
avoid refetching), polite delay, recursive subcategories.

  py -3 scrape_ffxiclopedia.py --preset voidwatch          # Voidwatch NMs/quests/KIs/NPCs/rewards
  py -3 scrape_ffxiclopedia.py --category "Notorious Monsters" --category Bestiary
  py -3 scrape_ffxiclopedia.py --all                        # every main-namespace page (long)
  py -3 scrape_ffxiclopedia.py --changed                    # incremental: pages edited since last run
"""
from __future__ import annotations
import argparse, hashlib, json, sqlite3, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
try:
    from .ffxiclopedia import SOURCE_ID, SOURCE_URL, norm_title, init_db
except ImportError:
    from ffxiclopedia import SOURCE_ID, SOURCE_URL, norm_title, init_db

API = "https://ffxiclopedia.fandom.com/api.php"
UA = "mission-toolkit-ffxiclopedia-sync/1.0 (local FFXI private-server toolkit; polite incremental bot)"
DELAY = 1.5
PRESETS = {
    "voidwatch": ["Voidwatch", "Voidwatch Notorious Monsters", "Voidwatch Quests", "Voidwatch Key Items",
                  "Voidwatch NPCs", "Voidwatch Rewards", "Stratum Abyssite", "Periapt", "Atmacite"],
}

def api(**p):
    p["format"] = "json"
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(p), headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(DELAY)
            return data
        except Exception as e:
            print(f"  api retry {attempt+1}: {e}", file=sys.stderr); time.sleep(5 * (attempt + 1))
    raise RuntimeError("API failed")

def paged(**p):
    cont = {}
    while True:
        r = api(**p, **cont)
        yield r
        if "continue" not in r: return
        cont = r["continue"]

def category_pages(cat, seen):
    """Titles (ns 0) in a category, recursing into subcategories."""
    if cat in seen: return
    seen.add(cat)
    for r in paged(action="query", list="categorymembers", cmtitle="Category:" + cat, cmlimit="500"):
        for m in r["query"]["categorymembers"]:
            if m["ns"] == 14: yield from category_pages(m["title"].removeprefix("Category:"), seen)
            elif m["ns"] == 0: yield m["title"]

def all_titles():
    for r in paged(action="query", list="allpages", apnamespace="0", aplimit="500", apfilterredir="nonredirects"):
        for m in r["query"]["allpages"]: yield m["title"]

def fetch(titles):
    for i in range(0, len(titles), 40):
        r = api(action="query", prop="revisions", rvprop="content|ids|timestamp", rvslots="main",
                titles="|".join(titles[i:i+40]))
        for pg in r["query"]["pages"].values():
            rev = (pg.get("revisions") or [None])[0]
            if rev: yield pg["pageid"], pg["title"], rev.get("revid"), rev.get("timestamp"), rev["slots"]["main"]["*"]

def changed_titles(con):
    since = con.execute("SELECT MAX(revision_timestamp) FROM reference_wiki_pages WHERE source_id=?", (SOURCE_ID,)).fetchone()[0]
    if not since: sys.exit("no existing data; run a category/--all crawl first")
    seen = set()
    for r in paged(action="query", list="recentchanges", rcnamespace="0", rcend=since, rclimit="500", rcprop="title"):
        for m in r["query"]["recentchanges"]:
            if m["title"] not in seen: seen.add(m["title"]); yield m["title"]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=Path("ffxi_zone_database.db"))
    ap.add_argument("--category", action="append", default=[])
    ap.add_argument("--preset", choices=PRESETS)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--changed", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    con = sqlite3.connect(a.db); init_db(con)
    if a.changed: titles = list(changed_titles(con))
    elif a.all: titles = list(all_titles())
    else:
        cats = a.category + (PRESETS[a.preset] if a.preset else [])
        if not cats: ap.error("give --preset, --category, --all or --changed")
        seen, titles = set(), []
        for c in cats:
            for t in category_pages(c, seen):
                if t not in titles: titles.append(t)
    if a.skip_existing:
        have = {r[0] for r in con.execute("SELECT title FROM reference_wiki_pages WHERE source_id=?", (SOURCE_ID,))}
        titles = [t for t in titles if t not in have]
    if a.limit: titles = titles[:a.limit]
    print(f"{len(titles)} page(s) to fetch")
    n = 0
    for pid, title, revid, ts, text in fetch(titles):
        con.execute("INSERT OR REPLACE INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                    (SOURCE_ID, str(pid), title, norm_title(title), str(revid), ts, text,
                     hashlib.sha256(text.encode("utf-8")).hexdigest()))
        n += 1
        if n % 40 == 0: con.commit(); print(f"  {n}/{len(titles)}")
    con.execute("INSERT OR REPLACE INTO reference_wiki_sources VALUES(?,?,?,?,?,?)",
                (SOURCE_ID, "FFXIclopedia", SOURCE_URL, "api-sync", datetime.now(timezone.utc).isoformat(),
                 "MediaWiki API scrape; reference-only evidence."))
    con.commit(); con.close(); print(f"done: {n} pages stored in {a.db}")

if __name__ == "__main__": main()
