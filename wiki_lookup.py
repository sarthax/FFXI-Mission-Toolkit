#!/usr/bin/env python3
"""
wiki_lookup.py -- query the BG Wiki dump for quest/mob/item pages without asking the user to
paste wikitext by hand.

REFERENCE ONLY, NOT SOURCE OF TRUTH: wiki content is player-written and can be stale, wrong for
a specific era, or simply not match Topaz's own scripted behavior. Use it to orient (quest chain,
rough reward, walkthrough shape) then verify anything load-bearing (ids, exact dialogue, exact
mechanics) against Topaz's own SQL/Lua/dat-extractor output before relying on it.

Usage:
    python wiki_lookup.py title "Promotion: Lance Corporal"     # exact/substring title match
    python wiki_lookup.py title "Promotion: Lance Corporal" --raw   # dump full raw wikitext
    python wiki_lookup.py category Mission --limit 20           # list pages in a category
    python wiki_lookup.py category Mission --zone "Ilrusi Atoll" # AND filter on title/text
"""
import argparse
import gzip
import json
import re
from pathlib import Path

DUMP_PATH = Path(__file__).parent / "vendor/ffxi-wiki-dumps-dist/bg-wiki.jsonl.gz"


def load_pages():
    if not DUMP_PATH.exists():
        raise SystemExit(f"{DUMP_PATH} not found.")
    with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            # CatsEyeXI is a different private server's custom content, documented on the same
            # BG Wiki dump under this category -- not retail, never a source for Topaz/DSP work.
            if any(c.lower() == "catseyexi" for c in p.get("categories", [])):
                continue
            yield p


def clean_wikitext(text: str) -> str:
    """Strip the most common wiki markup so a walkthrough section reads as plain text.
    Not a full wikitext parser -- good enough for reading, not for re-publishing verbatim."""
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)          # templates/infoboxes
    # Category:/File:/Image: links carry no real reading content -- drop them entirely rather
    # than let the generic [[link|label]] rule below turn "[[Category:Bastok Quests]]" into the
    # bare, meaningless text "Category:Bastok Quests" leaking into the cleaned output (found
    # live: leaked straight into a real extracted Walkthrough section's body text).
    text = re.sub(r"\[\[\s*(?:Category|File|Image)\s*:[^\]]*\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)  # [[link|label]] -> label
    text = re.sub(r"'''?([^']+)'''?", r"\1", text)       # bold/italic
    text = re.sub(r"==+\s*([^=]+?)\s*==+", r"\n\1\n", text)  # headers
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cmd_title(args):
    q = args.query.lower()
    hits = [p for p in load_pages() if q in p["title"].lower()]
    if not hits:
        print(f"No page title contains {args.query!r}.")
        return
    for p in hits[: args.limit]:
        print(f"\n=== {p['title']} ===")
        print(f"url: {p['url']}")
        print(f"categories: {', '.join(p['categories'])}")
        print(f"last edited: {p['timestamp']}")
        body = p["wikitext"] if args.raw else clean_wikitext(p["wikitext"])
        print(body[: args.chars] + ("... [truncated]" if len(body) > args.chars else ""))


def cmd_category(args):
    hits = []
    for p in load_pages():
        if args.category not in p["categories"]:
            continue
        if args.zone and args.zone.lower() not in p["title"].lower() and args.zone.lower() not in p["wikitext"].lower():
            continue
        hits.append(p)
    print(f"{len(hits)} page(s) in category {args.category!r}" + (f" matching {args.zone!r}" if args.zone else ""))
    for p in hits[: args.limit]:
        print(f"  {p['title']}  ({p['url']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    tp = sub.add_parser("title", help="find page(s) by title substring")
    tp.add_argument("query")
    tp.add_argument("--raw", action="store_true", help="print raw wikitext instead of cleaned text")
    tp.add_argument("--limit", type=int, default=3)
    tp.add_argument("--chars", type=int, default=4000, help="max characters of body to print per page")
    tp.set_defaults(func=cmd_title)

    cp = sub.add_parser("category", help="list pages in a wiki category, optionally filtered")
    cp.add_argument("category", help="e.g. Mission, Quest, Notorious Monster, Item")
    cp.add_argument("--zone", help="substring filter on title or body (e.g. a zone name)")
    cp.add_argument("--limit", type=int, default=50)
    cp.set_defaults(func=cmd_category)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
