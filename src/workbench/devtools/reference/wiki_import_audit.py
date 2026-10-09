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
    # Inspect only locally retained source text. A usable raw document can be
    # reparsed offline; missing/flattened originals require selective recovery.
    has_documents = bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_wiki_documents'"
    ).fetchone())
    for page in recovery_candidates:
        row = con.execute("""
          SELECT source_format,raw_source FROM reference_wiki_documents
          WHERE source_id=? AND page_id=?
        """, (page["source"],page["page_id"])).fetchone() if has_documents else None
        format_name = str(row[0] or "").lower() if row else ""
        usable = bool(row and row[1] and str(row[1]).strip()
                      and format_name in {"mediawiki","html"})
        page["recovery_action"] = "REPARSE_LOCAL_SOURCE" if usable else "SELECTIVE_SOURCE_FETCH"
        page["source_format"] = format_name or None
    return {"status": "OK", "sources": sources, "samples": samples,
            "recovery_candidates": recovery_candidates}



def preview_local_recovery(con: sqlite3.Connection, *, sample_limit: int = 12) -> list[dict]:
    """Parse retained source without storing blocks or changing imported records."""
    from workbench.devtools.reference.wiki_document import build_blocks
    candidates=audit(con,sample_limit=sample_limit).get("recovery_candidates",[])
    previews=[]
    for page in candidates:
        if page["recovery_action"]!="REPARSE_LOCAL_SOURCE":
            continue
        row=con.execute("""
          SELECT source_format,raw_source FROM reference_wiki_documents
          WHERE source_id=? AND page_id=?
        """,(page["source"],page["page_id"])).fetchone()
        if not row:
            continue
        source_format,raw_source=row
        _,_,blocks=build_blocks({"page_id":page["page_id"]},
                                 source_format=source_format,raw_source=raw_source)
        counts={}
        for block in blocks:
            kind=block.get("block_type") or "unknown"
            counts[kind]=counts.get(kind,0)+1
        previews.append({"source":page["source"],"page_id":page["page_id"],
                         "existing_legacy_blocks":page["legacy_blocks"],
                         "preview_block_count":len(blocks),
                         "preview_block_types":counts,
                         "requires_confirmation":True,
                         "applied":False})
    return previews



def apply_local_recovery(con: sqlite3.Connection, *, source: str, page_id: str,
                         expected_raw_hash: str, confirm: bool = False) -> dict:
    """Apply one local-source reparse; reject stale/unsafe/unpreviewed requests."""
    import hashlib
    from workbench.devtools.reference import wiki_document
    if not confirm or not source or not page_id or not expected_raw_hash:
        raise ValueError("Explicit confirmation, source, page ID and source hash required")
    con.execute("BEGIN IMMEDIATE")
    try:
        row=con.execute("""SELECT source_format,raw_source FROM reference_wiki_documents
                            WHERE source_id=? AND page_id=?""",(source,page_id)).fetchone()
        if not row or row[0] not in {"mediawiki","html"} or not row[1]:
            raise ValueError("Retained structured source unavailable")
        if hashlib.sha256(row[1].encode("utf-8")).hexdigest()!=expected_raw_hash:
            raise ValueError("Source changed since preview")
        counts=con.execute("""SELECT block_type,COUNT(*) FROM reference_wiki_blocks
                              WHERE source_id=? AND page_id=? GROUP BY block_type""",
                           (source,page_id)).fetchall()
        if not counts or any(kind!="legacy_text" for kind,_ in counts):
            raise ValueError("Page no longer contains exclusively legacy blocks")
        _,_,blocks=wiki_document.build_blocks({"page_id":page_id},
            source_format=row[0],raw_source=row[1])
        if not blocks or all(b.get("block_type")=="legacy_text" for b in blocks):
            raise ValueError("Preview produced no structured recovery")
        wiki_document.store_document(con,source_id=source,page_id=page_id,
            source_format=row[0],raw_source=row[1],blocks=blocks)
        con.commit()
        return {"source":source,"page_id":page_id,"applied":True,"blocks":len(blocks)}
    except Exception:
        con.rollback()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", type=Path, help="Existing imported Wiki SQLite database")
    parser.add_argument("--samples", type=int, default=12, help="Maximum example pages (0-100)")
    parser.add_argument("--preview-local", action="store_true", help="Preview reparsing local retained source; never write")
    parser.add_argument("--apply-source", help="Source ID of one page to recover")
    parser.add_argument("--apply-page", help="Page ID of one page to recover")
    parser.add_argument("--expect-hash", help="SHA256 of retained original source from preview")
    parser.add_argument("--confirm-local-recovery", action="store_true", help="Explicit single-page write authorization")
    args = parser.parse_args()
    applying=any((args.apply_source,args.apply_page,args.expect_hash,args.confirm_local_recovery))
    if applying and not all((args.apply_source,args.apply_page,args.expect_hash,args.confirm_local_recovery)):
        parser.error("Apply requires --apply-source --apply-page --expect-hash --confirm-local-recovery")
    uri = f"file:{args.db.resolve().as_posix()}?mode={'rw' if applying else 'ro'}"
    with sqlite3.connect(uri, uri=True) as con:
        if applying:
            result=apply_local_recovery(con,source=args.apply_source,page_id=args.apply_page,
                                        expected_raw_hash=args.expect_hash,confirm=True)
        else:
            result=audit(con, sample_limit=args.samples)
            if args.preview_local:
                result["local_recovery_previews"]=preview_local_recovery(con,sample_limit=args.samples)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
