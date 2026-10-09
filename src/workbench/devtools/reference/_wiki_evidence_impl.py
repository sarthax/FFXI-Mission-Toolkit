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

        CREATE TABLE IF NOT EXISTS reference_wiki_relations(
          relation_id TEXT PRIMARY KEY,
          source_id TEXT NOT NULL,
          page_id TEXT NOT NULL,
          page_title TEXT NOT NULL,
          page_url TEXT,
          revision_id TEXT,
          revision_timestamp TEXT,
          section_title TEXT,
          relation_type TEXT NOT NULL,
          subject_text TEXT NOT NULL,
          object_text TEXT NOT NULL,
          source_locator TEXT,
          authority TEXT NOT NULL DEFAULT 'REFERENCE_ONLY',
          extraction_method TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_reference_relation_page
          ON reference_wiki_relations(source_id,page_id,section_title);
        CREATE INDEX IF NOT EXISTS idx_reference_relation_type
          ON reference_wiki_relations(relation_type);

        CREATE TABLE IF NOT EXISTS reference_wiki_relation_mappings(
          relation_mapping_id TEXT PRIMARY KEY,
          relation_id TEXT NOT NULL,
          endpoint TEXT NOT NULL,
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
        CREATE INDEX IF NOT EXISTS idx_reference_relation_mapping_relation
          ON reference_wiki_relation_mappings(relation_id,endpoint);
        CREATE INDEX IF NOT EXISTS idx_reference_relation_mapping_target
          ON reference_wiki_relation_mappings(target_table,target_key);
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


def _relation_id(source_id: str, page_id: str, section: str, relation_type: str, subject: str, obj: str) -> str:
    raw="|".join([source_id,page_id,section or "",relation_type,subject or "",obj or ""])
    return "wiki-rel:"+hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _relation_mapping_id(relation_id: str, endpoint: str, table: str | None, key: str | None, status: str) -> str:
    raw="|".join([relation_id,endpoint,table or "",key or "",status])
    return "wiki-relmap:"+hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


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


def _resolve_subject_direct(con: sqlite3.Connection, subject: str) -> list[dict]:
    """Conservative direct-name resolver across indexed client/server reference tables."""
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



def _canonical_topic_aliases(con: sqlite3.Connection, subject: str) -> list[str]:
    """Return reviewed canonical topic labels for a source-page title, if any."""
    if not (_table_exists(con, "reference_wiki_pages") and _table_exists(con, "reference_wiki_topic_pages")
            and _table_exists(con, "reference_wiki_topics")):
        return []
    rows=con.execute(
        """SELECT DISTINCT t.canonical_title
           FROM reference_wiki_pages p
           JOIN reference_wiki_topic_pages tp
             ON tp.source_id=p.source_id AND tp.page_id=p.page_id
           JOIN reference_wiki_topics t ON t.topic_id=tp.topic_id
           WHERE lower(p.title)=lower(?) OR p.page_id=?""",
        (subject,subject),
    ).fetchall()
    return [str(row[0]) for row in rows if row and row[0] and str(row[0]).casefold()!=subject.casefold()]


def resolve_subject(con: sqlite3.Connection, subject: str) -> list[dict]:
    """Resolve a source label directly, then through reviewed multilingual topic aliases."""
    direct=_resolve_subject_direct(con,subject)
    if direct:
        return direct
    candidates=[]
    for alias in _canonical_topic_aliases(con,subject):
        for cand in _resolve_subject_direct(con,alias):
            copy=dict(cand)
            copy["mapping_method"]="MULTILINGUAL_TOPIC_ALIAS"
            details=dict(copy.get("details") or {})
            details.update({"source_subject":subject,"canonical_topic":alias})
            copy["details"]=details
            candidates.append(copy)
    unique={}
    for cand in candidates:
        unique[(cand["target_table"],cand["target_key"])]=cand
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



def _evidence_blocks(con: sqlite3.Connection, page: dict, source_id: str) -> list[dict]:
    """Return source-located blocks, persisting offline-available MediaWiki structure when possible."""
    page_id=str(page.get("pageid") or page.get("page_id") or page.get("title"))
    blocks=wiki_document.stored_blocks(con,source_id,page_id)
    if blocks:
        return blocks
    if source_id in {SOURCE_BG,SOURCE_FFXICLOPEDIA}:
        raw=page.get("wikitext") if "wikitext" in page else page.get("page_text") or ""
        _,source_format,blocks=wiki_document.build_blocks(
            page,source_format="mediawiki",raw_source=raw
        )
        wiki_document.store_document(
            con,source_id=source_id,page_id=page_id,source_format=source_format,
            raw_source=raw,blocks=blocks,
        )
        wiki_document.ensure_title_alias(con,source_id,page_id,page.get("title") or page_id)
        return blocks
    return []


def _structured_link_claims(con: sqlite3.Connection, page: dict, source_id: str) -> list[dict]:
    """Promote preserved source links into normal REFERENCE_ONLY entity-reference claims."""
    page_id=str(page.get("pageid") or page.get("page_id") or page.get("title"))
    blocks=_evidence_blocks(con,page,source_id)
    if not blocks:
        return []
    title=page.get("title") or ""
    revision_id=str(page.get("revid") or page.get("revision_id") or "") or None
    revision_ts=page.get("timestamp") or page.get("revision_timestamp")
    page_url=page.get("url")
    claims=[]
    seen=set()
    for block in blocks:
        if block.get("block_type")!="link":
            continue
        target=(block.get("target") or "").strip()
        label=(block.get("text") or "").strip()
        if not target:
            continue
        parsed=urllib.parse.urlparse(target)
        if parsed.scheme and parsed.netloc:
            if source_id==SOURCE_WIKIWIKI_JP and parsed.netloc.endswith("wikiwiki.jp") and parsed.path.startswith("/ffxi/"):
                target=urllib.parse.unquote(parsed.path[len("/ffxi/"):]).strip("/")
            else:
                continue
        elif source_id==SOURCE_WIKIWIKI_JP and target.startswith("/ffxi/"):
            target=urllib.parse.unquote(target[len("/ffxi/"):]).strip("/")
        elif target.startswith(("#","javascript:","mailto:")):
            continue
        target=urllib.parse.unquote(target).replace("_"," ").strip()
        if not target or target.lower().startswith(_NON_ENTITY_PREFIXES):
            continue
        section_path=block.get("section_path") or ""
        section_title=section_path.split(" > ")[-1] if section_path else None
        excerpt=label or target
        key=(section_title or "",target.casefold(),excerpt)
        if key in seen:
            continue
        seen.add(key)
        claims.append({
            "claim_id":_claim_id(source_id,page_id,section_title or "","ENTITY_REFERENCE",target,excerpt),
            "source_id":source_id,
            "page_id":page_id,
            "page_title":title,
            "page_url":page_url,
            "revision_id":revision_id,
            "revision_timestamp":revision_ts,
            "section_title":section_title,
            "claim_type":"ENTITY_REFERENCE",
            "subject_text":target,
            "excerpt":excerpt[:700],
            "source_locator":block.get("source_locator") or f"block:{block.get('block_id')}",
            "authority":REFERENCE_ONLY,
        })
    return claims



_RELATION_SECTION_NAMES = {
    "REFERENCE_DROPS": {
        "drops","drop","loot","戦利品","ドロップ","ドロップ品","戦利品一覧",
    },
    "REFERENCE_REWARDS": {
        "reward","rewards","報酬","クリア報酬","報酬品",
    },
    "REFERENCE_LOCATED_IN": {
        "location","locations","area","zone","場所","出現場所","エリア","生息域","所在地",
    },
    "REFERENCE_REQUIRES": {
        "requirement","requirements","prerequisite","prerequisites","eligibility",
        "条件","参加条件","前提条件","必要条件","突入条件",
    },
}
_RELATION_OBJECT_DOMAINS = {
    "REFERENCE_DROPS": {"item","key_item"},
    "REFERENCE_REWARDS": {"item","key_item"},
    "REFERENCE_LOCATED_IN": {"zone"},
    "REFERENCE_REQUIRES": {"item","key_item","zone"},
}


def _relation_type_for_section(section_path: str | None) -> str | None:
    parts=[wiki_document.normalize_search(x) for x in (section_path or "").split(" > ") if x.strip()]
    for relation_type,names in _RELATION_SECTION_NAMES.items():
        normalized={wiki_document.normalize_search(name) for name in names}
        if any(part in normalized for part in parts):
            return relation_type
    return None


def _internal_link_target(source_id: str, target: str) -> str | None:
    target=(target or "").strip()
    if not target:
        return None
    parsed=urllib.parse.urlparse(target)
    if parsed.scheme and parsed.netloc:
        if source_id==SOURCE_WIKIWIKI_JP and parsed.netloc.endswith("wikiwiki.jp") and parsed.path.startswith("/ffxi/"):
            target=urllib.parse.unquote(parsed.path[len("/ffxi/"):]).strip("/")
        else:
            return None
    elif source_id==SOURCE_WIKIWIKI_JP and target.startswith("/ffxi/"):
        target=urllib.parse.unquote(target[len("/ffxi/"):]).strip("/")
    elif parsed.scheme or parsed.netloc or target.startswith(("#","//","?")):
        # External, protocol-relative and non-page references cannot identify a
        # wiki entity. In particular, do not turn mailto: or javascript: into
        # a plausible target merely because they have no network location.
        return None
    target=urllib.parse.unquote(target).split("#", 1)[0].split("?", 1)[0].replace("_"," ").strip()
    if not target or target.lower().startswith(_NON_ENTITY_PREFIXES):
        return None
    return target


def extract_structured_relations(con: sqlite3.Connection, page: dict, source_id: str) -> list[dict]:
    """Extract only explicitly section-labelled binary reference relationships."""
    page_id=str(page.get("pageid") or page.get("page_id") or page.get("title"))
    blocks=_evidence_blocks(con,page,source_id)
    if not blocks:
        return []
    topic=wiki_document.page_topic(con,source_id,page_id)
    subject=(topic or {}).get("canonical_title") or page.get("title") or ""
    if not subject:
        return []
    revision_id=str(page.get("revid") or page.get("revision_id") or "") or None
    revision_ts=page.get("timestamp") or page.get("revision_timestamp")
    page_url=page.get("url")
    out=[]
    seen=set()
    for block in blocks:
        if block.get("block_type")!="link":
            continue
        relation_type=_relation_type_for_section(block.get("section_path"))
        if not relation_type:
            continue
        obj=_internal_link_target(source_id,block.get("target") or "")
        if not obj:
            continue
        section_path=block.get("section_path") or ""
        section_title=section_path.split(" > ")[-1] if section_path else None
        key=(relation_type,subject.casefold(),obj.casefold(),section_title or "")
        if key in seen:
            continue
        seen.add(key)
        locator=block.get("source_locator") or f"block:{block.get('block_id')}"
        rid=_relation_id(source_id,page_id,section_title or "",relation_type,subject,obj)
        out.append({
            "relation_id":rid,"source_id":source_id,"page_id":page_id,
            "page_title":page.get("title") or "","page_url":page_url,
            "revision_id":revision_id,"revision_timestamp":revision_ts,
            "section_title":section_title,"relation_type":relation_type,
            "subject_text":subject,"object_text":obj,"source_locator":locator,
            "authority":REFERENCE_ONLY,"extraction_method":"STRUCTURED_SECTION_LINK",
        })
    return out


def map_relation_endpoint(con: sqlite3.Connection, relation: dict, endpoint: str) -> list[dict]:
    if endpoint not in {"subject","object"}:
        raise ValueError("endpoint must be subject or object")
    text=relation[f"{endpoint}_text"]
    candidates=resolve_subject(con,text)
    if endpoint=="object":
        allowed=_RELATION_OBJECT_DOMAINS.get(relation["relation_type"])
        if allowed:
            candidates=[c for c in candidates if c.get("target_domain") in allowed]
    if not candidates:
        return [{
            "relation_mapping_id":_relation_mapping_id(relation["relation_id"],endpoint,None,None,"UNRESOLVED"),
            "relation_id":relation["relation_id"],"endpoint":endpoint,
            "target_domain":None,"target_table":None,"target_key":None,"target_label":None,
            "mapping_method":"STRUCTURED_RELATION_RESOLUTION","mapping_status":"UNRESOLVED",
            "confidence":"UNKNOWN","details":{"source_text":text},
        }]
    status="MAPPED" if len(candidates)==1 else "AMBIGUOUS"
    confidence="HIGH" if len(candidates)==1 else "LOW"
    return [{
        "relation_mapping_id":_relation_mapping_id(
            relation["relation_id"],endpoint,cand["target_table"],cand["target_key"],status
        ),
        "relation_id":relation["relation_id"],"endpoint":endpoint,**cand,
        "mapping_status":status,"confidence":confidence,
        "details":cand.get("details") or {},
    } for cand in candidates]


def _store_relation(con: sqlite3.Connection, relation: dict) -> None:
    content_hash=hashlib.sha256(
        "|".join([relation["relation_type"],relation["subject_text"],relation["object_text"]]).encode("utf-8")
    ).hexdigest()
    con.execute(
        """INSERT OR REPLACE INTO reference_wiki_relations
           (relation_id,source_id,page_id,page_title,page_url,revision_id,revision_timestamp,
            section_title,relation_type,subject_text,object_text,source_locator,authority,
            extraction_method,content_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            relation["relation_id"],relation["source_id"],relation["page_id"],relation["page_title"],
            relation.get("page_url"),relation.get("revision_id"),relation.get("revision_timestamp"),
            relation.get("section_title"),relation["relation_type"],relation["subject_text"],
            relation["object_text"],relation.get("source_locator"),relation.get("authority",REFERENCE_ONLY),
            relation["extraction_method"],content_hash,
        ),
    )


def _store_relation_mapping(con: sqlite3.Connection, mapping: dict) -> None:
    con.execute(
        """INSERT OR REPLACE INTO reference_wiki_relation_mappings
           (relation_mapping_id,relation_id,endpoint,target_domain,target_table,target_key,target_label,
            mapping_method,mapping_status,confidence,details_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            mapping["relation_mapping_id"],mapping["relation_id"],mapping["endpoint"],
            mapping.get("target_domain"),mapping.get("target_table"),mapping.get("target_key"),
            mapping.get("target_label"),mapping["mapping_method"],mapping["mapping_status"],
            mapping["confidence"],json.dumps(mapping.get("details") or {},sort_keys=True),
        ),
    )


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
    """Prefer imported cache records and exact identities over the offline BG dump.

    Wiki search links may carry a page ID, while manual Browse uses a title.
    Both must resolve to the same imported page and structured block identity.
    """
    init_db(con)
    title = title_from_query(title_query)
    norm = _norm(title)
    if source_id == SOURCE_WIKIWIKI_JP:
        norm = title
    row = con.execute(
        """SELECT source_id,page_id,title,revision_id,revision_timestamp,page_text,page_hash
           FROM reference_wiki_pages
           WHERE source_id=? AND
             (page_id=? OR norm_title=? OR lower(title)=lower(?))
           ORDER BY CASE WHEN page_id=? THEN 0 WHEN lower(title)=lower(?) THEN 1 ELSE 2 END
           LIMIT 1""",
        (source_id, str(title_query), norm, title, str(title_query), title),
    ).fetchone()
    if row:
        return {
            "source_id": row[0], "page_id": row[1], "title": row[2],
            "revision_id": row[3], "revision_timestamp": row[4],
            "page_text": row[5], "page_hash": row[6], "url": None,
        }
    if source_id == SOURCE_BG:
        return find_bg_page(title)
    return None


def ingest_page(con: sqlite3.Connection, source_id: str, title_query: str) -> dict:
    init_db(con)
    page = find_reference_page(con, source_id, title_query)
    if page is None:
        return {"status": "NOT_FOUND", "source_id": source_id, "query": title_query}

    claims = extract_claims(page, source_id=source_id)
    existing={(c.get("claim_type"),(c.get("section_title") or "").casefold(),(c.get("subject_text") or "").casefold())
              for c in claims}
    for claim in _structured_link_claims(con,page,source_id):
        key=(claim.get("claim_type"),(claim.get("section_title") or "").casefold(),(claim.get("subject_text") or "").casefold())
        if key not in existing:
            claims.append(claim)
            existing.add(key)
    page_id = str(page.get("pageid") or page.get("page_id") or page.get("title"))
    con.execute("DELETE FROM reference_wiki_mappings WHERE claim_id IN (SELECT claim_id FROM reference_wiki_claims WHERE source_id=? AND page_id=?)", (source_id, page_id))
    con.execute("DELETE FROM reference_wiki_claims WHERE source_id=? AND page_id=?", (source_id, page_id))
    con.execute("""DELETE FROM reference_wiki_relation_mappings
                   WHERE relation_id IN (SELECT relation_id FROM reference_wiki_relations
                                         WHERE source_id=? AND page_id=?)""",(source_id,page_id))
    con.execute("DELETE FROM reference_wiki_relations WHERE source_id=? AND page_id=?",(source_id,page_id))

    mappings = []
    for claim in claims:
        _store_claim(con, claim)
        for mapping in map_claim(con, claim):
            _store_mapping(con, mapping)
            mappings.append(mapping)

    relations=extract_structured_relations(con,page,source_id)
    relation_mappings=[]
    for relation in relations:
        _store_relation(con,relation)
        for endpoint in ("subject","object"):
            for mapping in map_relation_endpoint(con,relation,endpoint):
                _store_relation_mapping(con,mapping)
                relation_mappings.append(mapping)
    con.commit()
    mapped_relation_ids={
        relation["relation_id"] for relation in relations
        if all(
            sum(1 for m in relation_mappings
                if m["relation_id"]==relation["relation_id"]
                and m["endpoint"]==endpoint
                and m["mapping_status"]=="MAPPED")==1
            for endpoint in ("subject","object")
        )
    }
    counts = {
        "claims": len(claims),
        "entity_references": sum(1 for c in claims if c["claim_type"] == "ENTITY_REFERENCE"),
        "section_statements": sum(1 for c in claims if c["claim_type"] == "SECTION_STATEMENT"),
        "mapped": sum(1 for m in mappings if m["mapping_status"] == "MAPPED"),
        "ambiguous": sum(1 for m in mappings if m["mapping_status"] == "AMBIGUOUS"),
        "unresolved": sum(1 for m in mappings if m["mapping_status"] == "UNRESOLVED"),
        "unmapped": sum(1 for m in mappings if m["mapping_status"] == "UNMAPPED"),
        "relations": len(relations),
        "mapped_relations": len(mapped_relation_ids),
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
    relations=[]
    for row in con.execute(
        """SELECT * FROM reference_wiki_relations
           WHERE source_id=? AND page_id=? ORDER BY section_title,relation_type,relation_id""",
        (source_id,page_id),
    ).fetchall():
        relation=dict(row)
        relmaps=[]
        for mrow in con.execute(
            """SELECT * FROM reference_wiki_relation_mappings
               WHERE relation_id=? ORDER BY endpoint,mapping_status,target_table,target_key""",
            (relation["relation_id"],),
        ).fetchall():
            item=dict(mrow)
            item["details"]=json.loads(item.pop("details_json") or "{}")
            relmaps.append(item)
        relation["mappings"]=relmaps
        relations.append(relation)
    return {
        "status": "OK", "source_id": source_id, "page_id": page_id,
        "page_title": page.get("title"), "claims": claims, "relations": relations,
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
