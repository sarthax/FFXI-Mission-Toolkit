#!/usr/bin/env python3
"""Build the persisted BG Wiki reverse-reference index used by entity research tooling."""
from __future__ import annotations

import gzip
import io
import json
import re
import sqlite3
import sys

from workbench.devtools.reference import wiki_compile
from workbench.runtime.paths import DATABASE_PATH, VENDOR_ROOT

DB_PATH = DATABASE_PATH
DUMP_PATH = VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


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
                continue
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
