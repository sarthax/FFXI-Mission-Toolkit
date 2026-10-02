#!/usr/bin/env python3
"""Cross-reference anonymous server prop rows with client door/object positions.

Canonical implementation for the legacy root ``fix_zone_door_props.py`` entry point.
"""
from __future__ import annotations

import argparse
import json
import math
import re

from workbench.runtime.legacy_settings import get_active_server_root
from workbench.runtime.paths import repo_path

NPC_LIST_PATH = get_active_server_root() / "sql" / "npc_list.sql"
DOOR_JSON_PATH = repo_path("FFXI-DATS", "Info", "Door or Objects.json")
ENTITIES_DIR = repo_path("FFXI-DATS", "Entities")

GENERIC_PROP_RE = re.compile(r"^_[0-9a-zA-Z]{2,5}$")
CONFIDENCE_THRESHOLD = 10.0


def load_valid_ids(zoneid: int) -> set:
    path = ENTITIES_DIR / f"{zoneid}.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {entry["serverID"] for entry in data.get("entities", [])}


def load_door_props(zoneid: int):
    data = json.loads(DOOR_JSON_PATH.read_text(encoding="utf-8"))
    return [entry for entry in data if entry.get("ZoneId") == zoneid]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("zoneid", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    valid_ids = load_valid_ids(args.zoneid)
    doors = load_door_props(args.zoneid)
    print(f"zone {args.zoneid}: {len(valid_ids)} known entity ids, {len(doors)} real door/object positions")

    sql_text = NPC_LIST_PATH.read_text(encoding="utf-8", errors="ignore")
    rows = []
    for match in re.finditer(
        r"INSERT INTO `npc_list` VALUES \((\d+),'([^']*)','([^']*)',(\d+),([\-\d.]+),([\-\d.]+),([\-\d.]+),",
        sql_text,
    ):
        npc_id, name, longname, _unk, x, y, z = match.groups()
        npc_id = int(npc_id)
        if npc_id not in valid_ids or not GENERIC_PROP_RE.match(name):
            continue
        rows.append((npc_id, name, longname, x, y, z, float(x), float(z)))

    print(f"{len(rows)} candidate generic-prop rows found in npc_list.sql for this zone")
    if not rows or not doors:
        print("Nothing to do.")
        return

    pairs = []
    for row in rows:
        npc_id = row[0]
        for entry in doors:
            dist = math.hypot(entry["X"] - row[6], entry["Z"] - row[7])
            pairs.append((dist, npc_id, entry))
    pairs.sort(key=lambda item: item[0])

    assigned_npc, assigned_real, final = set(), set(), {}
    for dist, npc_id, entry in pairs:
        ident = entry["Identifier"].strip()
        if npc_id in assigned_npc or ident in assigned_real:
            continue
        assigned_npc.add(npc_id)
        assigned_real.add(ident)
        final[npc_id] = (ident, entry, dist)

    post_fix_names = {}
    for npc_id, name, _longname, _x, _y, _z, _fx, _fz in rows:
        ident, _entry, dist = final[npc_id]
        is_ambiguous = dist >= CONFIDENCE_THRESHOLD
        post_fix_names[npc_id] = (name if is_ambiguous else ident, is_ambiguous)

    seen, renamed_out_of_the_way = {}, {}
    for npc_id, (name, is_ambiguous) in post_fix_names.items():
        if name not in seen:
            seen[name] = (npc_id, is_ambiguous)
            continue
        other_id, other_ambiguous = seen[name]
        if is_ambiguous and not other_ambiguous:
            renamed_out_of_the_way[npc_id] = f"_dup{npc_id}"
        elif other_ambiguous and not is_ambiguous:
            renamed_out_of_the_way[other_id] = f"_dup{other_id}"
        else:
            print(
                f"\n!! Unresolvable name collision between {npc_id} and {other_id} on '{name}' "
                "-- aborting, nothing written."
            )
            return

    if renamed_out_of_the_way:
        print(f"\n{len(renamed_out_of_the_way)} ambiguous row(s) renamed out of the way to avoid a name collision:")
        for npc_id, placeholder in renamed_out_of_the_way.items():
            print(f"  {npc_id} -> {placeholder}")

    new_text = sql_text
    applied, skipped = 0, []
    for npc_id, name, longname, x, y, z, _fx, _fz in rows:
        ident, entry, dist = final[npc_id]
        if dist >= CONFIDENCE_THRESHOLD and npc_id not in renamed_out_of_the_way:
            skipped.append((npc_id, name, ident, dist))
            continue

        if npc_id in renamed_out_of_the_way:
            new_name = renamed_out_of_the_way[npc_id]
            new_longname = new_name if longname == name else longname
            new_x, new_y, new_z = x, y, z
            changed = "renamed-out-of-the-way (ambiguous/no confident match)"
        else:
            new_name = ident
            new_longname = longname if longname not in (name,) else ident
            new_x, new_y, new_z = f"{entry['X']:.4f}", f"{entry['Y']:.4f}", f"{entry['Z']:.4f}"
            changed = "RENAME" if ident != name else ("reposition" if dist > 0.01 else "unchanged")

        print(f"  {npc_id} {name:8s} -> {new_name:8s} dist={dist:6.2f} {changed}")
        if args.apply:
            pattern = re.compile(
                rf"INSERT INTO `npc_list` VALUES \({npc_id},'{re.escape(name)}','{re.escape(longname)}',(\d+),[\-\d.]+,[\-\d.]+,[\-\d.]+,"
            )

            def repl(match, new_name=new_name, new_longname=new_longname, new_x=new_x, new_y=new_y, new_z=new_z):
                unk = match.group(1)
                return (
                    f"INSERT INTO `npc_list` VALUES ({npc_id},'{new_name}','{new_longname}',"
                    f"{unk},{new_x},{new_y},{new_z},"
                )

            new_text, count = pattern.subn(repl, new_text)
            if count != 1:
                print(f"    !! failed to patch npc_id {npc_id} -- {count} matches")
            else:
                applied += 1

    print(f"\n{'Applied' if args.apply else 'Would apply'}: {applied if args.apply else len(rows) - len(skipped)} fixes")
    print(f"Skipped (truly no candidate, left untouched): {len(skipped)}")
    for npc_id, name, ident, dist in skipped:
        print(f"  {npc_id} {name} -- nearest leftover: {ident}, dist={dist:.1f}")

    if args.apply and applied:
        NPC_LIST_PATH.write_text(new_text, encoding="utf-8", newline="")
        print(f"\nWrote {applied} fixes to {NPC_LIST_PATH}")


if __name__ == "__main__":
    main()
