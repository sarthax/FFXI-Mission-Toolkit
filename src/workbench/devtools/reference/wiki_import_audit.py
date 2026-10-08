"""Read-only coverage audit for structured blocks from an existing Wiki import.

Usage: python -m workbench.devtools.reference.wiki_import_audit /path/to/wiki.db
No network requests, schema mutations, or re-ingestion.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def audit(con: sqlite3.Connection, *, sample_limit: int = 12) -> dict:
    """Summarize actual persisted Wiki blocks, with bounded source-page samples."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_wiki_blocks'").fetchone():
        return {"status": "NO_STRUCTURED_BLOCKS_TABLE", "sources": [], "samples": [], "recovery_candidates": []}
    sources = [
        {"source": source, "pages_with_blocks": pages, "blocks": blocks,
         "template_fields": fields, "degraded_blocks": legacy}
        for source, pages, blocks, fields, legacy in con.execute("""
          SELECT source_id, COUNT(DISTINCT page_id), COUNT(*),
                 SUM(CASE WHEN block_type='template_field' THEN 1 ELSE 0 END),
                 SUM(CASE WHEN block_type='legacy_text' THEN 1 ELSE 0 END)
          FROM reference_wiki_blocks GROUP BY source_id ORDER BY source_id
        """).fetchall()
    ]
    samples = [
        {"source": source, "page_id": page_id, "template_fields": fields,
         "legacy_blocks": legacy, "source_locators": locators}
        for source, page_id, fields, legacy, locators in con.execute("""
          SELECT source_id,page_id,
                 SUM(CASE WHEN block_type='template_field' THEN 1 ELSE 0 END),
                 SUM(CASE WHEN block_type='legacy_text' THEN 1 ELSE 0 END),
                 SUM(CASE WHEN source_locator IS NOT NULL AND source_locator!='' THEN 1 ELSE 0 END)
          FROM reference_wiki_blocks GROUP BY source_id,page_id
          ORDER BY SUM(CASE WHEN block_type='template_field' THEN 1 ELSE 0 END) DESC,
                   source_id,page_id LIMIT ?
        """, (max(0, min(sample_limit, 100)),)).fetchall()
    ]
    # Rank pages which have only flattened legacy content; prioritize Japanese
    # sources for selective recovery without requesting or changing source data.
    recovery_candidates = [
        {"source": source, "page_id": page_id, "legacy_blocks": legacy}
        for source, page_id, legacy in con.execute("""
          SELECT source_id,page_id,COUNT(*)
          FROM reference_wiki_blocks
          GROUP BY source_id,page_id
          HAVING SUM(CASE WHEN block_type='legacy_text' THEN 1 ELSE 0 END)>0
             AND SUM(CASE WHEN block_type NOT IN ('legacy_text') THEN 1 ELSE 0 END)=0
          ORDER BY CASE WHEN source_id='WikiWikiJP' THEN 0 ELSE 1 END,
                   COUNT(*) DESC,source_id,page_id LIMIT ?
        """, (max(0,min(sample_limit,100)),)).fetchall()
    ]
    return {"status": "OK", "sources": sources, "samples": samples,
            "recovery_candidates": recovery_candidates}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path, help="Existing imported Wiki SQLite database")
    parser.add_argument("--samples", type=int, default=12, help="Maximum example pages (0-100)")
    args = parser.parse_args()
    uri = f"file:{args.db.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as con:
        print(json.dumps(audit(con, sample_limit=args.samples), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
