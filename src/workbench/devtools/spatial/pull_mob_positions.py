#!/usr/bin/env python3
"""Capture-backed mob spawn position recovery tooling.

Canonical implementation for the legacy root ``pull_mob_positions.py`` entry point.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from workbench.runtime.legacy_settings import get_active_server_root

SQL_PATH = get_active_server_root() / "sql" / "mob_spawn_points.sql"


def find_csv(capture_dir: Path, mob_id: int):
    matches = list(capture_dir.rglob(f"PathLog/**/{mob_id}.csv"))
    return matches[0] if matches else None


LUA_DB_ENTRY_RE = re.compile(
    r"\[(\d+)\]\s*=\s*\{.*?\['x'\]=([\-\d.]+),\s*\['y'\]=([\-\d.]+),\s*\['z'\]=([\-\d.]+),\s*\['r'\]=(\d+),"
)


def find_in_lua_dbs(capture_dir: Path, mob_ids: set):
    """Fall back to NPCLogger Lua databases when no PathLog CSV exists."""
    results = {}
    for lua_file in list(capture_dir.rglob("*/database/*.lua")) + list(capture_dir.rglob("*/tables/*.lua")):
        text = lua_file.read_text(encoding="utf-8", errors="ignore")
        for match in LUA_DB_ENTRY_RE.finditer(text):
            mob_id = int(match.group(1))
            if mob_id in mob_ids and mob_id not in results:
                x, y, z, rot = (
                    float(match.group(2)),
                    float(match.group(3)),
                    float(match.group(4)),
                    int(match.group(5)),
                )
                results[mob_id] = (x, y, z, rot)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument("mob_ids", nargs="+", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    text = SQL_PATH.read_text(encoding="utf-8", errors="ignore")
    found, not_found = {}, []

    for mob_id in args.mob_ids:
        csv_path = find_csv(args.capture_dir, mob_id)
        if not csv_path:
            not_found.append(mob_id)
            continue
        with csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            not_found.append(mob_id)
            continue
        row = rows[0]
        found[mob_id] = (
            float(row["x"]),
            float(row["y"]),
            float(row["z"]),
            int(float(row["dir"])),
        )

    still_missing = set(args.mob_ids) - set(found)
    if still_missing:
        found.update(find_in_lua_dbs(args.capture_dir, still_missing))

    print(f"{len(found)} of {len(args.mob_ids)} mob ids found in capture data")
    applied = 0
    for mob_id, (x, y, z, rot) in found.items():
        match = re.search(
            rf"INSERT INTO `mob_spawn_points` VALUES \({mob_id},'([^']*)','([^']*)',(\d+),0,0,0,0\);",
            text,
        )
        if not match:
            print(f"  !! {mob_id}: not a zero-position row (already fixed, or wrong id)")
            continue
        name, longname, poolid = match.groups()
        new_line = (
            f"INSERT INTO `mob_spawn_points` VALUES "
            f"({mob_id},'{name}','{longname}',{poolid},{x},{y},{z},{rot});"
        )
        print(f"  {mob_id} ({name}) -> ({x},{y},{z},{rot})")
        if args.apply:
            text = text[: match.start()] + new_line + text[match.end() :]
            applied += 1

    if not_found:
        print(f"\n{len(not_found)} mob ids with NO PathLog data in this capture: {not_found}")

    if args.apply and applied:
        SQL_PATH.write_text(text, encoding="utf-8", newline="")
        print(f"\nApplied {applied} fixes to {SQL_PATH}")


if __name__ == "__main__":
    main()
