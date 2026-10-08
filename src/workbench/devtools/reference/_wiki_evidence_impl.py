#!/usr/bin/env python3
"""Claim-level wiki evidence and mapping ledger.

Reference pages are evidence, not truth.  This module preserves what a wiki page actually says
(page/revision/section/excerpt/link target) separately from any mapping into toolkit entities.

BG Wiki is read from the existing reproducible JSONL dump.  FFXIclopedia uses the separately
imported reference_wiki_pages table when available.  Automatic mappings are conservative exact
or normalized-name resolutions only; ambiguous and unresolved references remain first-class rows.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import urllib.parse
from pathlib import Path

import mwparserfromhell

import wiki_lookup
import wiki_document

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
BG_DUMP_PATH = TOOLS_ROOT / "vendor" / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"

SOURCE_BG = "BGWiki"
SOURCE_FFXICLOPEDIA = "FFXIclopedia"
SOURCE_WIKIWIKI_JP = "WikiWikiJP"
REFERENCE_ONLY = "REFERENCE_ONLY"

_NON_ENTITY_PREFIXES = ("image:", "file:", "category:", "media:", "template:", "user:", "special:")
WANTED_SECTIONS = {"Walkthrough", "Strategy", "Notes", "Plot Details", "Boss Fight", "Eligibility"}


def title_from_query(raw: str) -> str:
    raw = (raw or "").strip()
    if raw.startswith(("http://", "https://")):
        raw = urllib.parse.urlparse(raw).path.rsplit("/", 1)[-1]
    return urllib.parse.unquote(raw).replace("_", " ").strip()


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def init_db(con: sqlite3.Connection) -> None:
    wiki_document.init_db(con)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS reference_wiki_sources(
          source_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, base_url TEXT NOT NULL,
          snapshot_id TEXT, imported_at TEXT, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS reference_wiki_pages(
          source_id TEXT NOT NULL, page_id TEXT NOT NULL, title TEXT NOT NULL, norm_title TEXT NOT NULL,
          revision_id TEXT, revision_timestamp TEXT, page_text TEXT, page_hash TEXT NOT NULL,
          PRIMARY KEY(source_id,page_id)
        );
        CREATE INDEX IF NOT EXISTS idx_reference_wiki_norm ON reference_wiki_pages(source_id,norm_title);

        CREATE TABLE IF NOT EXISTS reference_wiki_claims(
          claim_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          page_id TEXT NOT NULL,
          page_title TEXT NOT NULL,
          page_url TEXT,
          revision_id TEXT,
          revision_timestamp TEXT,
          section_title TEXT,
          claim_type TEXT NOT NULL,
          subject_text TEXT,
          excerpt TEXT NOT NULL,
          source_locator TEXT,
          authority TEXT NOT NULL DEFAULT 'REFERENCE_ONLY',
          content_hash TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_reference_claim_page
          ON reference_wiki_claims(source_id,page_id,section_title);
        CREATE INDEX IF NOT EXISTS idx_reference_claim_subject
          ON reference_wiki_claims(subject_text);

        CREATE TABLE IF NOT EXISTS reference_wiki_mappings(
          mapping_id TEXT PRIMARY KEY,
          claim_id TEXT NOT NULL,
          target_domain TEXT,
          target_table TEXT,
          target_key TEXT,
          target_label TEXT,
          mapping_method TEXT NOT NULL,
          mapping_status TEXT NOT NULL,
          confidence TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_reference_mapping_claim
          ON reference_wiki_mappings(claim_id);
        CREATE INDEX IF NOT EXISTS idx_reference_mapping_target
          ON reference_wiki_mappings(target_table,target_key);
        CREATE TABLE IF NOT EXISTS reference_wiki_mapping_reviews(
          mapping_id TEXT PRIMARY KEY,
          review_status TEXT NOT NULL,
          notes TEXT,
          reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    con.execute(
        """INSERT OR IGNORE INTO reference_wiki_sources
           (source_id,display_name,base_url,snapshot_id,imported_at,notes)
           VALUES (?,?,?,?,?,?)""",
        (SOURCE_BG, "BG Wiki", "https://www.bg-wiki.com/ffxi/", None, None,
         "Offline BG Wiki dump; reference-only evidence."),
    )
    con.commit()


def _claim_id(source_id: str, page_id: str, section: str, claim_type: str, subject: str, excerpt: str) -> str:
    raw = "|".join([source_id, page_id, section or "", claim_type, subject or "", excerpt])
    return "wiki-claim:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _mapping_id(claim_id: str, table: str | None, key: str | None, status: str) -> str:
    raw = "|".join([claim_id, table or "", key or "", status])
    return "wiki-map:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _section_records(wikitext: str) -> list[tuple[str | None, str]]:
    wt = mwparserfromhell.parse(wikitext)
    sections = wt.get_sections(include_headings=True, flat=True)
    if not sections:
        return [(None, wikitext)]
    result = []
    for section in sections:
        headings = section.filter_headings()
        title = str(headings[0].title).strip() if headings else None
        result.append((title, str(section)))
    return result


def _line_excerpt(section_text: str, target: str) -> str:
    target_lower = target.lower()
    for line in section_text.splitlines():
        if target_lower in line.lower():
            cleaned = wiki_lookup.clean_wikitext(line).strip()
            if cleaned:
                return cleaned[:700]
    cleaned = wiki_lookup.clean_wikitext(section_text).strip()
    return cleaned[:700]


def extract_claims(page: dict, source_id: str = SOURCE_BG) -> list[dict]:
    """Extract explicit MediaWiki entity references plus structured walkthrough/list statements.

    No semantic truth is inferred. ENTITY_REFERENCE means only that the page explicitly linked to
    that title. SECTION_STATEMENT preserves a list/bullet instruction from useful gameplay sections
    as reference prose for later corroboration/mapping.
    """
    wikitext = page.get("wikitext") if "wikitext" in page else page.get("page_text", "")
    page_id = str(page.get("pageid") or page.get("page_id") or page.get("title"))
    title = page.get("title") or ""
    revision_id = str(page.get("revid") or page.get("revision_id") or "") or None
    revision_ts = page.get("timestamp") or page.get("revision_timestamp")
    page_url = page.get("url")
    claims = []
    seen = set()

    for section_title, section_text in _section_records(wikitext or ""):
        parsed = mwparserfromhell.parse(section_text)
        for link in parsed.filter_wikilinks():
            target = str(link.title).split("#", 1)[0].strip()
            if not target or target.lower().startswith(_NON_ENTITY_PREFIXES):
                continue
            excerpt = _line_excerpt(section_text, target)
            key = ("ENTITY_REFERENCE", section_title, target.lower(), excerpt)
            if key in seen:
                continue
            seen.add(key)
            claims.append({
                "claim_id": _claim_id(source_id, page_id, section_title or "", "ENTITY_REFERENCE", target, excerpt),
                "source_id": source_id,
                "page_id": page_id,
                "page_title": title,
                "page_url": page_url,
                "revision_id": revision_id,
                "revision_timestamp": revision_ts,
                "section_title": section_title,
                "claim_type": "ENTITY_REFERENCE",
                "subject_text": target,
                "excerpt": excerpt or target,
                "source_locator": f"section:{section_title}" if section_title else "page",
                "authority": REFERENCE_ONLY,
            })

        if section_title in WANTED_SECTIONS:
            for raw_line in section_text.splitlines():
                stripped = raw_line.strip()
                if not stripped.startswith(("*", "#")):
                    continue
                cleaned = wiki_lookup.clean_wikitext(stripped.lstrip("*#;: ")).strip()
                if len(cleaned) < 8:
                    continue
                key = ("SECTION_STATEMENT", section_title, cleaned)
                if key in seen:
                    continue
                seen.add(key)
                claims.append({
                    "claim_id": _claim_id(source_id, page_id, section_title or "", "SECTION_STATEMENT", "", cleaned),
                    "source_id": source_id,
                    "page_id": page_id,
                    "page_title": title,
                    "page_url": page_url,
                    "revision_id": revision_id,
                    "revision_timestamp": revision_ts,
                    "section_title": section_title,
                    "claim_type": "SECTION_STATEMENT",
                    "subject_text": None,
                    "excerpt": cleaned[:1200],
                    "source_locator": f"section:{section_title}",
                    "authority": REFERENCE_ONLY,
                })
    return claims


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def resolve_subject(con: sqlite3.Connection, subject: str) -> list[dict]:
    """Conservative name resolver across indexed client/server reference tables."""
    candidates = []
    norm = _norm(subject)

    if _table_exists(con, "zones"):
        guess = re.sub(r"[^A-Za-z0-9]+", "_", subject).strip("_").upper()
        for zoneid, name in con.execute("SELECT zoneid,name FROM zones WHERE name=?", (guess,)).fetchall():
            candidates.append({
                "target_domain": "zone", "target_table": "zones", "target_key": str(zoneid),
                "target_label": name, "mapping_method": "ZONE_CONSTANT_NORMALIZED",
            })

    if _table_exists(con, "npc_names"):
        for npcid, name, zoneid in con.execute(
            "SELECT DISTINCT npcid,name,zoneid FROM npc_names WHERE LOWER(name)=LOWER(?) LIMIT 25",
            (subject,),
        ).fetchall():
            candidates.append({
                "target_domain": "entity", "target_table": "npc_names", "target_key": str(npcid),
                "target_label": name, "mapping_method": "DISPLAY_NAME_EXACT",
                "details": {"zoneid": zoneid},
            })

    if _table_exists(con, "key_items"):
        for keyid, name in con.execute(
            "SELECT keyitem_id,name FROM key_items WHERE LOWER(name)=LOWER(?) LIMIT 25", (subject,)
        ).fetchall():
            candidates.append({
                "target_domain": "key_item", "target_table": "key_items", "target_key": str(keyid),
                "target_label": name, "mapping_method": "DISPLAY_NAME_EXACT",
            })

    for table, id_col, name_col in (
        ("items_ours", "itemid", "name"),
        ("sql_item_basic", "itemid", "name"),
        ("topaz_item_basic", "itemid", "name"),
        ("lsb_item_basic", "itemid", "name"),
    ):
        if not _table_exists(con, table):
            continue
        try:
            rows = con.execute(f"SELECT {id_col},{name_col} FROM {table}").fetchall()
        except sqlite3.OperationalError:
            continue
        for itemid, name in rows:
            if _norm(str(name or "")) == norm:
                candidates.append({
                    "target_domain": "item", "target_table": table, "target_key": str(itemid),
                    "target_label": str(name), "mapping_method": "NORMALIZED_NAME_EXACT",
                })

    # De-duplicate same physical identity emitted through duplicate rows.
    unique = {}
    for cand in candidates:
        key = (cand["target_table"], cand["target_key"])
        unique[key] = cand
    return list(unique.values())


def map_claim(con: sqlite3.Connection, claim: dict) -> list[dict]:
    if claim["claim_type"] != "ENTITY_REFERENCE" or not claim.get("subject_text"):
        return [{
            "mapping_id": _mapping_id(claim["claim_id"], None, None, "UNMAPPED"),
            "claim_id": claim["claim_id"],
            "target_domain": None, "target_table": None, "target_key": None, "target_label": None,
            "mapping_method": "NO_AUTOMATIC_SEMANTIC_MAPPING",
            "mapping_status": "UNMAPPED",
            "confidence": "UNKNOWN",
            "details": {},
        }]

    candidates = resolve_subject(con, claim["subject_text"])
    if not candidates:
        return [{
            "mapping_id": _mapping_id(claim["claim_id"], None, None, "UNRESOLVED"),
            "claim_id": claim["claim_id"],
            "target_domain": None, "target_table": None, "target_key": None, "target_label": None,
            "mapping_method": "EXACT_NAME_RESOLUTION",
            "mapping_status": "UNRESOLVED",
            "confidence": "UNKNOWN",
            "details": {"subject_text": claim["subject_text"]},
        }]

    status = "MAPPED" if len(candidates) == 1 else "AMBIGUOUS"
    confidence = "HIGH" if len(candidates) == 1 else "LOW"
    out = []
    for cand in candidates:
        out.append({
            "mapping_id": _mapping_id(claim["claim_id"], cand["target_table"], cand["target_key"], status),
            "claim_id": claim["claim_id"],
            **cand,
            "mapping_status": status,
            "confidence": confidence,
            "details": cand.get("details", {}),
        })
    return out


def _store_claim(con: sqlite3.Connection, claim: dict) -> None:
    content_hash = hashlib.sha256(claim["excerpt"].encode("utf-8")).hexdigest()
    con.execute(
        """INSERT OR REPLACE INTO reference_wiki_claims
           (claim_id,source_id,page_id,page_title,page_url,revision_id,revision_timestamp,
            section_title,claim_type,subject_text,excerpt,source_locator,authority,content_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            claim["claim_id"], claim["source_id"], claim["page_id"], claim["page_title"],
            claim.get("page_url"), claim.get("revision_id"), claim.get("revision_timestamp"),
            claim.get("section_title"), claim["claim_type"], claim.get("subject_text"),
            claim["excerpt"], claim.get("source_locator"), claim.get("authority", REFERENCE_ONLY),
            content_hash,
        ),
    )


