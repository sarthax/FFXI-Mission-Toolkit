#!/usr/bin/env python3
"""Offline scraper for the Japanese FFXI wiki (wikiwiki.jp/ffxi) -> reference_wiki_pages (source WikiWikiJP).

Zero token cost, resumable (INSERT OR REPLACE; --skip-existing). Only plain page URLs are fetched
(robots.txt disallows '?' query URLs), 1 request/4 sec, backoff on 429. HTML is flattened to text with table cells joined by ' | '.
Seeds crawl the subtree under the seed page, plus depth-1 links (NM/mission pages) with --follow.
Usage: py -3 scrape_wikiwiki_jp.py --seed ヴォイドウォッチ --follow --db ffxi_zone_database.db
"""
from __future__ import annotations
import urllib.error, argparse, hashlib, html, re, sqlite3, time, urllib.parse, urllib.request
from datetime import datetime, timezone

from workbench.devtools.reference import wiki_document

SOURCE_ID = "WikiWikiJP"
BASE = "https://wikiwiki.jp/ffxi/"
SKIP = ("::", "RecentChanges", "FINAL FANTASY XI Wiki", "MenuBar", "Menu")

def get(title):
    url = BASE + urllib.parse.quote(title, safe="/")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (offline reference scraper; polite)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def links(page):
    out = []
    for h in re.findall(r'href="/ffxi/([^"#?]*)"', page):
        t = urllib.parse.unquote(h)
        if t and not t.startswith(SKIP) and t not in out: out.append(t)
    return out

def to_text(page):
    m = re.search(r'<div id="body">(.*?)<div id="(?:footer|toolbar|bottom)', page, re.S) or re.search(r'<body.*?>(.*)</body>', page, re.S)
    s = m.group(1) if m else page
    s = re.sub(r'<(script|style|noscript)\b.*?</\1>', '', s, flags=re.S)
    s = re.sub(r'</t[dh]\s*>', ' | ', s); s = re.sub(r'</tr\s*>|<br\s*/?>|</(p|div|li|h\d|ul|table)\s*>', '\n', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    return "\n".join(l.strip() for l in re.sub(r'[ \t　]+', ' ', s).splitlines() if l.strip())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="append", default=[])
    ap.add_argument("--all", action="store_true", help="whole-site BFS crawl from the top page (resumable; use with --skip-existing, --max 0)"); ap.add_argument("--db", required=True)
    ap.add_argument("--follow", action="store_true", help="also fetch depth-1 linked pages outside the subtree")
    ap.add_argument("--max", type=int, default=400); ap.add_argument("--skip-existing", action="store_true")
    a = ap.parse_args()
    if a.all and not a.seed: a.seed = [""]
    if not a.seed: ap.error("give --seed or --all")
    if a.max == 0: a.max = 10**9
    con = sqlite3.connect(a.db)
    have = {r[0] for r in con.execute("SELECT title FROM reference_wiki_pages WHERE source_id=?", (SOURCE_ID,))} if a.skip_existing else set()
    queue, seen, n = [(s, 0) for s in a.seed], set(), 0
    while queue and n < a.max:
        title, depth = queue.pop(0)
        if title in seen: continue
        seen.add(title)
        if title in have and title not in a.seed: continue
        page = None
        for wait in (0, 20, 60, 120):
            time.sleep(wait)
            try: page = get(title); break
            except urllib.error.HTTPError as e:
                if e.code != 429: print("skip", title, e); break
            except Exception as e: print("skip", title, e); break
        if page is None: continue
        text = to_text(page)
        page_id = title
        con.execute("INSERT OR REPLACE INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                    (SOURCE_ID, page_id, title, title, "", datetime.now(timezone.utc).isoformat(), text, hashlib.sha256(text.encode()).hexdigest()))
        _, source_format, blocks = wiki_document.build_blocks(
            {"page_id": page_id, "title": title, "page_text": text},
            source_format="html",
            raw_source=page,
        )
        wiki_document.store_document(
            con,
            source_id=SOURCE_ID,
            page_id=page_id,
            source_format=source_format,
            raw_source=page,
            blocks=blocks,
        )
        wiki_document.ensure_title_alias(con, SOURCE_ID, page_id, title)
        n += 1
        for l in links(page):
            if a.all or any(l.startswith(s) for s in a.seed): queue.append((l, depth))
            elif a.follow and depth == 0: queue.append((l, 1))
        if n % 20 == 0: con.commit(); print(f"  {n} fetched")
        time.sleep(4)
    con.execute("INSERT OR REPLACE INTO reference_wiki_sources VALUES(?,?,?,?,?,?)",
                (SOURCE_ID, "FFXI Wiki (wikiwiki.jp, Japanese)", "https://wikiwiki.jp/ffxi/", "html-crawl",
                 datetime.now(timezone.utc).isoformat(), "Japanese-language scrape; reference-only evidence."))
    con.commit(); con.close(); print(f"done: {n} pages")

if __name__ == "__main__": main()
