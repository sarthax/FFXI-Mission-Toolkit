#!/usr/bin/env python3
"""
build_npc_index.py -- Mission Toolkit GUI, Phase 1 continuation.

Indexes every zone's real client NPC/mob-name list (via dat-extractor --extract-id, using the
real POLUtils formula 6720+zoneid, confirmed against our own client -- Nyzul Isle's real npc list
resolves to ROM4\\1\\76.DAT, 866 entries, and includes VENDING_BOX=17093430 exact match) into
ffxi_zone_database.db. Ground-truth id<->name lookup straight from the client, no capture needed.

Also stores each npcid's `content_tag` from Topaz's own sql/npc_list.sql (NOT client data --
cross-referenced against Topaz's SQL at index time). content_tag is a real, schema-defined
server-side content-category enable/disable flag ('TOAU', 'SOA', etc.) -- it is NOT proof an
entity belongs to any specific mission in a shared zone (e.g. Nyzul Isle hosts Assault, ToAU
missions, and other battle content in the same physical zone). Stored here purely so it's visible
at a glance without a separate lookup -- see lookup_entity.py's own caution note on this same
point, learned the hard way during a real Nyzul sweep this session.

Usage:
    py -3 build_npc_index.py --zone Nyzul_Isle
    py -3 build_npc_index.py --all
    py -3 build_npc_index.py --lookup 17093430          # search across all indexed zones by id
    py -3 build_npc_index.py --lookup "Vending"          # or by name substring
"""
import argparse
import io
import json
import re
import sqlite3
import subprocess
import sys

import build_database
import settings
from pathlib import Path


TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
DAT_EXTRACTOR_EXE = TOOLS_ROOT / "vendor/dat-extractor/bin/Debug/net9.0/dat-extractor.exe"
DEFAULT_FFXI_PATH = "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"


def npclist_id_for_zone(zoneid: int) -> int:
    """Real POLUtils MassExtractor formula for the per-zone NPC/mob name list, confirmed against
    our client (6720+77=6797 -> Nyzul Isle's real list, 866 entries, VENDING_BOX id exact match)."""
    return 6720 + zoneid


