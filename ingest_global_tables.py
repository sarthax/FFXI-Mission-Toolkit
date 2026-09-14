#!/usr/bin/env python3
"""
ingest_global_tables.py -- Mission Toolkit GUI, Phase 1 continuation.

Ingests POLUtils MassExtractor's cached, already-extracted global (non-zone-scoped) reference
tables from D:/Claude/FFXI-Tools/MassExtractor_output/ into ffxi_zone_database.db:
  - missions-assault.xml -> assault_missions (real client text: name + full mission-order text,
    per mission index -- matches this project's own mission numbering 1-50)
  - key-items.xml -> key_items (real client name/plural/description per key item id)

These are real client-extracted DMSGStringBlock dumps already sitting on disk (not re-extracted
here) -- this just loads them into queryable SQLite tables alongside the dialog/npc indexes
already built, per the Mission Toolkit GUI proposal's Phase 1 scope.

Usage:
    py -3 ingest_global_tables.py
    py -3 ingest_global_tables.py --mission 5      # print one mission's real text
    py -3 ingest_global_tables.py --keyitem "Zeruhn"   # search key items by name substring
"""
import argparse
import io
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import xi_tinkerer


TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
MASS_EXTRACTOR_DIR = TOOLS_ROOT / "MassExtractor_output"
DAT_EXTRACTOR_EXE = TOOLS_ROOT / "dat-extractor/bin/Debug/net9.0/dat-extractor.exe"
DEFAULT_FFXI_PATH = "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"

