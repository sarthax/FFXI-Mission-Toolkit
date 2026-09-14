"""
backport_sql_live_check.py -- run the SAME id-collision classification backport_sql_convert.py's
check_id_collisions() does, but against a REAL LIVE MySQL/MariaDB server (the actual DSP/Valhalla
target database), not this toolkit's own indexed snapshot.

Why this exists: DSP_TRANSITION_PLAN.md task 4 flags mob_groups (and, per the id-collision report
this session, mob_droplist too) as [NEEDS DBA/ADMIN] specifically because the renumbered ranges we
produced (mob_groups.groupid 14632-14731, mob_droplist.dropId 4587-4645, both free as of the
`old-dsp-reference` snapshot indexed in ffxi_zone_database.db) must be re-verified against the
ACTUAL LIVE target database before applying -- a real server can have grown its own groupid/dropId
space further since this snapshot was taken, and this script's whole job is closing that gap. We
don't have credentials to a live Valhalla-target database from this session -- this script is the
ready-to-run deliverable for whoever does.

Requires `mysql-connector-python` (NOT part of this toolkit's normal requirements.txt -- install it
yourself before running this: `py -3 -m pip install mysql-connector-python`). Deliberately kept as
a separate, optional dependency since only someone actually running this live check needs it.

Usage:
    py -3 backport_sql_live_check.py --host <host> --user <user> --password <pw> --database <db> \
        --package "D:\\Claude\\Topaz-Assault-Backport\\mission-packages\\nyzul_isle_investigation"

    # Or check one table/range directly without a package directory:
    py -3 backport_sql_live_check.py --host <host> --user <user> --password <pw> --database <db> \
        --table mob_groups --ids 14632-14731

What it does NOT do: write anything. This only ever runs SELECT queries -- it reports collisions,
it never applies the package's SQL for you. Applying is a separate, deliberate step for whoever
has write access, after reviewing this report.
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
        if args.package:
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
        elif args.table and args.ids:
            ids = parse_id_range(args.ids)
            result = check_live(cursor, args.table, ids, schema_map)
            print(f"=== {args.table} ({len(set(ids))} distinct id(s) checked: {args.ids}) ===")
            print(" ", result["note"])
            for u in result["unclassified"]:
                print(f"    live id already exists: {u['id']} (name: {u.get('live_name')})")
        else:
            ap.error("Provide either --package, or both --table and --ids.")
    finally:
        cursor.close()
        con.close()


if __name__ == "__main__":
    main()
