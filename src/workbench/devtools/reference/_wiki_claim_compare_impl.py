#!/usr/bin/env python3
"""Dual-wiki claim alignment and conservative conflict detection.

Compares already-ingested claim ledgers.  It never decides which wiki is correct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from difflib import SequenceMatcher
from pathlib import Path

import wiki_evidence

NEGATIONS = {"not","never","cannot","can't","doesn't","don't","isn't","won't","without","none","no"}


def _norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _tokens(value: str) -> set[str]:
    return set(_norm_text(value).split())


def _numbers(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", value or ""))


def _negated(value: str) -> bool:
    return any(tok in NEGATIONS for tok in _tokens(value))


def _strip_numbers_and_negation(value: str) -> str:
    toks = [t for t in _norm_text(value).split() if t not in NEGATIONS and not re.fullmatch(r"\d+(?:\.\d+)?%?", t)]
    return " ".join(toks)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm_text(a), _norm_text(b)).ratio()


def init_db(con: sqlite3.Connection) -> None:
    wiki_evidence.init_db(con)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS reference_wiki_page_alignments(
          alignment_id TEXT PRIMARY KEY,
          norm_title TEXT NOT NULL,
          bg_page_id TEXT,
          ffxiclopedia_page_id TEXT,
          status TEXT NOT NULL,
          details_json TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_reference_page_alignment_title
          ON reference_wiki_page_alignments(norm_title);

        CREATE TABLE IF NOT EXISTS reference_wiki_claim_alignments(
          pair_id TEXT PRIMARY KEY,
          alignment_id TEXT NOT NULL,
          bg_claim_id TEXT,
          ffxiclopedia_claim_id TEXT,
          alignment_type TEXT NOT NULL,
          status TEXT NOT NULL,
          similarity REAL,
          conflict_kind TEXT,
          details_json TEXT NOT NULL DEFAULT '{}',
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_reference_claim_alignment_page
          ON reference_wiki_claim_alignments(alignment_id,status);
        CREATE INDEX IF NOT EXISTS idx_reference_claim_alignment_claims
          ON reference_wiki_claim_alignments(bg_claim_id,ffxiclopedia_claim_id);
    """)
    con.commit()


def _alignment_id(norm_title: str) -> str:
    return "wiki-align:" + hashlib.sha1(norm_title.encode("utf-8")).hexdigest()[:20]


def _pair_id(alignment_id: str, bg_claim_id: str | None, fx_claim_id: str | None, status: str) -> str:
    raw = "|".join([alignment_id, bg_claim_id or "", fx_claim_id or "", status])
    return "wiki-pair:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:22]


def _claims(con: sqlite3.Connection, source_id: str, page_id: str) -> list[dict]:
    con.row_factory = sqlite3.Row
    return [
        dict(r) for r in con.execute(
            """SELECT * FROM reference_wiki_claims
               WHERE source_id=? AND page_id=?
               ORDER BY section_title,claim_type,subject_text,claim_id""",
            (source_id, page_id),
        ).fetchall()
    ]


def _page_id(con: sqlite3.Connection, source_id: str, title: str) -> str | None:
    norm = wiki_evidence._norm(title)
    row = con.execute(
        """SELECT page_id FROM reference_wiki_pages
           WHERE source_id=? AND norm_title=? LIMIT 1""",
        (source_id, norm),
    ).fetchone()
    if row:
        return str(row[0])
    # BG pages normally come from the dump and are represented by claims after ingestion.
    row = con.execute(
        """SELECT page_id FROM reference_wiki_claims
           WHERE source_id=? AND lower(page_title)=lower(?) LIMIT 1""",
        (source_id, title),
    ).fetchone()
    return str(row[0]) if row else None


