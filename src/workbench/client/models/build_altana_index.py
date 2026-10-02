#!/usr/bin/env python3
"""Build a queryable SQLite index from AltanaView ``List/`` CSV files.

AltanaView's list files describe ROM location groups and labels. They do not provide a universal
animation-code dictionary, so this index intentionally stores locations, categories, ordering,
and labels without inventing global FourCC semantics.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

from workbench.runtime.paths import REPO_ROOT

DEFAULT_LIST_ROOT = r"C:\ValhallaXI\AltanaView-master\List"
DB_PATH = REPO_ROOT / "altana_view_index.db"

LOCATION_GROUP_RE = re.compile(r"^\s*(\d+)/(\d+)/(\d+)(?:-(\d+))?\s*$")


def parse_location_refs(raw: str):
    """Split a ``;``-joined location string into integer location ranges."""
    groups = []
    for part in raw.split(";"):
        match = LOCATION_GROUP_RE.match(part)
        if match:
            region, dirn, file_start, file_end = match.groups()
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
            category TEXT,
            subcategory TEXT,
            section TEXT,
            row_order INTEGER,
            raw_locations TEXT,
            name TEXT,
            source_csv TEXT
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-root", default=DEFAULT_LIST_ROOT)
    args = ap.parse_args()

    list_root = Path(args.list_root)
    if not list_root.is_dir():
        raise SystemExit(f"List/ root not found: {list_root}")

    conn = sqlite3.connect(DB_PATH)
    try:
        build(list_root, conn)
    finally:
        conn.close()
    print(f"Wrote {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
