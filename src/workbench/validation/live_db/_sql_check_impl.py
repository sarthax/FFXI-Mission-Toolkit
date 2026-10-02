"""
backport_sql_live_check.py -- run the SAME id-collision AND content-duplication classification
backport_sql_convert.py's check_id_collisions()/check_content_duplication() do, but against a REAL
LIVE MySQL/MariaDB server (the actual DSP/Valhalla target database), not this toolkit's own indexed
snapshot.

Why this exists: DSP_TRANSITION_PLAN.md task 4 flags mob_groups (and, per the id-collision report
this session, mob_droplist too) as [NEEDS DBA/ADMIN] specifically because the renumbered ranges we
produced (mob_groups.groupid 14632-14731, mob_droplist.dropId 4587-4645, both free as of the
`old-dsp-reference` snapshot indexed in ffxi_zone_database.db) must be re-verified against the
ACTUAL LIVE target database before applying -- a real server can have grown its own groupid/dropId
space further since this snapshot was taken, and this script's whole job is closing that gap.

**2026-09-15 addition -- content duplication, not just id collision.** A real incident (see
D:\\Claude\\Topaz-Assault-Backport\\reports\\dsp_repair_2026-09-15\\INCIDENT_REPORT.md) showed that
id-collision checking alone is NOT sufficient for mob_groups: multiple backport passes each minted
a FRESH, genuinely-unused groupid for content a prior pass had already backported, so
check_id_collisions() reported "clear" every time while 195 live rows ended up silently pulling
wrong loot. This script now ALSO runs check_content_duplication() (keyed on (poolid, zoneid) for
mob_groups) and, unlike the offline version, can classify each match by REAL live impact -- does
the existing DSP row actually have live mob_spawn_points, does the candidate's dropid differ from
it -- the same classification used to diagnose and repair that incident, now runnable proactively
before a new package is ever applied.

Requires `mysql-connector-python` (NOT part of this toolkit's normal requirements.txt -- install it
yourself before using this: `py -3 -m pip install mysql-connector-python`). Deliberately kept as a
separate, optional dependency since only someone actually running this live check needs it.

Usage:
    py -3 backport_sql_live_check.py --host <host> --user <user> --password <pw> --database <db> \
        --package "D:\\Claude\\Topaz-Assault-Backport\\mission-packages\\nyzul_isle_investigation"

    # Or check one table/range directly without a package directory:
    py -3 backport_sql_live_check.py --host <host> --user <user> --password <pw> --database <db> \
        --table mob_groups --ids 14632-14731

    # Full live health scan for content duplication across the WHOLE table (not just a candidate
    # package) -- e.g. a periodic check that the 2026-09-15 incident hasn't recurred:
    py -3 backport_sql_live_check.py --host <host> --user <user> --password <pw> --database <db> \
        --scan-duplicates mob_groups

What it does NOT do: write anything. This only ever runs SELECT queries -- it reports collisions
and duplicates, it never applies a package's SQL or repairs anything for you. Applying/repairing is
a separate, deliberate step for whoever has write access, after reviewing this report.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import backport_sql_convert as bsc

TOOLS_ROOT = Path(__file__).resolve().parent

# Real table/column names to check live, per Topaz table name this toolkit already tracks in
# dsp_sql_schema_map.json -- reuses that map's id_column/name_column, but queries the REAL live
# table (e.g. `mob_groups`), not an indexed `dsp_mob_groups` snapshot table.
LIVE_TABLE = {
    "npc_list": "npc_list",
    "mob_pools": "mob_pools",
    "mob_droplist": "mob_droplist",
    "mob_spawn_points": "mob_spawn_points",
    "instance_entities": "instance_entities",
    "instance_list": "instance_list",
    "mob_groups": "mob_groups",
}


def parse_id_range(spec: str) -> list[int]:
    """'14632-14731' -> [14632, ..., 14731]. '1,2,3' -> [1,2,3]. A single number -> [that number]."""
    ids: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            ids.extend(range(int(lo), int(hi) + 1))
        elif part:
            ids.append(int(part))
    return ids


def check_live(cursor, table: str, ids: list[int], schema_map: dict,
                id_to_name: dict[int, str] | None = None) -> dict:
    """Same classification as backport_sql_convert.check_id_collisions, but querying a real live
    MySQL table directly (using %s placeholders, MySQL's paramstyle) instead of the sqlite-backed
    indexed snapshot."""
    spec = schema_map.get(table, {})
    id_col = spec.get("id_column")
    name_col = spec.get("name_column")
    live_table = LIVE_TABLE.get(table, table)
    if not id_col:
        return {"table": live_table, "id_column": id_col, "same_entity": [], "name_mismatch": [],
                "unclassified": [], "note": f"No id_column configured for `{table}` -- can't check."}

    distinct_ids = sorted(set(ids))
    if not distinct_ids:
        return {"table": live_table, "id_column": id_col, "same_entity": [], "name_mismatch": [],
                "unclassified": [], "note": "No ids to check."}

    placeholders = ",".join(["%s"] * len(distinct_ids))
    select_cols = f"{id_col}, {name_col}" if name_col else id_col
    cursor.execute(f"SELECT DISTINCT {select_cols} FROM `{live_table}` WHERE `{id_col}` IN ({placeholders})",
                   distinct_ids)
    dsp_rows = cursor.fetchall()

    seen: dict = {}
    for row in dsp_rows:
        seen.setdefault(row[0], row)
    dsp_rows = list(seen.values())

    same_entity, name_mismatch, unclassified = [], [], []
    for row in dsp_rows:
        cid = row[0]
        live_name = row[1] if name_col and len(row) > 1 else None
        expected_name = (id_to_name or {}).get(cid)
        if live_name is not None and expected_name is not None:
            if str(live_name) == str(expected_name):
                same_entity.append({"id": cid, "name": live_name})
            else:
                name_mismatch.append({"id": cid, "live_name": live_name, "our_name": expected_name})
        else:
            unclassified.append({"id": cid, "live_name": live_name})

    total = len(same_entity) + len(name_mismatch) + len(unclassified)
    note = f"{total} of {len(distinct_ids)} distinct id(s) already exist LIVE in `{live_table}`.{id_col}."
    if name_mismatch:
        note += f" {len(name_mismatch)} are REAL collisions (different entity already at that id)."
    if unclassified:
        note += f" {len(unclassified)} could not be name-classified (no name column) -- treat as real."
    if not total:
        note = f"CLEAR -- none of the {len(distinct_ids)} distinct id(s) checked exist live in `{live_table}`.{id_col}."

    return {"table": live_table, "id_column": id_col, "same_entity": same_entity,
            "name_mismatch": name_mismatch, "unclassified": unclassified, "note": note}


def load_package_ids(package_dir: Path, table: str, schema_map: dict) -> tuple[list[int], dict[int, str]]:
    """Parse a package's own sql/<table>.sql (the ORIGINAL Topaz ids, not the renumbered sql-dsp/
    output) to get every id + name this package uses -- so a DBA can check the package's real
    intended ids directly, without needing to already know a renumbered range."""
    sql_path = package_dir / "sql" / f"{table}.sql"
    if not sql_path.exists():
        return [], {}
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    rows = [r for t, r in bsc.parse_insert_values(text) if t == table]
    if not rows:
        return [], {}
    result = bsc.convert_table(table, rows, schema_map)
    ids = []
    for raw in result.converted_ids:
        try:
            ids.append(int(bsc._unquote(raw)))
        except ValueError:
            continue
    return ids, result.id_to_name


def load_package_rows(package_dir: Path, table: str) -> list[list[str]]:
    """Like load_package_ids, but returns the raw Topaz-shaped field-value rows (not converted
    ids) -- needed by check_live_content_duplication, which has to see multiple columns together
    (e.g. mob_groups' poolid AND zoneid) per row, not one flattened id list."""
    sql_path = package_dir / "sql" / f"{table}.sql"
    if not sql_path.exists():
        return []
    text = sql_path.read_text(encoding="utf-8", errors="replace")
    return [r for t, r in bsc.parse_insert_values(text) if t == table]


def check_live_content_duplication(cursor, table: str, rows: list[list[str]], schema_map: dict) -> dict:
    """Live equivalent of backport_sql_convert.check_content_duplication(), plus the real-impact
    classification the 2026-09-15 incident repair used: for each existing DSP row found at a
    candidate's content key, join mob_spawn_points to see whether it actually has live spawns, and
    compare its dropid against the candidate's. Classifies each duplicate as:
      - "harmless": existing row's dropid is 0 or matches the candidate's -- no loot-correctness
        risk either way.
      - "live_conflict": existing row HAS live spawns and its dropid DIFFERS from the candidate's
        -- the exact incident shape (one live, wrong-loot-risk duplicate about to be created).
      - "orphaned": existing row has ZERO live spawns -- safe to reuse/consolidate into, not
        currently affecting anything live.
      - "ambiguous": can't tell from id/dropid alone (e.g. existing row already has live spawns of
        its own AND a differing dropid, meaning it's already a real, separate entity -- needs a
        human look, likely NOT a bug, see the incident report's 27 false-positive cases where the
        same poolid legitimately spawns under different names at different positions).

    Only implemented for mob_groups today (the only table in CONTENT_KEY_COLUMNS) -- the
    spawn-count join below is mob_groups-specific (via mob_spawn_points.groupid).
    """
    key_cols = bsc.CONTENT_KEY_COLUMNS.get(table)
    spec = schema_map.get(table, {})
    topaz_cols = spec.get("topaz_columns", [])
    id_col = spec.get("id_column")
    live_table = LIVE_TABLE.get(table, table)

    if not key_cols or table != "mob_groups":
        return {"table": live_table, "content_key_columns": key_cols, "checked_count": 0,
                "duplicates": [],
                "note": f"Live content-duplication classification is only implemented for "
                        f"mob_groups today (table `{table}` requested)."}

    missing = [c for c in (*key_cols, id_col) if c not in topaz_cols]
    if missing:
        return {"table": live_table, "content_key_columns": key_cols, "checked_count": 0,
                "duplicates": [],
                "note": f"Schema map for `{table}` is missing column(s) {missing}."}

    key_idx = [topaz_cols.index(c) for c in key_cols]
    id_idx = topaz_cols.index(id_col)
    dropid_idx = topaz_cols.index("dropid") if "dropid" in topaz_cols else None

    checked = 0
    seen_keys: set[tuple] = set()
    duplicates: list[dict] = []
    for row in rows:
        if len(row) != len(topaz_cols):
            continue
        try:
            key_vals = tuple(int(bsc._unquote(row[i])) for i in key_idx)
            candidate_id = int(bsc._unquote(row[id_idx]))
            candidate_dropid = int(bsc._unquote(row[dropid_idx])) if dropid_idx is not None else None
        except ValueError:
            continue
        if key_vals in seen_keys:
            continue
        seen_keys.add(key_vals)
        checked += 1

        where = " AND ".join(f"`{c}` = %s" for c in key_cols)
        cursor.execute(f"SELECT groupid, dropid FROM `{live_table}` WHERE {where}", key_vals)
        existing_rows = cursor.fetchall()
        if not existing_rows:
            continue

        classified = []
        for existing_gid, existing_dropid in existing_rows:
            cursor.execute("SELECT COUNT(*) FROM `mob_spawn_points` WHERE `groupid` = %s", (existing_gid,))
            spawn_count = cursor.fetchone()[0]
            same_dropid = (candidate_dropid is not None and existing_dropid == candidate_dropid)
            if same_dropid or existing_dropid == 0:
                classification = "harmless"
            elif spawn_count == 0:
                classification = "orphaned"
            else:
                classification = "live_conflict"
            classified.append({
                "groupid": existing_gid, "dropid": existing_dropid, "spawn_count": spawn_count,
                "classification": classification,
            })
        if any(c["classification"] == "live_conflict" for c in classified) and len(classified) > 1:
            # multiple existing rows, at least one both live AND dropid-differing -- if more than
            # one of them is independently live, this is the "27 false positive" shape (legitimate
            # distinct spawn variants sharing a poolid), not the incident shape -- downgrade to
            # ambiguous rather than falsely flagging it the same as a real conflict.
            live_count = sum(1 for c in classified if c["spawn_count"] > 0)
            for c in classified:
                if c["classification"] == "live_conflict" and live_count > 1:
                    c["classification"] = "ambiguous"

        duplicates.append({
            "content_key": dict(zip(key_cols, key_vals)),
            "candidate_id": candidate_id, "candidate_dropid": candidate_dropid,
            "existing": classified,
        })

    n_conflict = sum(1 for d in duplicates for e in d["existing"] if e["classification"] == "live_conflict")
    note = (f"{len(duplicates)} of {checked} distinct content key(s) already have an existing live "
            f"DSP row. {n_conflict} classified as live_conflict (real wrong-loot risk, same shape "
            f"as the 2026-09-15 incident) -- do not apply this package as-is for those, resolve "
            f"first (reuse the existing groupid rather than inserting a new one).")
    if not duplicates:
        note = f"CLEAR -- none of the {checked} distinct content key(s) checked already exist live."

    return {"table": live_table, "content_key_columns": key_cols, "checked_count": checked,
            "duplicates": duplicates, "note": note}


def scan_live_duplicates(cursor, table: str) -> dict:
    """Full live-DB health scan for the 2026-09-15 incident class: are there ALREADY multiple
    groupids for the same (poolid, zoneid) in the live table right now, regardless of any
    candidate package? Unlike check_live_content_duplication (which checks a candidate package
    against what's live), this checks the live table against ITSELF -- meant to be run
    periodically/standalone to confirm the incident hasn't recurred, not just before a merge.
    Only implemented for mob_groups today, same reason as check_live_content_duplication."""
    if table != "mob_groups":
        return {"table": table, "note": f"Live duplicate scan is only implemented for mob_groups today (table `{table}` requested)."}

    cursor.execute("""
        SELECT poolid, zoneid, GROUP_CONCAT(groupid) FROM `mob_groups`
        GROUP BY poolid, zoneid HAVING COUNT(*) > 1
    """)
    dupe_keys = cursor.fetchall()

    live_conflict, orphaned_only, ambiguous = [], [], []
    for poolid, zoneid, gids_str in dupe_keys:
        gids = [int(g) for g in gids_str.split(",")]
        info = []
        for gid in gids:
            cursor.execute("SELECT dropid FROM `mob_groups` WHERE `groupid` = %s", (gid,))
            dropid = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM `mob_spawn_points` WHERE `groupid` = %s", (gid,))
            spawns = cursor.fetchone()[0]
            info.append({"groupid": gid, "dropid": dropid, "spawn_count": spawns})

        distinct_dropids = {g["dropid"] for g in info}
        live = [g for g in info if g["spawn_count"] > 0]
        entry = {"poolid": poolid, "zoneid": zoneid, "groups": info}

        if len(distinct_dropids) <= 1:
            continue  # harmless -- identical/zero dropid everywhere, not a loot-correctness risk
        elif len(live) == 1:
            live_conflict.append(entry)
        else:
            ambiguous.append(entry)

    note = (f"{len(dupe_keys)} (poolid, zoneid) pair(s) have 2+ live groupids. "
            f"{len(live_conflict)} classified live_conflict (real wrong-loot risk -- fix these). "
            f"{len(ambiguous)} ambiguous (2+ live groupids or none, likely a legitimate "
            f"same-poolid-different-variant case per the incident report's 27 false positives -- "
            f"review, don't auto-fix).")
    if not live_conflict and not ambiguous:
        note = f"CLEAR -- no live_conflict or ambiguous duplicate (poolid, zoneid) pairs found in `mob_groups`."

    return {"table": table, "total_duplicate_keys": len(dupe_keys),
            "live_conflict": live_conflict, "ambiguous": ambiguous, "note": note}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--database", required=True)
    ap.add_argument("--package", type=str, default=None,
                     help="Path to a mission package dir (has a sql/ subfolder) -- checks every "
                          "table it has against the live DB.")
    ap.add_argument("--table", type=str, default=None, help="Check just one table (with --ids or --range).")
    ap.add_argument("--ids", type=str, default=None,
                     help="Comma/range spec of ids to check for --table, e.g. '14632-14731' or '1,2,3'.")
    ap.add_argument("--scan-duplicates", type=str, default=None, metavar="TABLE",
                     help="Full live-DB content-duplication health scan for TABLE (only mob_groups "
                          "implemented today), independent of any candidate package -- run this "
                          "periodically to confirm the 2026-09-15 incident hasn't recurred.")
    args = ap.parse_args()

    try:
        import mysql.connector
    except ImportError:
        print("ERROR: mysql-connector-python is not installed. Run:\n"
              "  py -3 -m pip install mysql-connector-python\n"
              "before using this script (deliberately not part of this toolkit's normal "
              "requirements.txt -- see this file's own docstring).", file=sys.stderr)
        sys.exit(2)

    schema_map = bsc.load_schema_map()
    con = mysql.connector.connect(host=args.host, port=args.port, user=args.user,
                                   password=args.password, database=args.database)
    cursor = con.cursor()

    try:
        if args.scan_duplicates:
            result = scan_live_duplicates(cursor, args.scan_duplicates)
            print(f"=== {args.scan_duplicates} live content-duplication scan ===")
            print(" ", result["note"])
            for entry in result.get("live_conflict", []):
                print(f"    LIVE_CONFLICT poolid={entry['poolid']} zoneid={entry['zoneid']}: {entry['groups']}")
            for entry in result.get("ambiguous", []):
                print(f"    ambiguous poolid={entry['poolid']} zoneid={entry['zoneid']}: {entry['groups']}")
        elif args.package:
            package_dir = Path(args.package)
            for table in LIVE_TABLE:
                ids, id_to_name = load_package_ids(package_dir, table, schema_map)
                if not ids:
                    continue
                result = check_live(cursor, table, ids, schema_map, id_to_name=id_to_name)
                print(f"=== {table} ({len(set(ids))} distinct id(s) from this package's sql/{table}.sql) ===")
                print(" ", result["note"])
                for m in result["name_mismatch"]:
                    print(f"    MISMATCH id={m['id']}: live has '{m['live_name']}', package has '{m['our_name']}'")
                for u in result["unclassified"][:20]:
                    print(f"    unclassified (no name to compare) id={u['id']}")
                print()

                if table in bsc.CONTENT_KEY_COLUMNS:
                    rows = load_package_rows(package_dir, table)
                    dup_result = check_live_content_duplication(cursor, table, rows, schema_map)
                    print(f"=== {table} content-duplication check ({dup_result['checked_count']} distinct "
                          f"content key(s) from this package) ===")
                    print(" ", dup_result["note"])
                    for d in dup_result["duplicates"]:
                        for e in d["existing"]:
                            if e["classification"] in ("live_conflict", "ambiguous"):
                                print(f"    {e['classification'].upper()} content_key={d['content_key']} "
                                      f"candidate_id={d['candidate_id']} (dropid={d['candidate_dropid']}) "
                                      f"vs existing groupid={e['groupid']} (dropid={e['dropid']}, "
                                      f"spawns={e['spawn_count']})")
                    print()
        elif args.table and args.ids:
            ids = parse_id_range(args.ids)
            result = check_live(cursor, args.table, ids, schema_map)
            print(f"=== {args.table} ({len(set(ids))} distinct id(s) checked: {args.ids}) ===")
            print(" ", result["note"])
            for u in result["unclassified"]:
                print(f"    live id already exists: {u['id']} (name: {u.get('live_name')})")
        else:
            ap.error("Provide either --package, --scan-duplicates TABLE, or both --table and --ids.")
    finally:
        cursor.close()
        con.close()


if __name__ == "__main__":
    main()