def _store_mapping(con: sqlite3.Connection, mapping: dict) -> None:
    con.execute(
        """INSERT OR REPLACE INTO reference_wiki_mappings
           (mapping_id,claim_id,target_domain,target_table,target_key,target_label,mapping_method,
            mapping_status,confidence,details_json)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            mapping["mapping_id"], mapping["claim_id"], mapping.get("target_domain"),
            mapping.get("target_table"), mapping.get("target_key"), mapping.get("target_label"),
            mapping["mapping_method"], mapping["mapping_status"], mapping["confidence"],
            json.dumps(mapping.get("details") or {}, sort_keys=True),
        ),
    )


def review_mapping(
    con: sqlite3.Connection,
    mapping_id: str,
    review_status: str,
    notes: str | None = None,
) -> None:
    init_db(con)
    review_status = (review_status or "").upper()
    if review_status not in {"CONFIRMED", "REJECTED", "UNREVIEWED"}:
        raise ValueError("review_status must be CONFIRMED, REJECTED, or UNREVIEWED")
    exists = con.execute(
        "SELECT 1 FROM reference_wiki_mappings WHERE mapping_id=?", (mapping_id,)
    ).fetchone()
    if not exists:
        raise ValueError(f"wiki mapping {mapping_id!r} not found")
    if review_status == "UNREVIEWED":
        con.execute("DELETE FROM reference_wiki_mapping_reviews WHERE mapping_id=?", (mapping_id,))
    else:
        con.execute(
            """INSERT OR REPLACE INTO reference_wiki_mapping_reviews(mapping_id,review_status,notes,reviewed_at)
               VALUES(?,?,?,CURRENT_TIMESTAMP)""",
            (mapping_id, review_status, notes),
        )
    con.commit()


def find_bg_page(title_query: str) -> dict | None:
    if not BG_DUMP_PATH.exists():
        return None
    query = title_from_query(title_query).lower()
    exact = None
    substring = None
    with gzip.open(BG_DUMP_PATH, "rt", encoding="utf-8") as src:
        for line in src:
            page = json.loads(line)
            if any(str(c).lower() == "catseyexi" for c in page.get("categories", [])):
                continue
            title = str(page.get("title") or "")
            if title.lower() == query:
                exact = page
                break
            if substring is None and query in title.lower():
                substring = page
    return exact or substring


def find_reference_page(con: sqlite3.Connection, source_id: str, title_query: str) -> dict | None:
    init_db(con)
    if source_id == SOURCE_BG:
        found = find_bg_page(title_query)
        if found:
            return found
    norm = _norm(title_from_query(title_query))
    if source_id == SOURCE_WIKIWIKI_JP:
        norm = title_from_query(title_query)  # JP titles have no a-z0-9 form; the scraper stores the raw title
    row = con.execute(
        """SELECT source_id,page_id,title,revision_id,revision_timestamp,page_text,page_hash
           FROM reference_wiki_pages WHERE source_id=? AND norm_title=? LIMIT 1""",
        (source_id, norm),
    ).fetchone()
    if not row:
        return None
    return {
        "source_id": row[0], "page_id": row[1], "title": row[2], "revision_id": row[3],
        "revision_timestamp": row[4], "page_text": row[5], "page_hash": row[6],
        "url": None,
    }


def ingest_page(con: sqlite3.Connection, source_id: str, title_query: str) -> dict:
    init_db(con)
    page = find_reference_page(con, source_id, title_query)
    if page is None:
        return {"status": "NOT_FOUND", "source_id": source_id, "query": title_query}

    claims = extract_claims(page, source_id=source_id)
    page_id = str(page.get("pageid") or page.get("page_id") or page.get("title"))
    con.execute("DELETE FROM reference_wiki_mappings WHERE claim_id IN (SELECT claim_id FROM reference_wiki_claims WHERE source_id=? AND page_id=?)", (source_id, page_id))
    con.execute("DELETE FROM reference_wiki_claims WHERE source_id=? AND page_id=?", (source_id, page_id))

    mappings = []
    for claim in claims:
        _store_claim(con, claim)
        for mapping in map_claim(con, claim):
            _store_mapping(con, mapping)
            mappings.append(mapping)
    con.commit()
    counts = {
        "claims": len(claims),
        "entity_references": sum(1 for c in claims if c["claim_type"] == "ENTITY_REFERENCE"),
        "section_statements": sum(1 for c in claims if c["claim_type"] == "SECTION_STATEMENT"),
        "mapped": sum(1 for m in mappings if m["mapping_status"] == "MAPPED"),
        "ambiguous": sum(1 for m in mappings if m["mapping_status"] == "AMBIGUOUS"),
        "unresolved": sum(1 for m in mappings if m["mapping_status"] == "UNRESOLVED"),
        "unmapped": sum(1 for m in mappings if m["mapping_status"] == "UNMAPPED"),
    }
    return {
        "status": "OK", "source_id": source_id, "page_id": page_id,
        "page_title": page.get("title"), "counts": counts,
    }


def page_evidence(con: sqlite3.Connection, source_id: str, title_query: str) -> dict:
    page = find_reference_page(con, source_id, title_query)
    if page is None:
        return {"status": "NOT_FOUND", "source_id": source_id, "query": title_query}
    page_id = str(page.get("pageid") or page.get("page_id") or page.get("title"))
    con.row_factory = sqlite3.Row
    claims = [
        dict(row) for row in con.execute(
            """SELECT * FROM reference_wiki_claims
               WHERE source_id=? AND page_id=?
               ORDER BY section_title,claim_type,subject_text,claim_id""",
            (source_id, page_id),
        ).fetchall()
    ]
    mappings_by_claim = {}
    for row in con.execute(
        """SELECT m.*,COALESCE(r.review_status,'UNREVIEWED') AS review_status,
                  r.notes AS review_notes,r.reviewed_at
           FROM reference_wiki_mappings m
           JOIN reference_wiki_claims c ON c.claim_id=m.claim_id
           LEFT JOIN reference_wiki_mapping_reviews r ON r.mapping_id=m.mapping_id
           WHERE c.source_id=? AND c.page_id=?
           ORDER BY m.claim_id,m.mapping_status,m.target_table,m.target_key""",
        (source_id, page_id),
    ).fetchall():
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json") or "{}")
        mappings_by_claim.setdefault(item["claim_id"], []).append(item)
    for claim in claims:
        claim["mappings"] = mappings_by_claim.get(claim["claim_id"], [])
    return {
        "status": "OK", "source_id": source_id, "page_id": page_id,
        "page_title": page.get("title"), "claims": claims,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("--source", default=SOURCE_BG, choices=(SOURCE_BG, SOURCE_FFXICLOPEDIA))
    ap.add_argument("--db", type=Path, default=DB_PATH)
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    result = ingest_page(con, args.source, args.title)
    print(json.dumps(result, indent=2, sort_keys=True))
    con.close()
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
