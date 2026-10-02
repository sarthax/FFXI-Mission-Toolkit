#!/usr/bin/env python3
"""Global client DAT reference-table ingestion.

Canonical implementation for the historical ``ingest_global_tables.py`` utility.  Repository-owned
paths are resolved through ``workbench.runtime.paths`` and DAT resolution uses the packaged
Client/DAT extractor helper.
"""
from __future__ import annotations

import argparse
import io
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import xi_tinkerer
except ModuleNotFoundError:
    xi_tinkerer = None

from workbench.client.dat.extractor_bin import EXE as DAT_EXTRACTOR_EXE, ensure_dat_extractor
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT

DB_PATH = DATABASE_PATH
MASS_EXTRACTOR_DIR = REPO_ROOT / "MassExtractor_output"
DEFAULT_FFXI_PATH = "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"

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
            continue
        name = field_text(thing, "string-2")
        full_text = field_text(thing, "string-3")
        if name:
            rows.append((mission_id, name, full_text))
    con.executemany(
        "INSERT OR REPLACE INTO assault_missions (mission_id, name, full_text) VALUES (?, ?, ?)", rows
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
            continue
        name = field_text(thing, "string-5")
        plural = field_text(thing, "string-6")
        description = field_text(thing, "string-7")
        if name:
            rows.append((keyitem_id, name, plural, description))
    con.executemany(
        "INSERT OR REPLACE INTO key_items (keyitem_id, name, plural, description) VALUES (?, ?, ?, ?)", rows
    )
    con.commit()
    return len(rows)


def _resolve_rom_path(ffxi_path: str, rom_ids: list[int]) -> Path | None:
    ensure_dat_extractor()
    result = subprocess.run(
        [str(DAT_EXTRACTOR_EXE), "--resolve", ffxi_path, *[str(i) for i in rom_ids]],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            path = Path(parts[1])
            if path.exists():
                return path
    return None


def _require_xi_tinkerer():
    if xi_tinkerer is None:
        raise RuntimeError(
            "xi-tinkerer Python bindings are not available. Install/build xi-tinkerer before ingesting client DMSG tables."
        )
    return xi_tinkerer


def ingest_key_items_from_client(con: sqlite3.Connection, ffxi_path: str) -> int:
    path = _resolve_rom_path(ffxi_path, KEY_ITEMS_ROM_IDS)
    if not path:
        print("  [!] could not resolve the key items dat on this client, skipping")
        return 0
    result = _require_xi_tinkerer().parse_dmsg_table(str(path))
    rows = []
    for entry in result["lists"].values():
        if len(entry) < 7:
            continue
        keyitem_id = entry[0].get("number")
        name = entry[4].get("string", "")
        plural = entry[5].get("string", "")
        description = entry[6].get("string", "")
        if keyitem_id and name:
            rows.append((keyitem_id, name, plural, description))
    con.executemany(
        "INSERT OR REPLACE INTO key_items (keyitem_id, name, plural, description) VALUES (?, ?, ?, ?)", rows
    )
    con.commit()
    return len(rows)


def ingest_missions_from_client(con: sqlite3.Connection, ffxi_path: str) -> int:
    path = _resolve_rom_path(ffxi_path, ASSAULT_MISSIONS_ROM_IDS)
    if not path:
        print("  [!] could not resolve the assault missions dat on this client, skipping")
        return 0
    result = _require_xi_tinkerer().parse_dmsg_table(str(path))
    rows = []
    for entry in result["lists"].values():
        if len(entry) < 3:
            continue
        mission_id = entry[0].get("number")
        name = entry[1].get("string", "")
        full_text = entry[2].get("string", "")
        if mission_id and name:
            rows.append((mission_id, name, full_text))
    con.executemany(
        "INSERT OR REPLACE INTO assault_missions (mission_id, name, full_text) VALUES (?, ?, ?)", rows
    )
    con.commit()
    return len(rows)


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_keyitem_readiness(
    con: sqlite3.Connection, keyitem_id: int, real_name: str, table: str = "keyitems_ours"
) -> dict:
    id_row = con.execute(f"SELECT const_name FROM {table} WHERE id = ?", (keyitem_id,)).fetchone()
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
    return {"id_match": id_match, "name_match": name_match, "status": status}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mission", type=int, help="Print one Assault mission's real text by id (1-50)")
    ap.add_argument("--keyitem", help="Search key items by name substring")
    ap.add_argument(
        "--ffxi-path", default=DEFAULT_FFXI_PATH,
        help="Pull directly from your real client dat (no MassExtractor needed)",
    )
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
