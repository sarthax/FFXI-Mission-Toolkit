"""Extract the sanitized Wiki V2 regression corpus from a LOCAL Toolkit database.

Reads ``reference_wiki_*`` tables read-only and writes minimal structural excerpts
(template parameters with short values, or a few table rows) plus provenance to
``test_fixtures/wiki_corpus/real_manifest.json``. Full pages are never written.

The CI runner never needs this script or the database; it only reads the manifest.
Re-run only to refresh/extend the real-source samples:

    py -3.11 scripts/wiki_corpus_extract.py --db ffxi_zone_database.db

Expected classifications come from the documented exact-label policy in
``EXPECTED_FIELD_TYPES`` (a frozen copy of the Wiki V2 contract) -- they are NOT read
back from the parser, so a parser regression or an unreviewed alias shows up as a diff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import urllib.parse
from pathlib import Path

import mwparserfromhell

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "test_fixtures" / "wiki_corpus" / "real_manifest.json"
JP_OUT = ROOT / "test_fixtures" / "wiki_corpus" / "real_jp_manifest.json"
MAX_VALUE = 220  # characters kept per parameter value
EXTRACT_VERSION = "wiki-corpus-extract-v1"

SOURCES = {
    "BGWiki": {"base": "https://www.bg-wiki.com/ffxi/", "license": "see site footer (CC BY-NC-SA believed); attribution retained"},
    "FFXIclopedia": {"base": "https://ffxiclopedia.fandom.com/wiki/", "license": "see site footer (CC BY-SA believed); attribution retained"},
}

# Frozen documented contract (exact normalized label -> canonical type).
EXPECTED_FIELD_TYPES = {
    "drops": "DROPS", "drop": "DROPS", "loot": "DROPS", "戦利品": "DROPS", "ドロップ": "DROPS",
    "reward": "REWARDS", "rewards": "REWARDS", "報酬": "REWARDS",
    "location": "LOCATION", "zone": "LOCATION", "場所": "LOCATION", "エリア": "LOCATION",
    "requirements": "REQUIRES", "prerequisites": "REQUIRES", "必要条件": "REQUIRES", "参加条件": "REQUIRES",
    "spawn conditions": "SPAWN_CONDITIONS", "spawn condition": "SPAWN_CONDITIONS", "spawn": "SPAWN_CONDITIONS",
    "pop conditions": "SPAWN_CONDITIONS", "出現条件": "SPAWN_CONDITIONS", "ポップ条件": "SPAWN_CONDITIONS",
    "quest": "QUEST", "quests": "QUEST", "mission": "QUEST", "missions": "QUEST", "クエスト": "QUEST", "ミッション": "QUEST",
    "notorious monster": "NM_IDENTITY", "nm": "NM_IDENTITY", "nm name": "NM_IDENTITY", "ノートリアスモンスター": "NM_IDENTITY",
}

# (sample_id, source, page title, kind, template/table selector, category tags, note)
SPECS = [
    ("bg-nm-medusa", "BGWiki", "Medusa", "template", "Adversary Description", ["nm", "infobox", "research-example"], "Known research example; Notes param embeds ===headings==="),
    ("bg-nm-absolute-virtue", "BGWiki", "Absolute Virtue", "template", "Adversary Description", ["nm", "infobox", "research-example"], "Known research example"),
    ("bg-quest-header", "BGWiki", "Granddaddy Dearest", "template", "Quest Header", ["quest", "rewards", "nested-links"], ""),
    ("bg-mission-header", "BGWiki", "Seekers of Adoulin Mission 2-1", "template", "Mission Header", ["mission", "rewards"], ""),
    ("bg-keyitem-header", "BGWiki", "Insulator tablet", "template", "Key Item Header", ["key-item"], ""),
    ("bg-npc-template", "BGWiki", "Fariska Lokhmi", "template", "NPC", ["npc", "location"], ""),
    ("bg-bcnm-drops", "BGWiki", "Divine Might II", "template", "BCNMv2", ["drops", "treasure", "location", "tiered-drop-labels"], "DropsB/DropsC style labels are not exact allowlist matches"),
    ("bg-trial-magians", "BGWiki", "Trial 4999", "template", "Trial of the Magians", ["requirements", "rewards", "location"], ""),
    ("bg-campaign-header", "BGWiki", "Fiat Lux (W)", "template", "Campaign Header", ["rewards", "location"], ""),
    ("bg-two-columns", "BGWiki", "Gua. Lumber", "template", "Two Columns", ["two-column", "unsupported-labels"], "heading/content labels are layout, not semantics"),
    ("bg-insert-template-table", "BGWiki", "Leviathan's Couse", "template", "Item Quest Reward Table", ["rewards", "nested-template", "unsupported-labels"], "Value is an 'Insert ... List Template' macro name"),
    ("bg-adversary-2-japanese", "BGWiki", "id:143859", "template", "Adversary Description 2", ["nm", "japanese-label"], "Contains a Japanese= field value"),
    ("bg-malformed-unclosed", "BGWiki", "Goblin Headsman", "template", "*", ["malformed"], "Source has 3 '{{' vs 4 '}}'"),
    ("bg-table-shikaree-x", "BGWiki", "Shikaree X", "table", None, ["table", "two-column"], ""),
    ("bg-table-dryptotaur", "BGWiki", "Dryptotaur", "table", None, ["table", "nm", "drops"], ""),
    ("bg-table-attrs-rowspan", "BGWiki", "id:100195", "table", None, ["table", "cell-attributes", "rowspan", "colspan"], "Cell attributes (colspan/BGCOLOR/width) must not leak into cell text"),
    ("bg-table-nm-column-header", "BGWiki", "Easy Button", "table", None, ["table", "column-header-hit", "nm"], "Header cell NM types the cells beneath it (review-only)"),
    ("ffx-keyitem-infobox", "FFXIclopedia", '"Adoulin\'s Topiary Treasures"', "template", "Infobox Key Item", ["key-item", "infobox", "quest"], ""),
    ("ffx-keyitem-infobox-2", "FFXIclopedia", '"Climbing"', "template", "Infobox Key Item", ["key-item", "infobox"], ""),
    ("ffx-item-statistics", "FFXIclopedia", '"A" Egg', "template", "Item Statistics", ["item", "infobox"], ""),
    ("ffx-quest", "FFXIclopedia", '"Always more," Quoth the Ravenous', "template", "Quest", ["quest", "rewards", "requirements"], ""),
    ("ffx-quest-description", "FFXIclopedia", '"Always more," Quoth the Ravenous', "template", "Quest/Description", ["quest", "nested-template"], ""),
    ("ffx-table-abs", "FFXIclopedia", '"A" - Abs', "table", None, ["table"], ""),
    ("ffx-table-bloodpact", "FFXIclopedia", '"Blood Pact" Ability Delay', "table", None, ["table"], ""),
]


# Real WikiWikiJP HTML table excerpts: (sample_id, page title, table index, tags, note).
JP_BASE = "https://wikiwiki.jp/ffxi/"
JP_SPECS = [
    ("jp-vw-loot-table", "ヴォイドウォッチ/第一章/戦利品", 0, ["table", "drops", "japanese-label"], "Loot list table; header is not a label/value pair"),
    ("jp-vw-npc-table", "ヴォイドウォッチ/NPC", 0, ["table", "rowspan"], "Exchange table with rowspan/colspan cells"),
    ("jp-vw-weakness-table", "ヴォイドウォッチ/弱点", 0, ["table", "row-header"], "Row-header (th) first column"),
    ("jp-vw-route-table", "ヴォイドウォッチ/第一章/ルート：ウィンダス", 0, ["table", "nested-links", "map-grid"], "Route table with in-page anchors and grid references"),
    ("jp-bfnm-area-npc-table", "BFNM", 1, ["table", "header-pair-hint", "japanese-label"], "Header row エリア|NPC is paired as label/value by the table hinting"),
    ("jp-bfnm-location-monster-table", "BFNM", 5, ["table", "header-pair-hint", "japanese-label"], "Header row 場所|モンスター名称"),
    ("jp-nm-abyssean-area-table", "NM/アビセアン", 0, ["table", "header-pair-hint", "nm"], "Header row エリア|無色 (colour columns), not a label/value table"),
    ("jp-nm-index-list", "NM", "list", ["list", "nm", "no-structure"], "NM index is plain list items with links: no labels, no hints"),
]
JP_TABLE_ROWS = 2  # body rows kept after the header
JP_LIST_ITEMS = 4


def html_list_excerpt(raw: str):
    items = re.findall(r"<li>.*?</li>", raw, re.S | re.I)
    items = [i for i in items if "<li>" not in i[4:] and len(i) < 400][:JP_LIST_ITEMS]
    return "<ul>" + "".join(items) + "</ul>" if items else None


def html_table_excerpt(raw: str, index: int):
    tabs = re.findall(r"<table.*?</table>", raw, re.S | re.I)
    if index >= len(tabs):
        return None
    t = tabs[index]
    head = re.search(r"<thead>.*?</thead>", t, re.S | re.I)
    rows = re.findall(r"<tr>.*?</tr>", re.sub(r"<thead>.*?</thead>", "", t, flags=re.S | re.I), re.S | re.I)
    body = "".join(rows[:JP_TABLE_ROWS])
    return "<table>" + (head.group(0) if head else "") + "<tbody>" + body + "</tbody></table>"


def html_cells(excerpt: str):
    """Independent (parser-free) cell inventory: [(tag, plain text)]."""
    out = []
    for m in re.finditer(r"<(th|td|li)(?: [^>]*)?>(.*?)</(?:th|td|li)>", excerpt, re.S | re.I):
        text = re.sub(r"<[^>]+>", " ", m.group(2))
        out.append((m.group(1).lower(), " ".join(text.split())))
    return out


def norm(label: str) -> str:
    return re.sub(r"\s+", " ", (label or "").strip()).casefold()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def template_excerpt(raw: str, name: str):
    code = mwparserfromhell.parse(raw)
    tpls = [t for t in code.filter_templates(recursive=False)]
    if name != "*":
        tpls = [t for t in tpls if str(t.name).strip().casefold() == name.casefold()]
    if not tpls:
        return None
    t = tpls[0]
    lines, kept, omitted = [f"{{{{{str(t.name).strip()}"], [], []
    for p in t.params:
        if not p.showkey:
            continue
        key, val = str(p.name).strip(), str(p.value).strip()
        v = val.replace("\r", "")
        if "\n" in v or len(v) > MAX_VALUE or v.count("{{") != v.count("}}") or v.count("[[") != v.count("]]"):
            omitted.append(key)
            continue
        lines.append(f"|{key}={v}")
        kept.append(key)
    lines.append("}}")
    return "\n".join(lines), kept, omitted, str(t.name).strip()


def expected_fields(excerpt: str):
    """Per-field expectations derived from the frozen policy, not from the parser."""
    t = mwparserfromhell.parse(excerpt).filter_templates(recursive=False)[0]
    out = []
    for idx, p in enumerate(t.params, 1):
        if not p.showkey:
            continue
        label, raw = str(p.name).strip(), str(p.value).strip()
        ftype = EXPECTED_FIELD_TYPES.get(norm(label))
        out.append({"label": label, "raw_value": raw, "locator": f"section::template:1:field:{idx}",
                    "expected_type": ftype, "review_only": True,
                    "reject_reason": None if ftype else "label not in exact-label policy"})
    return out


def table_excerpt(raw: str):
    lines = raw.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("{|")), None)
    if start is None:
        return None
    out = []
    for l in lines[start:start + 14]:
        out.append(l[:MAX_VALUE])
        if l.startswith("|}"):
            break
    if not out[-1].startswith("|}"):
        out.append("|}")
    return "\n".join(out)


SYN_SRC = ROOT / "test_fixtures" / "wiki_corpus" / "synthetic_sources.json"
SYN_OUT = ROOT / "test_fixtures" / "wiki_corpus" / "synthetic_manifest.json"


def build_synthetic() -> int:
    src = json.loads(SYN_SRC.read_text(encoding="utf-8"))["samples"]
    out = []
    for s in src:
        fmt = s.get("source_format", "mediawiki")
        row = {"evidence_type": "synthetic", "source_format": fmt, "excerpt_sha256": sha(s["excerpt_wikitext"]), **s}
        row.setdefault("source_format", fmt)
        if fmt == "mediawiki" and s["excerpt_wikitext"].startswith("{{"):
            try:
                row["fields"] = expected_fields(s["excerpt_wikitext"])
            except Exception:  # malformed sample: no reliable expectation
                row["fields"] = []
        out.append(row)
    SYN_OUT.write_text(json.dumps({"extract_version": EXTRACT_VERSION, "samples": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} synthetic samples -> {SYN_OUT}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--synthetic", action="store_true", help="regenerate synthetic manifest only (no DB needed)")
    a = ap.parse_args()
    if a.synthetic:
        return build_synthetic()
    if not a.db:
        ap.error("--db is required unless --synthetic")
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    samples, skipped = [], []
    for sid, src, title, kind, sel, tags, note in SPECS:
        row = con.execute(
            "select p.page_id,p.title,p.revision_id,p.revision_timestamp,d.raw_source,d.raw_hash "
            "from reference_wiki_pages p join reference_wiki_documents d using(source_id,page_id) "
            "where p.source_id=? and " + ("p.page_id=?" if title.startswith("id:") else "p.title=?"),
            (src, title[3:] if title.startswith("id:") else title)).fetchone()
        if not row:
            skipped.append((sid, "page/document not found"))
            continue
        page_id, ptitle, rev, rts, raw, rhash = row
        if kind == "template":
            res = template_excerpt(raw, sel)
            if not res:
                skipped.append((sid, "template not found"))
                continue
            excerpt, kept, omitted, tname = res
            detail = {"template": tname, "kept_params": kept, "omitted_params": omitted,
                      "fields": expected_fields(excerpt)}
        else:
            excerpt = table_excerpt(raw)
            if not excerpt:
                skipped.append((sid, "no table"))
                continue
            detail = {"table": True}
        quoted = ptitle.replace(" ", "_")
        samples.append({
            "sample_id": sid, "evidence_type": "real_excerpt", "source_wiki": src,
            "page_title": ptitle, "page_id": page_id,
            "source_url": SOURCES[src]["base"] + quoted, "revision_id": rev, "revision_timestamp": rts,
            "retrieved_at": None, "retrieval_note": "local snapshot import time not recorded per page",
            "raw_source_sha256": rhash, "raw_source_sha256_verified": sha(raw) == rhash,
            "raw_source_chars": len(raw), "license_note": SOURCES[src]["license"],
            "categories": tags, "note": note, "excerpt_kind": kind,
            "excerpt_wikitext": excerpt, "excerpt_sha256": sha(excerpt), **detail,
        })
    jp_samples = []
    for sid, title, idx, tags, note in JP_SPECS:
        row = con.execute(
            "select d.raw_source,d.raw_hash,d.retrieved_at,d.source_revision from reference_wiki_documents d "
            "where d.source_id='WikiWikiJP' and d.page_id=?", (title,)).fetchone()
        if not row or not row[0] or not row[2]:
            skipped.append((sid, "no raw source / retrieved_at (re-crawl the page first)"))
            continue
        raw, rhash, rat, rrev = row
        is_list = idx == "list"
        excerpt = html_list_excerpt(raw) if is_list else html_table_excerpt(raw, idx)
        if not excerpt:
            skipped.append((sid, "excerpt not found"))
            continue
        jp_samples.append({
            "sample_id": sid, "evidence_type": "real_excerpt", "source_wiki": "WikiWikiJP",
            "page_title": title, "page_id": title, "source_url": JP_BASE + urllib.parse.quote(title, safe="/"),
            "revision_id": "none-exposed", "revision_timestamp": None, "source_revision": rrev,
            "retrieved_at": rat, "retrieval_note": "revision id not exposed by PukiWiki HTML; retrieved_at recorded at crawl",
            "raw_source_sha256": rhash, "raw_source_sha256_verified": sha(raw) == rhash,
            "raw_source_chars": len(raw), "license_note": "terms not verified; minimal structural excerpt only, check before wider redistribution",
            "categories": tags, "note": note, "excerpt_kind": "html_list" if is_list else "html_table", "source_format": "html",
            "table_index": None if is_list else idx, "excerpt_wikitext": excerpt, "excerpt_sha256": sha(excerpt),
            "cells": [list(c) for c in html_cells(excerpt)],
        })
    JP_OUT.write_text(json.dumps({"extract_version": EXTRACT_VERSION, "samples": jp_samples}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(jp_samples)} JP samples -> {JP_OUT}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"extract_version": EXTRACT_VERSION, "samples": samples}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(samples)} samples -> {OUT}")
    for s in skipped:
        print("SKIPPED", s, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
