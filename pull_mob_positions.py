#!/usr/bin/env python3
"""
pull_mob_positions.py -- finds real spawn positions for zero-position mob_spawn_points rows by
searching a capture's PathLog for a CSV file named after each mob id, and applies the first
(spawn) row's x/y/z/dir.

Usage:
    python pull_mob_positions.py <capture_dir> <mob_id> [<mob_id> ...] [--apply]

<capture_dir> should be the folder containing "Thris" (or similar) -- the script searches under
it for any PathLog/*/<zone>/<MobName>/<mob_id>.csv file recursively.
"""
import argparse
import csv
import re
from pathlib import Path

import settings

SQL_PATH = settings.get_topaz_root() / "sql/mob_spawn_points.sql"


def find_csv(capture_dir: Path, mob_id: int):
    matches = list(capture_dir.rglob(f"PathLog/**/{mob_id}.csv"))
    return matches[0] if matches else None


LUA_DB_ENTRY_RE = re.compile(
    r"\[(\d+)\]\s*=\s*\{.*?\['x'\]=([\-\d.]+),\s*\['y'\]=([\-\d.]+),\s*\['z'\]=([\-\d.]+),\s*\['r'\]=(\d+),"
)


def find_in_lua_dbs(capture_dir: Path, mob_ids: set):
    """Falls back to npclogger's Lua database format (used when no PathLog CSVs exist), e.g.
    D:\\...\\npclogger\\database\\<Zone>.lua or \\tables\\<Zone>.lua."""
    results = {}
    for lua_file in list(capture_dir.rglob("*/database/*.lua")) + list(capture_dir.rglob("*/tables/*.lua")):
        text = lua_file.read_text(encoding="utf-8", errors="ignore")
        for m in LUA_DB_ENTRY_RE.finditer(text):
            mid = int(m.group(1))
            if mid in mob_ids and mid not in results:
                x, y, z, rot = float(m.group(2)), float(m.group(3)), float(m.group(4)), int(m.group(5))
                results[mid] = (x, y, z, rot)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture_dir", type=Path)
    ap.add_argument("mob_ids", nargs="+", type=int)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    text = SQL_PATH.read_text(encoding="utf-8", errors="ignore")
    found, not_found = {}, []

    for mid in args.mob_ids:
        csv_path = find_csv(args.capture_dir, mid)
        if not csv_path:
            not_found.append(mid)
            continue
        rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
        if not rows:
            not_found.append(mid)
            continue
        r = rows[0]
        found[mid] = (float(r["x"]), float(r["y"]), float(r["z"]), int(float(r["dir"])))

    still_missing = set(args.mob_ids) - set(found)
    if still_missing:
        found.update(find_in_lua_dbs(args.capture_dir, still_missing))

    print(f"{len(found)} of {len(args.mob_ids)} mob ids found in capture data")
    applied = 0
    for mid, (x, y, z, rot) in found.items():
        m = re.search(rf"INSERT INTO `mob_spawn_points` VALUES \({mid},'([^']*)','([^']*)',(\d+),0,0,0,0\);", text)
        if not m:
            print(f"  !! {mid}: not a zero-position row (already fixed, or wrong id)")
            continue
        name, longname, poolid = m.groups()
        new_line = f"INSERT INTO `mob_spawn_points` VALUES ({mid},'{name}','{longname}',{poolid},{x},{y},{z},{rot});"
        print(f"  {mid} ({name}) -> ({x},{y},{z},{rot})")
        if args.apply:
            text = text[: m.start()] + new_line + text[m.end() :]
            applied += 1

    if not_found:
        print(f"\n{len(not_found)} mob ids with NO PathLog data in this capture: {not_found}")

    if args.apply and applied:
        SQL_PATH.write_text(text, encoding="utf-8", newline="")
        print(f"\nApplied {applied} fixes to {SQL_PATH}")


if __name__ == "__main__":
    main()
