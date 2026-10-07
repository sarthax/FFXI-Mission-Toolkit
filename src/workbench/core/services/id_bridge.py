#!/usr/bin/env python3
"""Bridge LSB/retail-era item and key-item research to Topaz ids by normalized name."""
from __future__ import annotations

import argparse
import re
import sqlite3

from workbench.runtime.paths import DATABASE_PATH

DB_PATH = DATABASE_PATH


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


TABLES = {
    "item": ("items_external", "items_ours", "itemid", "name"),
    "keyitem": ("keyitems_external", "keyitems_ours", "id", "const_name"),
}


def lookup(conn, kind: str, query: str = None, ext_id: int = None):
    ext_table, ours_table, ours_id_col, ours_name_col = TABLES[kind]

    if ext_id is not None:
        ext_rows = conn.execute(
            f"SELECT id, name, norm_name FROM {ext_table} WHERE id = ?", (ext_id,)
        ).fetchall()
    else:
        norm = normalize(query)
        ext_rows = conn.execute(
            f"SELECT id, name, norm_name FROM {ext_table} WHERE norm_name = ?", (norm,)
        ).fetchall()
        if not ext_rows:
            ext_rows = conn.execute(
                f"SELECT id, name, norm_name FROM {ext_table} WHERE norm_name LIKE ? LIMIT 10",
                (f"%{norm}%",),
            ).fetchall()

    if not ext_rows:
        print(f"No {kind} on the LSB/external side matches {query or ext_id!r}.")
        return

    for eid, ename, enorm in ext_rows:
        ours_exact = conn.execute(
            f"SELECT {ours_id_col}, {ours_name_col} FROM {ours_table} WHERE norm_name = ?",
            (enorm,),
        ).fetchall()
        ours_fuzzy = []
        if not ours_exact:
            ours_fuzzy = conn.execute(
                f"SELECT {ours_id_col}, {ours_name_col} FROM {ours_table} "
                f"WHERE norm_name LIKE ? OR ? LIKE '%' || norm_name || '%' LIMIT 5",
                (f"%{enorm}%", enorm),
            ).fetchall()
        ours_by_id = conn.execute(
            f"SELECT {ours_id_col}, {ours_name_col} FROM {ours_table} WHERE {ours_id_col} = ?",
            (eid,),
        ).fetchall()

        print(f"\nLSB/external: id={eid}  name={ename!r}")
        if ours_exact:
            for oid, oname in ours_exact:
                flag = "SAME id" if oid == eid else f"** ID SHIFTED ** (external id {eid} -> Topaz id {oid})"
                print(f"  -> Topaz match by NAME: id={oid} name={oname!r}   [{flag}]")
        elif ours_fuzzy:
            for oid, oname in ours_fuzzy:
                flag = "SAME id" if oid == eid else f"** ID SHIFTED ** (external id {eid} -> Topaz id {oid})"
                print(f"  -> Topaz FUZZY match: id={oid} name={oname!r}   [{flag}]  (verify manually)")
        else:
            print("  -> no Topaz entry with this name at all (not implemented, or named differently)")

        matched_ids = {oid for oid, _ in (ours_exact or ours_fuzzy)}
        if ours_by_id and ours_by_id[0][0] not in matched_ids:
            oid, oname = ours_by_id[0]
            print(
                f"  !! WARNING: Topaz id {eid} exists but is a DIFFERENT thing: {oname!r} "
                f"-- do NOT reuse this id by number alone."
            )


def drift_report(conn, kind: str, limit: int):
    """Report unambiguous 1:1 normalized-name matches whose ids differ."""
    ext_table, ours_table, ours_id_col, ours_name_col = TABLES[kind]

    ambiguous = conn.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT norm_name FROM {ext_table} GROUP BY norm_name HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    ambiguous_ours = conn.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT norm_name FROM {ours_table} GROUP BY norm_name HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    rows = conn.execute(f"""
        SELECT e.id, e.name, o.{ours_id_col}, o.{ours_name_col}
        FROM {ext_table} e
        JOIN {ours_table} o ON o.norm_name = e.norm_name
        WHERE o.{ours_id_col} != e.id
          AND e.norm_name IN (SELECT norm_name FROM {ext_table} GROUP BY norm_name HAVING COUNT(*) = 1)
          AND o.norm_name IN (SELECT norm_name FROM {ours_table} GROUP BY norm_name HAVING COUNT(*) = 1)
        ORDER BY e.name
        LIMIT ?
    """, (limit,)).fetchall()
    total = conn.execute(f"""
        SELECT COUNT(*) FROM {ext_table} e
        JOIN {ours_table} o ON o.norm_name = e.norm_name
        WHERE o.{ours_id_col} != e.id
          AND e.norm_name IN (SELECT norm_name FROM {ext_table} GROUP BY norm_name HAVING COUNT(*) = 1)
          AND o.norm_name IN (SELECT norm_name FROM {ours_table} GROUP BY norm_name HAVING COUNT(*) = 1)
    """).fetchone()[0]

    print(
        f"{kind}: {total} unambiguous 1:1 name matches where the id differs between LSB/external "
        f"and Topaz (showing up to {limit})."
    )
    print(
        f"({ambiguous} external names and {ambiguous_ours} Topaz names are shared by multiple rows "
        f"and excluded from this list -- use `{kind} --id N` to disambiguate those individually.)\n"
    )
    for ext_id, name, our_id, our_name in rows:
        print(f"  {name!r}: external id {ext_id}  ->  Topaz id {our_id} ({our_name!r})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    for kind in TABLES:
        p = sub.add_parser(kind, help=f"look up a {kind} by name or external id")
        p.add_argument("query", nargs="?", help="name to search for")
        p.add_argument("--id", type=int, dest="ext_id", help="look up by external (LSB) numeric id instead")

    dp = sub.add_parser("drift-report", help="list all name-matched id mismatches for a category")
    dp.add_argument("kind", choices=list(TABLES))
    dp.add_argument("--limit", type=int, default=50)

    args = ap.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"{DB_PATH} not found -- run `python -m workbench.devtools.indexing.build_database` first.")
    conn = sqlite3.connect(DB_PATH)

    if args.cmd == "drift-report":
        drift_report(conn, args.kind, args.limit)
    else:
        if not args.query and args.ext_id is None:
            raise SystemExit("provide a name or --id")
        lookup(conn, args.cmd, args.query, args.ext_id)


if __name__ == "__main__":
    main()