def _statement_conflict(bg: dict, fx: dict) -> tuple[str | None, dict]:
    a, b = bg["excerpt"], fx["excerpt"]
    base_sim = _similarity(a, b)
    stripped_sim = SequenceMatcher(None, _strip_numbers_and_negation(a), _strip_numbers_and_negation(b)).ratio()
    nums_a, nums_b = _numbers(a), _numbers(b)
    neg_a, neg_b = _negated(a), _negated(b)

    if nums_a and nums_b and nums_a != nums_b and stripped_sim >= 0.72:
        return "NUMERIC_DISAGREEMENT", {
            "bg_numbers": nums_a, "ffxiclopedia_numbers": nums_b,
            "base_similarity": round(base_sim, 4), "structural_similarity": round(stripped_sim, 4),
        }
    if neg_a != neg_b and stripped_sim >= 0.78:
        return "NEGATION_DISAGREEMENT", {
            "bg_negated": neg_a, "ffxiclopedia_negated": neg_b,
            "base_similarity": round(base_sim, 4), "structural_similarity": round(stripped_sim, 4),
        }
    return None, {
        "base_similarity": round(base_sim, 4),
        "structural_similarity": round(stripped_sim, 4),
    }


def align_page(con: sqlite3.Connection, title: str) -> dict:
    init_db(con)
    norm_title = wiki_evidence._norm(title)
    alignment_id = _alignment_id(norm_title)
    bg_page_id = _page_id(con, wiki_evidence.SOURCE_BG, title)
    fx_page_id = _page_id(con, wiki_evidence.SOURCE_FFXICLOPEDIA, title)

    if not bg_page_id and not fx_page_id:
        return {"status": "NOT_FOUND", "title": title}

    page_status = "DUAL_SOURCE" if bg_page_id and fx_page_id else (
        "BG_ONLY" if bg_page_id else "FFXICLOPEDIA_ONLY"
    )
    con.execute(
        """INSERT OR REPLACE INTO reference_wiki_page_alignments
           (alignment_id,norm_title,bg_page_id,ffxiclopedia_page_id,status,details_json,updated_at)
           VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (alignment_id, norm_title, bg_page_id, fx_page_id, page_status, "{}"),
    )
    con.execute("DELETE FROM reference_wiki_claim_alignments WHERE alignment_id=?", (alignment_id,))

    bg_claims = _claims(con, wiki_evidence.SOURCE_BG, bg_page_id) if bg_page_id else []
    fx_claims = _claims(con, wiki_evidence.SOURCE_FFXICLOPEDIA, fx_page_id) if fx_page_id else []

    pairs = []
    used_bg, used_fx = set(), set()

    # Strongest deterministic alignment: same claim type + normalized entity subject.
    fx_entity = {}
    for c in fx_claims:
        if c["claim_type"] == "ENTITY_REFERENCE" and c.get("subject_text"):
            fx_entity.setdefault(wiki_evidence._norm(c["subject_text"]), []).append(c)
    for bg in bg_claims:
        if bg["claim_type"] != "ENTITY_REFERENCE" or not bg.get("subject_text"):
            continue
        key = wiki_evidence._norm(bg["subject_text"])
        candidates = fx_entity.get(key, [])
        if not candidates:
            continue
        for fx in candidates:
            if fx["claim_id"] in used_fx:
                continue
            status = "AGREEMENT"
            pair = {
                "bg": bg, "fx": fx, "alignment_type": "ENTITY_REFERENCE",
                "status": status, "similarity": 1.0, "conflict_kind": None,
                "details": {"normalized_subject": key},
            }
            pairs.append(pair); used_bg.add(bg["claim_id"]); used_fx.add(fx["claim_id"])
            break

    # Section statements: only compare inside same normalized section, greedily by similarity.
    remaining_bg = [c for c in bg_claims if c["claim_type"] == "SECTION_STATEMENT" and c["claim_id"] not in used_bg]
    remaining_fx = [c for c in fx_claims if c["claim_type"] == "SECTION_STATEMENT" and c["claim_id"] not in used_fx]
    for bg in remaining_bg:
        same_section = [
            fx for fx in remaining_fx
            if fx["claim_id"] not in used_fx
            and _norm_text(fx.get("section_title") or "") == _norm_text(bg.get("section_title") or "")
        ]
        if not same_section:
            continue
        ranked = sorted(((_similarity(bg["excerpt"], fx["excerpt"]), fx) for fx in same_section), reverse=True, key=lambda x: x[0])
        sim, fx = ranked[0]
        if sim < 0.42:
            continue
        conflict_kind, details = _statement_conflict(bg, fx)
        if conflict_kind:
            status = "REFERENCE_CONFLICT"
        elif sim >= 0.82:
            status = "AGREEMENT"
        else:
            status = "DIVERGENT"
        pairs.append({
            "bg": bg, "fx": fx, "alignment_type": "SECTION_STATEMENT",
            "status": status, "similarity": sim, "conflict_kind": conflict_kind,
            "details": details,
        })
        used_bg.add(bg["claim_id"]); used_fx.add(fx["claim_id"])

    for bg in bg_claims:
        if bg["claim_id"] not in used_bg:
            pairs.append({
                "bg": bg, "fx": None, "alignment_type": bg["claim_type"],
                "status": "BG_ONLY", "similarity": None, "conflict_kind": None, "details": {},
            })
    for fx in fx_claims:
        if fx["claim_id"] not in used_fx:
            pairs.append({
                "bg": None, "fx": fx, "alignment_type": fx["claim_type"],
                "status": "FFXICLOPEDIA_ONLY", "similarity": None, "conflict_kind": None, "details": {},
            })

    for pair in pairs:
        bgid = pair["bg"]["claim_id"] if pair["bg"] else None
        fxid = pair["fx"]["claim_id"] if pair["fx"] else None
        pid = _pair_id(alignment_id, bgid, fxid, pair["status"])
        con.execute(
            """INSERT INTO reference_wiki_claim_alignments
               (pair_id,alignment_id,bg_claim_id,ffxiclopedia_claim_id,alignment_type,status,
                similarity,conflict_kind,details_json)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                pid, alignment_id, bgid, fxid, pair["alignment_type"], pair["status"],
                pair["similarity"], pair["conflict_kind"], json.dumps(pair["details"], sort_keys=True),
            ),
        )

    con.commit()
    counts = {k: 0 for k in ("AGREEMENT","REFERENCE_CONFLICT","DIVERGENT","BG_ONLY","FFXICLOPEDIA_ONLY")}
    for pair in pairs:
        counts[pair["status"]] = counts.get(pair["status"], 0) + 1
    return {
        "status": "OK", "alignment_id": alignment_id, "title": title,
        "page_status": page_status, "bg_page_id": bg_page_id,
        "ffxiclopedia_page_id": fx_page_id, "counts": counts,
    }