def init_db(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS npc_names (
            zoneid INTEGER,
            npcid INTEGER,
            name TEXT,
            PRIMARY KEY (zoneid, npcid)
        )
    """)
    # Migrate an existing table from before content_tag existed -- must happen before the CREATE
    # INDEX below, which fails outright if the column doesn't exist yet on a pre-existing table.
    cols = [r[1] for r in con.execute("PRAGMA table_info(npc_names)").fetchall()]
    if "content_tag" not in cols:
        con.execute("ALTER TABLE npc_names ADD COLUMN content_tag TEXT")
    if "norm_name" not in cols:
        # Real client names are wildly inconsistent in punctuation/spacing across entities --
        # confirmed live: "Lamia No.13" (spaces, period, no underscore) and "Qiqirn_Treasure_Hunter"
        # (all underscores) both exist as real stored `name` values. Entity search only ever
        # matched the raw column, so typing the "other" style than whatever got extracted for that
        # specific entity silently found nothing. norm_name strips everything but a-z0-9 (same
        # normalize() already used for items_ours/lsb_* tables), so any spacing/punctuation/
        # underscore variant of the same real name converges to one comparable string.
        con.execute("ALTER TABLE npc_names ADD COLUMN norm_name TEXT")
        con.create_function("_normalize_for_backfill", 1, build_database.normalize)
        con.execute("UPDATE npc_names SET norm_name = _normalize_for_backfill(name) WHERE name IS NOT NULL")
    con.executescript("""
        CREATE INDEX IF NOT EXISTS idx_npc_names_id ON npc_names(npcid);
        CREATE INDEX IF NOT EXISTS idx_npc_names_name ON npc_names(name);
        CREATE INDEX IF NOT EXISTS idx_npc_names_tag ON npc_names(content_tag);
        CREATE INDEX IF NOT EXISTS idx_npc_names_norm ON npc_names(norm_name);
    """)
    con.commit()


NPC_LIST_ROW_RE = re.compile(
    r"INSERT INTO `npc_list` VALUES \("
    r"(\d+),'[^']*','[^']*',\d+,"
    r"[\-\d.]+,[\-\d.]+,[\-\d.]+,"  # pos_x, pos_y, pos_z (not needed here)
    r"\d+,\d+,\d+,\d+,\d+,\d+,\d+,\d+,0x[0-9A-Fa-f]+,\d+,"
    r"(NULL|'[^']*'),\d+\);"  # content_tag
)

_content_tag_cache: dict[int, str | None] | None = None


def load_content_tags() -> dict[int, str | None]:
    """Parses Topaz's own sql/npc_list.sql once for every npcid's content_tag -- loaded lazily
    and cached module-wide since this file is ~4MB and re-parsing it per zone would be wasteful
    across a --all run."""
    global _content_tag_cache
    if _content_tag_cache is not None:
        return _content_tag_cache
    tags: dict[int, str | None] = {}
    npc_list_path = TOPAZ_ROOT / "sql/npc_list.sql"
    if npc_list_path.exists():
        for line in npc_list_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = NPC_LIST_ROW_RE.search(line)
            if not m:
                continue
            npcid_str, tag = m.groups()
            tags[int(npcid_str)] = None if tag == "NULL" else tag.strip("'")
    _content_tag_cache = tags
    return tags


def resolve_zoneid(con: sqlite3.Connection, zone_folder_name: str) -> int | None:
    row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone_folder_name.upper(),)).fetchone()
    return row[0] if row else None


def extract_npclist(zoneid: int, ffxi_path: str) -> list[dict] | None:
    file_id = npclist_id_for_zone(zoneid)
    out_path = TOOLS_ROOT / "mission_reports" / "_npc_index_tmp" / f"{file_id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(DAT_EXTRACTOR_EXE), "--extract-id", ffxi_path, str(file_id), str(out_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not out_path.exists():
        print(f"    [!] extract-id {file_id} failed: {result.stdout.strip()} {result.stderr.strip()}")
        return None
    with open(out_path, encoding="utf-8-sig") as f:
        data = json.load(f)
    # MobListParser also matches ItemData/other 32-byte-aligned formats by coincidence on rare
    # files -- entry 0 being ('none', id 0) is MobListParser's own real-format signature (checked
    # in Program.cs), so a mismatch here means this file resolved to something else entirely.
    if not data or data[0].get("Text") != "none" or data[0].get("Index") != 0:
        print(f"    [!] file {file_id} did not parse as a MobList (unexpected header) -- skipping")
        return None
    return data


def index_zone_npcs(con: sqlite3.Connection, zoneid: int, ffxi_path: str, force: bool = False) -> int:
    if not force:
        existing = con.execute("SELECT COUNT(*) FROM npc_names WHERE zoneid = ?", (zoneid,)).fetchone()[0]
        if existing:
            return existing
    entries = extract_npclist(zoneid, ffxi_path)
    if entries is None:
        return 0
    con.execute("DELETE FROM npc_names WHERE zoneid = ?", (zoneid,))
    content_tags = load_content_tags()
    # OR REPLACE: a handful of real zone lists carry the same npcid twice (harmless duplicate
    # client-side slot reuse, not an extraction bug) -- last one wins, fine for a lookup index.
    con.executemany(
        "INSERT OR REPLACE INTO npc_names (zoneid, npcid, name, content_tag, norm_name) VALUES (?, ?, ?, ?, ?)",
        [
            (zoneid, e["Index"], e["Text"], content_tags.get(e["Index"]), build_database.normalize(e["Text"]))
            for e in entries if e["Index"] != 0
        ],
    )
    con.commit()
    return len(entries)


def process_zone(con: sqlite3.Connection, zone_folder_name: str, ffxi_path: str, force: bool):
    zoneid = resolve_zoneid(con, zone_folder_name)
    if zoneid is None:
        print(f"[{zone_folder_name}] could not resolve zoneid (not in zones table), skipping")
        return
    print(f"[{zone_folder_name}] zoneid={zoneid}, npc list file={npclist_id_for_zone(zoneid)}")
    count = index_zone_npcs(con, zoneid, ffxi_path, force=force)
    if count:
        print(f"  {count} real NPC/mob names indexed")


def lookup(con: sqlite3.Connection, query: str):
    if query.isdigit():
        rows = con.execute(
            "SELECT zoneid, npcid, name, content_tag FROM npc_names WHERE npcid = ?", (int(query),)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT zoneid, npcid, name, content_tag FROM npc_names WHERE name LIKE ? LIMIT 50",
            (f"%{query}%",),
        ).fetchall()
    if not rows:
        print("  no matches")
        return
    for zoneid, npcid, name, content_tag in rows:
        zname = con.execute("SELECT name FROM zones WHERE zoneid = ?", (zoneid,)).fetchone()
        zname = zname[0] if zname else "?"
        tag_suffix = f"  [content_tag={content_tag}]" if content_tag else ""
        print(f"  [{zname}] {npcid} = {name!r}{tag_suffix}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", help="Zone folder name under scripts/zones (e.g. Nyzul_Isle)")
    ap.add_argument("--all", action="store_true", help="Process every zone in the zones table")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--lookup", help="Look up an npc id (exact) or name (substring) across all indexed zones")
    args = ap.parse_args()

    if not args.zone and not args.all and not args.lookup:
        ap.error("Specify --zone NAME, --all, or --lookup QUERY")

    con = sqlite3.connect(DB_PATH)
    init_db(con)

    if args.zone:
        process_zone(con, args.zone, args.ffxi_path, args.force)
    elif args.all:
        zones_dir = TOPAZ_ROOT / "scripts/zones" if TOPAZ_ROOT else None
        if not zones_dir or not zones_dir.is_dir():
            print("[build_npc_index] --all needs a real Topaz checkout (scripts/zones/ supplies the "
                  "per-zone worklist; nothing else in this toolkit currently provides an equivalent). "
                  f"Configured topaz_server_path: {TOPAZ_ROOT}")
            con.close()
            return
        for zone_dir in sorted(zones_dir.iterdir()):
            if zone_dir.is_dir():
                process_zone(con, zone_dir.name, args.ffxi_path, args.force)

    if args.lookup:
        print(f"\nLookup {args.lookup!r}:")
        lookup(con, args.lookup)

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
