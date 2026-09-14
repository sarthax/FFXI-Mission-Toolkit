#!/usr/bin/env python3
"""
Ingests every AltanaView List/ CSV into a queryable SQLite database.

AltanaView (a compiled FFXI .DAT asset browser, source lost/no accompanying
source for the exe itself, though a partial source repo exists at
https://github.com/voliathon/AltanaViewer) organizes its own knowledge of the
client's ROM dat tree as ~191 plain-text CSVs under List/{Effect,Image,Music,
NPC,PC}/. These files carry NO universal FourCC/animation-name master list --
confirmed by direct binary inspection (2026-08-25, AltanaView.exe fully
UPX-unpacked and string-scanned, zero hits for any real emote name). What they
DO carry is real ROM tree location data: each row points at one or more
`<region>/<dir>/<file>[-<file2>]` locations, optionally labeled with a short
name (not always present -- many rows, especially "index.csv" summaries and
generic-named grabs like "Emote"/"Job Emotes", are unlabeled position ranges).

Per-model reality (confirmed by the user 2026-08-25): a given FourCC-style
code is NOT a global key -- each model/race/gender's own animation dat
re-defines its own local set of codes. This index therefore stores WHERE
things live (location groups, categories, per-race base offsets), not a
pretend universal code table. Use it to narrow down which dat range to
inspect for a given race/category, not to look up a code's meaning directly.

Usage: py -3 build_altana_index.py [--list-root <path to AltanaView List/>]
"""
import argparse
import csv
import re
import sqlite3
from pathlib import Path

DEFAULT_LIST_ROOT = r"C:\ValhallaXI\AltanaView-master\List"
DB_PATH = Path(__file__).parent / "altana_view_index.db"

# `<region>/<dir>/<file>` or `<region>/<dir>/<file1>-<file2>`, multiple groups
# joined by `;`.
LOCATION_GROUP_RE = re.compile(r"^\s*(\d+)/(\d+)/(\d+)(?:-(\d+))?\s*$")


def parse_location_refs(raw: str):
    """Splits a `;`-joined location-ref string into (region, dir, file_start, file_end) tuples."""
    groups = []
    for part in raw.split(";"):
        m = LOCATION_GROUP_RE.match(part)
        if m:
            region, dirn, file_start, file_end = m.groups()
            groups.append((int(region), int(dirn), int(file_start), int(file_end or file_start)))
    return groups


def build(list_root: Path, conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS altana_rows")
    cur.execute("DROP TABLE IF EXISTS altana_locations")
    cur.execute(
        """
        CREATE TABLE altana_rows (
            id INTEGER PRIMARY KEY,
            category TEXT,       -- top-level folder: Effect/Image/Music/NPC/PC
            subcategory TEXT,    -- immediate parent (race folder name, or csv basename for flat categories)
            section TEXT,        -- most recent "@Section" header above this row, if any
            row_order INTEGER,   -- 0-based position within its source file (dropdown order proxy)
            raw_locations TEXT,  -- original location-ref string, unparsed
            name TEXT,           -- label after the location refs; often empty for unlabeled rows
            source_csv TEXT      -- path relative to List/
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE altana_locations (
            row_id INTEGER,
            region INTEGER,
            dir INTEGER,
            file_start INTEGER,
            file_end INTEGER,
            FOREIGN KEY (row_id) REFERENCES altana_rows(id)
        )
        """
    )

    row_id = 0
    csv_files = sorted(list_root.rglob("*.csv"))
    for csv_path in csv_files:
        rel = csv_path.relative_to(list_root).as_posix()
        parts = rel.split("/")
        category = parts[0]
        subcategory = parts[1] if len(parts) > 2 else csv_path.stem

        section = None
        try:
            text = csv_path.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue

        for order, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            if line.startswith("@"):
                section = line[1:].strip()
                continue

            # First comma splits location-refs from the trailing name (names never
            # contain the location-ref charset, but MAY contain commas themselves --
            # take name as everything after the first comma).
            if "," in line:
                loc_part, name = line.split(",", 1)
            else:
                loc_part, name = line, ""

            row_id += 1
            cur.execute(
                "INSERT INTO altana_rows (id, category, subcategory, section, row_order, "
                "raw_locations, name, source_csv) VALUES (?,?,?,?,?,?,?,?)",
                (row_id, category, subcategory, section, order, loc_part.strip(), name.strip(), rel),
            )
            for region, dirn, fstart, fend in parse_location_refs(loc_part):
                cur.execute(
                    "INSERT INTO altana_locations (row_id, region, dir, file_start, file_end) "
                    "VALUES (?,?,?,?,?)",
                    (row_id, region, dirn, fstart, fend),
                )

    cur.execute("CREATE INDEX idx_rows_category ON altana_rows(category, subcategory)")
    cur.execute("CREATE INDEX idx_rows_name ON altana_rows(name)")
    cur.execute("CREATE INDEX idx_loc_dirfile ON altana_locations(dir, file_start, file_end)")
    conn.commit()
    print(f"Ingested {len(csv_files)} CSVs, {row_id} rows.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-root", default=DEFAULT_LIST_ROOT)
    args = ap.parse_args()

    list_root = Path(args.list_root)
    if not list_root.is_dir():
        raise SystemExit(f"List/ root not found: {list_root}")

    conn = sqlite3.connect(DB_PATH)
    build(list_root, conn)
    conn.close()
    print(f"Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