# 2026-09-06: real fix -- these two tables don't actually need MassExtractor at all. Both are
# DMSGStringBlock-format dats, the exact same format dialog/npc indexing already reads via
# xi_tinkerer's parse_dmsg_table -- confirmed live this session by resolving these real rom-file
# ids (dat-extractor/data/ROMFileMappings.xml) against the real client and checking the text:
# 55695 -> 3053 real key items ("Zeruhn report", "Kindred crest", ...), 55720 -> 128 real Assault
# missions ("Leujaoam Cleansing", "Counting Sheep", ...) matching this project's own established
# mission numbering exactly. Alternates are other ids the mapping file lists as resolving to the
# same logical table on different client builds/regions -- tried in order if the first doesn't
# resolve on a given client.
KEY_ITEMS_ROM_IDS = [55695, 55696, 55697, 55698, 55699, 55700, 55703, 55705, 55713, 55714]
ASSAULT_MISSIONS_ROM_IDS = [55720, 56260, 55840, 55600]


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS assault_missions (
            mission_id INTEGER PRIMARY KEY,
            name TEXT,
            full_text TEXT
        );
        CREATE TABLE IF NOT EXISTS key_items (
            keyitem_id INTEGER PRIMARY KEY,
            name TEXT,
            plural TEXT,
            description TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_key_items_name ON key_items(name);
    """)
    con.commit()


def field_text(thing_el: ET.Element, field_name: str) -> str:
    field = thing_el.find(f"./field[@name='{field_name}']")
    if field is None or field.text is None:
        return ""
    return field.text.strip()


def ingest_missions(con: sqlite3.Connection) -> int:
    path = MASS_EXTRACTOR_DIR / "missions-assault.xml"
    if not path.exists():
        print(f"  [!] {path} not found, skipping")
        return 0
    root = ET.parse(path).getroot()
    rows = []
    for thing in root.findall("./thing"):
        idx_field = thing.find("./field[@name='index']")
        if idx_field is None or idx_field.text is None:
            continue
        mission_id = int(idx_field.text.strip())
        if mission_id == 0:
            continue  # index 0 is the header/template entry, not a real mission
        name = field_text(thing, "string-2")
        full_text = field_text(thing, "string-3")
        if not name:
            continue
        rows.append((mission_id, name, full_text))
    con.executemany(
        "INSERT OR REPLACE INTO assault_missions (mission_id, name, full_text) VALUES (?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def ingest_key_items(con: sqlite3.Connection) -> int:
    path = MASS_EXTRACTOR_DIR / "key-items.xml"
    if not path.exists():
        print(f"  [!] {path} not found, skipping")
        return 0
    root = ET.parse(path).getroot()
    rows = []
    for thing in root.findall("./thing"):
        idx_field = thing.find("./field[@name='index']")
        if idx_field is None or idx_field.text is None:
            continue
        keyitem_id = int(idx_field.text.strip())
        if keyitem_id == 0:
            continue  # index 0 is the header/template entry
        name = field_text(thing, "string-5")
        plural = field_text(thing, "string-6")
        description = field_text(thing, "string-7")
        if not name:
            continue
        rows.append((keyitem_id, name, plural, description))
    con.executemany(
        "INSERT OR REPLACE INTO key_items (keyitem_id, name, plural, description) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def _resolve_rom_path(ffxi_path: str, rom_ids: list[int]) -> Path | None:
    """Tries each candidate rom-file id in turn via dat-extractor --resolve, returns the first
    that resolves to a real file on THIS client -- the right id can differ by client build/
    region, never assume the first one always works."""
    if not DAT_EXTRACTOR_EXE.exists():
        return None
    result = subprocess.run(
        [str(DAT_EXTRACTOR_EXE), "--resolve", ffxi_path, *[str(i) for i in rom_ids]],
        capture_output=True, text=True,
    )
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            path = Path(parts[1])
            if path.exists():
                return path
    return None


def ingest_key_items_from_client(con: sqlite3.Connection, ffxi_path: str) -> int:
    """Real replacement for ingest_key_items() -- pulls straight from the real client dat using
    tools already in this package (dat-extractor to resolve the real path, xi_tinkerer's native
    parse_dmsg_table to read it). No MassExtractor needed. See KEY_ITEMS_ROM_IDS' own comment for
    what was confirmed live."""
    path = _resolve_rom_path(ffxi_path, KEY_ITEMS_ROM_IDS)
    if not path:
        print("  [!] could not resolve the key items dat on this client, skipping")
        return 0
    result = xi_tinkerer.parse_dmsg_table(str(path))
    rows = []
    for entry in result["lists"].values():
        if len(entry) < 7:
            continue
        keyitem_id = entry[0].get("number")
        name = entry[4].get("string", "")
        plural = entry[5].get("string", "")
        description = entry[6].get("string", "")
        if not keyitem_id or not name:
            continue
        rows.append((keyitem_id, name, plural, description))
    con.executemany(
        "INSERT OR REPLACE INTO key_items (keyitem_id, name, plural, description) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def ingest_missions_from_client(con: sqlite3.Connection, ffxi_path: str) -> int:
    """Real replacement for ingest_missions() -- same real direct-from-client approach as
    ingest_key_items_from_client() above. See ASSAULT_MISSIONS_ROM_IDS' own comment for what was
    confirmed live."""
    path = _resolve_rom_path(ffxi_path, ASSAULT_MISSIONS_ROM_IDS)
    if not path:
        print("  [!] could not resolve the assault missions dat on this client, skipping")
        return 0
    result = xi_tinkerer.parse_dmsg_table(str(path))
    rows = []
    for entry in result["lists"].values():
        if len(entry) < 3:
            continue
        mission_id = entry[0].get("number")
        name = entry[1].get("string", "")
        full_text = entry[2].get("string", "")
        if not mission_id or not name:
            continue
        rows.append((mission_id, name, full_text))
    con.executemany(
        "INSERT OR REPLACE INTO assault_missions (mission_id, name, full_text) VALUES (?, ?, ?)",
        rows,
    )
    con.commit()
    return len(rows)


def normalize_name(name: str) -> str:
    """Same convention used throughout this toolkit (id_bridge.py, wiki_compile.py) for
    comparing a real display name against an ALL_CAPS Lua constant name."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_keyitem_readiness(con: sqlite3.Connection, keyitem_id: int, real_name: str,
                               table: str = "keyitems_ours") -> dict:
    """Cross-references one real client key item (from key_items, itself ingested from
    key-items.xml -- real DAT-sourced text) against a parsed key-item enum table -- by default
    `keyitems_ours`, which since CORE_AGNOSTIC_DESIGN.md's LSB-primary rework holds LSB's own
    scripts/enum/key_item.lua (xi.keyItem), parsed by build_database.py's load_keyitems_ours().
    Pass `table="topaz_keyitems"` to run the same check against the backport module's Topaz-side
    table instead (build_topaz_index.py's load_keyitems(), Topaz's own scripts/globals/keyitems.lua
    tpz.keyItem) -- same column shape (id, const_name, norm_name) on both tables, so the query
    itself doesn't change, only which table it targets.

    Two independent checks, since either can drift independently:
      - id_match: does the target enum have ANY constant at this exact real client id?
      - name_match: does the target enum have a constant whose name matches this item's real name,
        possibly at a totally different id? (This is how real id drift gets caught -- the
        project's own prior finding was 2,910 of 3,242 key items drifted between an external/LSB
        id and Topaz's real one; the same drift can exist between the real client id and the
        target enum's assigned value.)

    Status:
      clean      -- id_match and name_match agree (same constant, same id) -- genuinely ready
      drifted    -- name_match exists but at a different id than id_match (or id_match missing)
      wrong_name -- id_match exists but its name doesn't match this item's real name at all
                    (a different key item entirely occupies this id in the target enum)
      missing    -- neither an id nor a name match exists anywhere in the target enum
    """
    id_row = con.execute(
        f"SELECT const_name FROM {table} WHERE id = ?", (keyitem_id,)
    ).fetchone()
    norm = normalize_name(real_name)
    name_rows = con.execute(
        f"SELECT id, const_name FROM {table} WHERE norm_name = ?", (norm,)
    ).fetchall()

    id_match = id_row[0] if id_row else None
    name_match = None
    for nid, nconst in name_rows:
        if nid == keyitem_id:
            name_match = (nid, nconst)
            break
    if name_match is None and name_rows:
        name_match = name_rows[0]

    if id_match and name_match and name_match[0] == keyitem_id:
        status = "clean"
    elif name_match:
        status = "drifted"
    elif id_match:
        status = "wrong_name"
    else:
        status = "missing"

    return {
        "id_match": id_match,
        "name_match": name_match,
        "status": status,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mission", type=int, help="Print one Assault mission's real text by id (1-50)")
    ap.add_argument("--keyitem", help="Search key items by name substring")
    ap.add_argument("--ffxi-path", default=DEFAULT_FFXI_PATH,
                    help="Pull directly from your real client dat (no MassExtractor needed)")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    init_db(con)

    if not args.mission and not args.keyitem:
        n_missions = ingest_missions_from_client(con, args.ffxi_path) or ingest_missions(con)
        print(f"assault_missions: {n_missions} real missions ingested")
        n_keyitems = ingest_key_items_from_client(con, args.ffxi_path) or ingest_key_items(con)
        print(f"key_items: {n_keyitems} real key items ingested")

    if args.mission:
        row = con.execute(
            "SELECT name, full_text FROM assault_missions WHERE mission_id = ?", (args.mission,)
        ).fetchone()
        if not row:
            print(f"No mission {args.mission} found (ingest first by running with no args)")
        else:
            print(f"Mission {args.mission}: {row[0]}\n{row[1]}")

    if args.keyitem:
        rows = con.execute(
            "SELECT keyitem_id, name, description FROM key_items WHERE name LIKE ? LIMIT 20",
            (f"%{args.keyitem}%",),
        ).fetchall()
        if not rows:
            print("No matches")
        for kid, name, desc in rows:
            print(f"  [{kid}] {name}")
            print(f"    {desc[:100]!r}")

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