def alignment_report(con: sqlite3.Connection, title: str) -> dict:
    init_db(con)
    norm = wiki_evidence._norm(title)
    con.row_factory = sqlite3.Row
    page = con.execute(
        "SELECT * FROM reference_wiki_page_alignments WHERE norm_title=?",
        (norm,),
    ).fetchone()
    if not page:
        return {"status": "NOT_BUILT", "title": title}
    rows = con.execute(
        """SELECT a.*,bg.excerpt AS bg_excerpt,bg.subject_text AS bg_subject,bg.section_title AS bg_section,
                  bg.revision_id AS bg_revision,bg.revision_timestamp AS bg_revision_timestamp,
                  fx.excerpt AS fx_excerpt,fx.subject_text AS fx_subject,fx.section_title AS fx_section,
                  fx.revision_id AS fx_revision,fx.revision_timestamp AS fx_revision_timestamp
           FROM reference_wiki_claim_alignments a
           LEFT JOIN reference_wiki_claims bg ON bg.claim_id=a.bg_claim_id
           LEFT JOIN reference_wiki_claims fx ON fx.claim_id=a.ffxiclopedia_claim_id
           WHERE a.alignment_id=?
           ORDER BY CASE a.status
              WHEN 'REFERENCE_CONFLICT' THEN 0 WHEN 'DIVERGENT' THEN 1
              WHEN 'BG_ONLY' THEN 2 WHEN 'FFXICLOPEDIA_ONLY' THEN 3 ELSE 4 END,
              a.alignment_type,a.pair_id""",
        (page["alignment_id"],),
    ).fetchall()
    pairs = []
    for row in rows:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json") or "{}")
        pairs.append(item)
    return {"status": "OK", "page": dict(page), "pairs": pairs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("--db", type=Path, default=wiki_evidence.DB_PATH)
    args = ap.parse_args()
    con = sqlite3.connect(args.db)
    result = align_page(con, args.title)
    print(json.dumps(result, indent=2, sort_keys=True))
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
