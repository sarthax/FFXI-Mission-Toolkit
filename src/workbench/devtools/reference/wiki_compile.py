#!/usr/bin/env python3
"""BG Wiki content-readiness compiler for the Mission Toolkit.

Canonical implementation for the legacy root ``wiki_compile.py`` entry point. Behavior is kept
compatible while repository-owned paths and already-packaged dependencies are resolved through
the ``workbench`` package.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import sqlite3
import sys
import urllib.parse

import mwparserfromhell

from workbench.client.dat import global_tables as ingest_global_tables
from workbench.devtools.entities import profile as entity_profile
from workbench.devtools.reference import wiki_lookup
from workbench.runtime.legacy_settings import get_active_server_root
from workbench.runtime.paths import DATABASE_PATH, VENDOR_ROOT

TOPAZ_ROOT = get_active_server_root()
DB_PATH = DATABASE_PATH
DUMP_PATH = VENDOR_ROOT / "ffxi-wiki-dumps-dist" / "bg-wiki.jsonl.gz"

NON_ENTITY_PREFIXES = ("image:", "file:", "category:", "media:", "template:", "user:", "special:")


def title_from_query(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        path = urllib.parse.urlparse(raw).path
        raw = path.rsplit("/", 1)[-1]
    raw = urllib.parse.unquote(raw)
    return raw.replace("_", " ").strip()


def find_page(title_query: str) -> dict | None:
    if not DUMP_PATH.exists():
        raise SystemExit(f"{DUMP_PATH} not found.")
    title_query = title_from_query(title_query)
    q = title_query.lower()
    exact = None
    first_substring = None
    with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            if any(c.lower() == "catseyexi" for c in p.get("categories", [])):
                continue
            if p["title"].lower() == q:
                exact = p
                break
            if first_substring is None and q in p["title"].lower():
                first_substring = p
    return exact or first_substring


def extract_entity_links(wikitext: str) -> list[str]:
    wt = mwparserfromhell.parse(wikitext)
    names = []
    seen = set()
    for link in wt.filter_wikilinks():
        title = str(link.title).strip()
        if not title or title.lower().startswith(NON_ENTITY_PREFIXES):
            continue
        title = title.split("#", 1)[0].strip()
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(title)

    for template in wt.filter_templates():
        if str(template.name).strip().lower() != "item tooltip":
            continue
        if not template.params:
            continue
        title = str(template.params[0].value).strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(title)

    return names


def resolve_zone(con: sqlite3.Connection, name: str) -> list[tuple]:
    guess = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return con.execute("SELECT zoneid, name FROM zones WHERE name = ?", (guess,)).fetchall()


def resolve_npc(con: sqlite3.Connection, name: str) -> list[dict]:
    rows = con.execute(
        "SELECT DISTINCT npcid, name, zoneid FROM npc_names WHERE LOWER(name) = LOWER(?) LIMIT 10", (name,)
    ).fetchall()
    return [
        {
            "id": npcid,
            "name": real_name,
            "zoneid": zoneid,
            "zone_name": (con.execute("SELECT name FROM zones WHERE zoneid = ?", (zoneid,)).fetchone() or [None])[0],
            "wiring": entity_profile.get_wiring_status(con, npcid),
        }
        for npcid, real_name, zoneid in rows
    ]


def resolve_keyitem(con: sqlite3.Connection, name: str) -> list[dict]:
    rows = con.execute(
        "SELECT keyitem_id, name FROM key_items WHERE LOWER(name) = LOWER(?) LIMIT 10", (name,)
    ).fetchall()
    results = []
    for keyitem_id, real_name in rows:
        readiness = ingest_global_tables.resolve_keyitem_readiness(con, keyitem_id, real_name)
        results.append({"id": keyitem_id, "name": real_name, "readiness": readiness})
    return results


ITEM_ROW_RE = re.compile(r"INSERT INTO `item_basic` VALUES \((\d+),\d+,'([^']*)'")


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


_item_basic_cache: dict[str, list[tuple]] | None = None


def load_item_basic() -> dict[str, list[tuple]]:
    global _item_basic_cache
    if _item_basic_cache is not None:
        return _item_basic_cache
    cache: dict[str, list[tuple]] = {}
    path = TOPAZ_ROOT / "sql/item_basic.sql"
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = ITEM_ROW_RE.search(line)
            if not m:
                continue
            itemid, raw_name = int(m.group(1)), m.group(2)
            cache.setdefault(normalize(raw_name), []).append((itemid, raw_name))
    _item_basic_cache = cache
    return cache


def resolve_item(name: str) -> list[tuple]:
    return load_item_basic().get(normalize(name), [])


WANTED_SECTIONS = ["Walkthrough", "Strategy", "Notes", "Plot Details", "Boss Fight", "Eligibility"]


def extract_wiki_sections(wikitext: str) -> dict[str, str]:
    wt = mwparserfromhell.parse(wikitext)
    found = {}
    for section in wt.get_sections(include_headings=True, flat=True):
        headings = section.filter_headings()
        if not headings:
            continue
        title = str(headings[0].title).strip()
        if title not in WANTED_SECTIONS:
            continue
        body = str(section)
        body = re.sub(r"^\s*=+[^=]+=+\s*", "", body, count=1)
        cleaned = wiki_lookup.clean_wikitext(body).strip()
        if cleaned:
            found[title] = cleaned
    return found


def get_excerpt(con: sqlite3.Connection, page_title: str, wikitext: str) -> dict:
    client_row = con.execute(
        "SELECT full_text FROM assault_missions WHERE LOWER(name) = LOWER(?)", (page_title,)
    ).fetchone()
    client_text = client_row[0] if client_row else None
    sections = extract_wiki_sections(wikitext)
    if not client_text and not sections:
        cleaned = wiki_lookup.clean_wikitext(wikitext)
        return {
            "client_text": None,
            "sections": {},
            "fallback_source": "wiki text (BG Wiki, reference only -- no Walkthrough/Notes/etc. section found)",
            "fallback_text": cleaned[:1500],
        }
    return {"client_text": client_text, "sections": sections, "fallback_source": None, "fallback_text": None}


def compile_report(con: sqlite3.Connection, title_query: str) -> dict:
    resolved_title = title_from_query(title_query)
    page = find_page(title_query)
    if page is None:
        return {"error": f"No wiki page found matching {resolved_title!r} (resolved from input {title_query!r})"}

    excerpt = get_excerpt(con, page["title"], page["wikitext"])
    names = extract_entity_links(page["wikitext"])
    rows = []
    kind_order = ["zone", "npc/mob", "key item", "item"]
    sections: dict[str, list] = {k: [] for k in kind_order}
    not_found_names = []

    for name in names:
        candidates = []
        for kind, resolver in (
            ("zone", lambda n: resolve_zone(con, n)),
            ("npc/mob", lambda n: resolve_npc(con, n)),
            ("key item", lambda n: resolve_keyitem(con, n)),
            ("item", resolve_item),
        ):
            hits = resolver(name)
            if hits:
                candidates.append((kind, hits))

        total_hits = sum(len(hits) for _, hits in candidates)
        if total_hits == 0:
            status = "not_found"
        elif total_hits == 1:
            status = "found"
        else:
            status = "ambiguous"

        rows.append({"name": name, "status": status, "candidates": candidates})
        if not candidates:
            not_found_names.append(name)
        else:
            for kind, hits in candidates:
                sections[kind].append({"name": name, "status": status, "hits": hits})

    return {
        "title": page["title"],
        "url": page["url"],
        "rows": rows,
        "excerpt": excerpt,
        "sections": [(k, sections[k]) for k in kind_order if sections[k]],
        "not_found_names": not_found_names,
        "counts": {
            "found": sum(1 for r in rows if r["status"] == "found"),
            "ambiguous": sum(1 for r in rows if r["status"] == "ambiguous"),
            "not_found": sum(1 for r in rows if r["status"] == "not_found"),
        },
    }


STATUS_ICON = {"found": "\u2705", "ambiguous": "\u2753", "not_found": "\U0001F534"}


def _keyitem_note(h: dict) -> str:
    rd = h["readiness"]
    if rd["status"] == "clean":
        return f"`tpz.keyItem.{rd['id_match']}` -- ready"
    if rd["status"] == "drifted":
        return (
            f"`tpz.keyItem.{rd['name_match'][1]}` "
            f"(real id {rd['name_match'][0]}, NOT {h['id']} -- drifted, verify before using)"
        )
    if rd["status"] == "wrong_name":
        return f"id {h['id']} exists in Topaz but as a **different** key item -- do not reuse"
    return "**NOT implemented** in Topaz's keyitems.lua"


def to_markdown(report: dict) -> str:
    if "error" in report:
        return f"# Wiki Handoff: error\n\n{report['error']}\n"

    lines = []
    lines.append(f"# Wiki Handoff: {report['title']}")
    lines.append(f"Source: {report['url']}")
    lines.append("Reference only -- verify anything load-bearing before relying on it.\n")

    ex = report["excerpt"]
    if ex["client_text"]:
        lines.append("## Mission text (real client text, missions-assault.xml)")
        lines.append(ex["client_text"].strip())
        lines.append("")
    for heading, body in ex["sections"].items():
        lines.append(f"## {heading} (wiki text, BG Wiki -- reference only)")
        lines.append(body.strip())
        lines.append("")
    if ex["fallback_text"]:
        lines.append(f"## Page text ({ex['fallback_source']})")
        lines.append(ex["fallback_text"].strip())
        lines.append("")

    lines.append("## Resolved entities\n")
    for kind, entries in report["sections"]:
        lines.append(f"### {kind.title()} ({len(entries)})")
        for e in entries:
            icon = STATUS_ICON[e["status"]]
            for h in e["hits"]:
                if kind == "key item":
                    lines.append(
                        f"- {icon} **{e['name']}** -> key item id `{h['id']}` ({h['name']!r}) -- {_keyitem_note(h)}"
                    )
                elif kind == "npc/mob":
                    zone_display = f"{h['zoneid']} ({h['zone_name']})" if h.get("zone_name") else h["zoneid"]
                    lines.append(
                        f"- {icon} **{e['name']}** -> npc/mob id `{h['id']}` ({h['name']!r}), "
                        f"zone {zone_display} -- {h['wiring']}"
                    )
                elif kind == "zone":
                    lines.append(f"- {icon} **{e['name']}** -> zoneid `{h[0]}` (`{h[1]}`)")
                else:
                    lines.append(f"- {icon} **{e['name']}** -> item id `{h[0]}` (`{h[1]}`)")
        lines.append("")

    if report["not_found_names"]:
        lines.append(f"## Gaps -- not found anywhere in Topaz ({len(report['not_found_names'])})")
        for name in report["not_found_names"]:
            lines.append(
                f"- \U0001F534 **{name}** -- no match in zones/npc_names/key_items/item_basic. "
                "Could be genuinely unimplemented, or a name-variant (punctuation, abbreviation, redirect) "
                "worth a manual check before assuming it's missing."
            )
        lines.append("")

    lines.append("## Do not treat as settled")
    lines.append(
        "This is BG Wiki content (player-written, may be stale or wrong-era) cross-referenced "
        "against Topaz's own real indexed data. The ids above are confirmed against Topaz's actual "
        "SQL/client dat -- but mission mechanics, exact dialogue, and drop rates are NOT verified. "
        "Check Topaz's own scripts/SQL directly before treating anything beyond the ids as fact."
    )
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title", help="Wiki page title (substring match if no exact hit)")
    ap.add_argument("--markdown", action="store_true", help="Print the pasteable handoff packet instead")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    report = compile_report(con, args.title)

    if args.markdown:
        print(to_markdown(report))
        con.close()
        return

    if "error" in report:
        print(report["error"])
        return

    print(f"=== {report['title']} ===")
    print(f"{report['url']}")
    c = report["counts"]
    print(
        f"{len(report['rows'])} real linked entities: {c['found']} found, "
        f"{c['ambiguous']} ambiguous, {c['not_found']} not found\n"
    )

    def keyitem_note(h):
        rd = h["readiness"]
        if rd["status"] == "clean":
            return f"tpz.keyItem.{rd['id_match']} -- ready"
        if rd["status"] == "drifted":
            return (
                f"tpz.keyItem.{rd['name_match'][1]} "
                f"(real id {rd['name_match'][0]}, not {h['id']} -- drifted)"
            )
        if rd["status"] == "wrong_name":
            return f"id {h['id']} exists in Topaz but as a DIFFERENT key item"
        return "NOT implemented in Topaz's keyitems.lua"

    for kind, entries in report["sections"]:
        print(f"--- {kind} ({len(entries)}) ---")
        for e in entries:
            icon = STATUS_ICON[e["status"]]
            for h in e["hits"]:
                if kind == "key item":
                    note = f"  {keyitem_note(h)}"
                elif kind == "npc/mob":
                    note = f"  [{h['wiring']}]"
                else:
                    note = ""
                print(f"  {icon} {e['name']}: {h}{note}")
        print()

    if report["not_found_names"]:
        print(f"--- not found ({len(report['not_found_names'])}) ---")
        for name in report["not_found_names"]:
            print(f"  {STATUS_ICON['not_found']} {name}")

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
