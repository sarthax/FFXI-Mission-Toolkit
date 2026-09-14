#!/usr/bin/env python3
"""
build_wiki_index.py -- Mission Toolkit GUI, wiki reverse-reference index.

Walks the entire BG Wiki dump ONCE (47,606 real pages), extracting every real [[wikilink]] and
{{Item Tooltip}} reference per page (reusing wiki_compile.py's own extractor, not a second
implementation), into a persisted wiki_entity_refs table (norm_name -> page_title/url). This is
what entity_profile.py's get_wiki_references() reads -- a live full-dump scan per profile lookup
would be far too slow (mwparserfromhell parsing isn't free across 47k pages); this indexes once,
the same index-then-query pattern used by every other build_*.py tool in this toolkit.

Usage:
    py -3 build_wiki_index.py
"""
import gzip
import io
import json
import re
import sqlite3
import sys
from pathlib import Path

import wiki_compile

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
DUMP_PATH = TOOLS_ROOT / "ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz"


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


# CatsEyeXI is a different private server with its own custom content documented on the same
# BG Wiki dump under this category -- not retail, not applicable to Topaz/DSP. Excluded at
# ingestion so it never enters the index rather than being filtered per-query later.
EXCLUDED_CATEGORIES = {"catseyexi"}


def is_excluded(page: dict) -> bool:
    return any(c.lower() in EXCLUDED_CATEGORIES for c in page.get("categories", []))


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS wiki_entity_refs (
            norm_name TEXT,
            page_title TEXT,
            page_url TEXT,
            PRIMARY KEY (norm_name, page_title)
        );
        CREATE INDEX IF NOT EXISTS idx_wiki_refs_norm ON wiki_entity_refs(norm_name);
        CREATE TABLE IF NOT EXISTS wiki_pages (
            norm_title TEXT PRIMARY KEY,
            title TEXT,
            url TEXT
        );
    """)
    con.commit()


def build_index(con: sqlite3.Connection, progress_every: int = 5000) -> int:
    if not DUMP_PATH.exists():
        raise SystemExit(f"{DUMP_PATH} not found.")
    init_db(con)
    con.execute("DELETE FROM wiki_entity_refs")
    con.execute("DELETE FROM wiki_pages")

    # wiki_pages: one row per real page, keyed by the page's OWN (normalized) title. This is the
    # piece the original single-table design was missing -- wiki_entity_refs only captures pages
    # that [[link to]] a name, and a page about "Jaggedy-Eared Jack" typically never wikilinks to
    # its own title, so the canonical article was invisible to get_wiki_references() while an
    # incidental listing page (e.g. "Hunts/Home Nations", which does link to it) surfaced instead.
    # Found live 2026-09-03 by the user spot-checking a real entity lookup.
    ref_rows = []
    page_rows = []
    n = 0
    with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            n += 1
            if is_excluded(p):
                continue
            page_rows.append((normalize(p["title"]), p["title"], p["url"]))
            try:
                names = wiki_compile.extract_entity_links(p["wikitext"])
            except Exception:
                continue  # a handful of real pages have malformed wikitext -- skip, don't crash the whole build
            for name in names:
                ref_rows.append((normalize(name), p["title"], p["url"]))
            if n % progress_every == 0:
                print(f"  ...{n} pages scanned, {len(ref_rows)} refs so far")
                con.executemany(
                    "INSERT OR REPLACE INTO wiki_entity_refs (norm_name, page_title, page_url) VALUES (?, ?, ?)",
                    ref_rows,
                )
                con.executemany(
                    "INSERT OR REPLACE INTO wiki_pages (norm_title, title, url) VALUES (?, ?, ?)",
                    page_rows,
                )
                ref_rows = []
                page_rows = []
                con.commit()

    if ref_rows or page_rows:
        con.executemany(
            "INSERT OR REPLACE INTO wiki_entity_refs (norm_name, page_title, page_url) VALUES (?, ?, ?)",
            ref_rows,
        )
        con.executemany(
            "INSERT OR REPLACE INTO wiki_pages (norm_title, title, url) VALUES (?, ?, ?)",
            page_rows,
        )
        con.commit()

    total = con.execute("SELECT COUNT(*) FROM wiki_entity_refs").fetchone()[0]
    return total


def main():
    con = sqlite3.connect(DB_PATH)
    print(f"Indexing {DUMP_PATH.name}...")
    total = build_index(con)
    print(f"Done. {total} real entity-reference rows indexed across the whole wiki dump.")
    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
