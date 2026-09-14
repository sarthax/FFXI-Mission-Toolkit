#!/usr/bin/env python3
"""
fix_zone_door_props.py -- generalized version of the Mamool Ja Training Grounds door-prop fix.

For a given topaz zoneid, cross-references npc_list.sql's generic anonymous prop rows (leading
underscore, short identifier, e.g. "_jue", "_1u1") against FFXI-DATS' real client door/object
positions (D:\\Claude\\FFXI-Tools\\FFXI-DATS\\Info\\Door or Objects.json), using a one-to-one
nearest-neighbor XZ match (confirmed identity transform for X/Y/Z, see
ffxi_client_to_topaz_coord_transform memory) to detect and fix identifier/position drift.

Candidate rows are restricted to ids that FFXI-DATS' own Entities/<zoneid>.json lists for this
zone (ground truth for "this id belongs to this zone") AND whose current name matches a generic
anonymous-prop pattern -- named/quest-critical NPCs are never touched.

Usage:
    python fix_zone_door_props.py <zoneid> [--apply]

Without --apply, only prints the report (dry run). With --apply, writes the fix into
C:\\topaz\\sql\\npc_list.sql (back it up first).
"""
import argparse
import json
import math
import re
from pathlib import Path

import settings

TOOLS_ROOT = Path(__file__).parent
NPC_LIST_PATH = settings.get_topaz_root() / "sql/npc_list.sql"
DOOR_JSON_PATH = TOOLS_ROOT / "FFXI-DATS/Info/Door or Objects.json"
ENTITIES_DIR = TOOLS_ROOT / "FFXI-DATS/Entities"

GENERIC_PROP_RE = re.compile(r"^_[0-9a-zA-Z]{2,5}$")
CONFIDENCE_THRESHOLD = 10.0


def load_valid_ids(zoneid: int) -> set:
    f = ENTITIES_DIR / f"{zoneid}.json"
    if not f.exists():
        return set()
    data = json.loads(f.read_text(encoding="utf-8"))
    return {e["serverID"] for e in data.get("entities", [])}


def load_door_props(zoneid: int):
    data = json.loads(DOOR_JSON_PATH.read_text(encoding="utf-8"))
    return [e for e in data if e.get("ZoneId") == zoneid]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zoneid", type=int)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    valid_ids = load_valid_ids(args.zoneid)
    doors = load_door_props(args.zoneid)
    print(f"zone {args.zoneid}: {len(valid_ids)} known entity ids, {len(doors)} real door/object positions")

    sql_text = NPC_LIST_PATH.read_text(encoding="utf-8", errors="ignore")
    rows = []
    for m in re.finditer(
        r"INSERT INTO `npc_list` VALUES \((\d+),'([^']*)','([^']*)',(\d+),([\-\d.]+),([\-\d.]+),([\-\d.]+),",
        sql_text,
    ):
        npc_id, name, longname, unk, x, y, z = m.groups()
        npc_id = int(npc_id)
        if npc_id not in valid_ids:
            continue
        if not GENERIC_PROP_RE.match(name):
            continue
        rows.append((npc_id, name, longname, x, y, z, float(x), float(z)))

    print(f"{len(rows)} candidate generic-prop rows found in npc_list.sql for this zone")
    if not rows or not doors:
        print("Nothing to do.")
        return

    pairs = []
    for r in rows:
        npc_id = r[0]
        for e in doors:
            dist = math.hypot(e["X"] - r[6], e["Z"] - r[7])
            pairs.append((dist, npc_id, e))
    pairs.sort(key=lambda t: t[0])

    assigned_npc, assigned_real, final = set(), set(), {}
    for dist, npc_id, e in pairs:
        ident = e["Identifier"].strip()
        if npc_id in assigned_npc or ident in assigned_real:
            continue
        assigned_npc.add(npc_id)
        assigned_real.add(ident)
        final[npc_id] = (ident, e, dist)

    # Hard mechanical safety check computed BEFORE writing anything: no two rows in this zone's
    # npc_list block may end up with the same name after the fix, regardless of which data source
    # is "right" -- a name collision breaks name-dispatched trigger scripts (see
    # topaz_npc_name_drives_script_lookup memory). An "ambiguous" row keeps its old name; if that
    # collides with a confident row's new name, rename the ambiguous one out of the way with a
    # unique placeholder instead of blocking the whole zone -- it had no confident real match
    # anyway, so its old name wasn't trustworthy either.
    post_fix_names = {}
    for npc_id, name, longname, x, y, z, fx, fz in rows:
        ident, e, dist = final[npc_id]
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
            print(f"\n!! Unresolvable name collision between {npc_id} and {other_id} on '{name}' -- aborting, nothing written.")
            return

    if renamed_out_of_the_way:
        print(f"\n{len(renamed_out_of_the_way)} ambiguous row(s) renamed out of the way to avoid a name collision:")
        for npc_id, placeholder in renamed_out_of_the_way.items():
            print(f"  {npc_id} -> {placeholder}")

    new_text = sql_text
    applied, skipped = 0, []
    for npc_id, name, longname, x, y, z, fx, fz in rows:
        ident, e, dist = final[npc_id]
        if dist >= CONFIDENCE_THRESHOLD and npc_id not in renamed_out_of_the_way:
            skipped.append((npc_id, name, ident, dist))
            continue

        if npc_id in renamed_out_of_the_way:
            new_name = renamed_out_of_the_way[npc_id]
            new_longname = new_name if longname == name else longname
            new_x, new_y, new_z = x, y, z  # position untouched, only disambiguating the name
            changed = "renamed-out-of-the-way (ambiguous/no confident match)"
        else:
            new_name = ident
            new_longname = longname if longname not in (name,) else ident
            new_x, new_y, new_z = f"{e['X']:.4f}", f"{e['Y']:.4f}", f"{e['Z']:.4f}"
            changed = "RENAME" if ident != name else ("reposition" if dist > 0.01 else "unchanged")

        print(f"  {npc_id} {name:8s} -> {new_name:8s} dist={dist:6.2f} {changed}")
        if args.apply:
            pattern = re.compile(
                rf"INSERT INTO `npc_list` VALUES \({npc_id},'{re.escape(name)}','{re.escape(longname)}',(\d+),[\-\d.]+,[\-\d.]+,[\-\d.]+,"
            )
            def repl(m, new_name=new_name, new_longname=new_longname, new_x=new_x, new_y=new_y, new_z=new_z):
                unk = m.group(1)
                return f"INSERT INTO `npc_list` VALUES ({npc_id},'{new_name}','{new_longname}',{unk},{new_x},{new_y},{new_z},"
            new_text, n = pattern.subn(repl, new_text)
            if n != 1:
                print(f"    !! failed to patch npc_id {npc_id} -- {n} matches")
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
