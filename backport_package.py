#!/usr/bin/env python3
r"""
backport_package.py -- end-to-end orchestrator for backporting one Topaz package (a folder with
lua/ and optionally sql/) to a DSP target, chaining together every already-built per-file/per-table
tool instead of running each by hand: converts every .lua file (backport_lua_convert.py) and every
.sql file (backport_sql_convert.py), then runs the binding audit (backport_binding_audit.py), the
Lua sanity check (backport_lua_sanity_check.py), and the SQL id-collision check
(backport_sql_convert.check_id_collisions) over the WHOLE converted result, and emits one
consolidated report instead of four separate tool invocations to piece together by hand.

Package folder shape (same as backport-workspace/mission-packages/<name>/ and this project's own
Topaz-Assault-Backport/mission-packages/<name>/):
    <package_dir>/lua/**/*.lua   -- Topaz source, read-only input
    <package_dir>/sql/*.sql      -- Topaz SQL, read-only input (optional)
Output, mirroring the input trees:
    <package_dir>/lua-dsp/**/*.lua
    <package_dir>/sql-dsp/*.sql   (table name = file stem, e.g. npc_list.sql -> table `npc_list`)
    <package_dir>/BACKPORT_REPORT.md

What this does NOT do (an honest boundary, not an oversight):
  - Auto-discover WHICH files belong to a mission across zone/npc/mob/ability layers. That's a
    fundamentally different, harder problem this project already tried and rejected automating
    (see package_mission.py's own docstring: require() chains alone can't distinguish a genuine
    dependency from an unrelated zone's IDs.lua sitting in the same require() line). This tool
    operates on a package folder someone has already assembled -- the same starting point the
    GUI's Lua/SQL Converter pages assume one file at a time, just applied to a whole tree at once.
  - Per-file zone_table/id_shape auto-detection. The same --zone-table/--id-shape/--target apply
    to every .lua file in one run, same as manually running the GUI converter repeatedly with the
    same settings. A package spanning zones with genuinely different id-shape conventions needs
    separate runs per zone subfolder (or hand-editing the flagged output afterward) -- not solved
    here yet.
  - Deciding what a flagged line or a real binding gap actually means. Every flag/gap surfaces in
    the report for a human to resolve, the same "flag, don't guess" discipline as every other tool
    in this project.

Usage:
    py -3 backport_package.py backport-workspace/mission-packages/_example_godmode
    py -3 backport_package.py <package_dir> --target old_dsp_reference --id-shape flat
    py -3 backport_package.py <package_dir> --zone-table Periqia --id-file-hint IDs
    py -3 backport_package.py <package_dir> --dsp-root D:\some\other\old-dsp-reference
    py -3 backport_package.py <package_dir> --verify-only   # re-run just the 3 checks against an
                                                              # already-converted lua-dsp/, skip
                                                              # re-converting
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import backport_binding_audit as bba
import backport_lua_convert as blc
import backport_lua_sanity_check as blsc
import backport_sql_convert as bsc
import settings


def convert_lua_tree(src_root: Path, dst_root: Path, target: str, zone_table: str | None,
                      id_shape: str | None, id_file_hint: str | None) -> dict:
    """Converts every .lua file under src_root into the mirrored path under dst_root. Returns
    {"converted": [rel_paths], "flagged": [(rel_path, count)], "total_flags": int}."""
    converted, flagged = [], []
    total_flags = 0
    for src in sorted(src_root.rglob("*.lua")):
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        result = blc.convert(text, zone_table=zone_table, id_shape=id_shape,
                              id_file_hint=id_file_hint, target=target)
        dst.write_text(result.converted, encoding="utf-8", newline="\n")
        converted.append(str(rel))
        if result.flagged:
            flagged.append((str(rel), len(result.flagged)))
            total_flags += len(result.flagged)
    return {"converted": converted, "flagged": flagged, "total_flags": total_flags}


def convert_sql_tree(src_root: Path, dst_root: Path, schema_map: dict) -> dict:
    """Converts every .sql file under src_root (table name = file stem) into the mirrored path
    under dst_root. Returns {"converted": [rel_paths], "warnings": [...], "ids_by_table": {table:
    [raw_ids]}, "id_to_name_by_table": {table: {id: name}}, "rows_by_table": {table: [rows]}} --
    the last three feed the id-collision and content-duplication checks without re-parsing the
    converted output back out. rows_by_table keeps the ORIGINAL Topaz-shaped rows (not converted_sql
    text), since check_content_duplication() needs multiple raw columns together per row (e.g.
    mob_groups' poolid AND zoneid), not a flattened id list."""
    if not src_root.is_dir():
        return {"converted": [], "warnings": [], "ids_by_table": {}, "id_to_name_by_table": {},
                "rows_by_table": {}}

    converted, warnings = [], []
    ids_by_table: dict[str, list[str]] = {}
    id_to_name_by_table: dict[str, dict[int, str]] = {}
    rows_by_table: dict[str, list[list[str]]] = {}
    for src in sorted(src_root.glob("*.sql")):
        table = src.stem
        dst = dst_root / src.name
        dst_root.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        rows = [r for t, r in bsc.parse_insert_values(text) if t == table]
        if rows:
            rows_by_table.setdefault(table, []).extend(rows)
        result = bsc.convert_table(table, rows, schema_map)
        dst.write_text(result.converted_sql, encoding="utf-8", newline="\n")
        converted.append(src.name)
        for w in result.warnings:
            warnings.append({"file": src.name, **w})
        if result.converted_ids:
            ids_by_table.setdefault(table, []).extend(result.converted_ids)
            id_to_name_by_table.setdefault(table, {}).update(result.id_to_name)
    return {"converted": converted, "warnings": warnings, "ids_by_table": ids_by_table,
            "id_to_name_by_table": id_to_name_by_table, "rows_by_table": rows_by_table}


def run_id_collision_checks(ids_by_table: dict, id_to_name_by_table: dict, schema_map: dict) -> dict:
    """Runs backport_sql_convert.check_id_collisions for every table the SQL conversion touched,
    against the real indexed DSP data (ffxi_zone_database.db's dsp_* tables). Returns {table:
    result_dict}. Opens its own short-lived connection -- this is a one-shot CLI run, not a
    long-lived server."""
    if not ids_by_table:
        return {}
    con = sqlite3.connect(str(settings.DB_PATH))
    try:
        return {
            table: bsc.check_id_collisions(con, table, ids, schema_map,
                                            id_to_name=id_to_name_by_table.get(table))
            for table, ids in ids_by_table.items()
        }
    finally:
        con.close()


def run_content_duplication_checks(rows_by_table: dict, schema_map: dict) -> dict:
    """Runs backport_sql_convert.check_content_duplication for every table that has a
    CONTENT_KEY_COLUMNS entry (currently just mob_groups), against the real indexed DSP data.
    Added 2026-09-15 after a real incident (see D:\\Claude\\Topaz-Assault-Backport\\reports\\
    dsp_repair_2026-09-15\\INCIDENT_REPORT.md) where id-collision checking alone missed 195 rows of
    content that had already been backported under a DIFFERENT groupid in a prior pass -- every
    pass used a genuinely-free id, so run_id_collision_checks() reported clean every time. This is
    the offline (indexed-snapshot) check; for a real-impact classification (does the existing DSP
    row actually have live spawns, is the loot genuinely wrong) use backport_sql_live_check.py's
    --package mode against the real live server before applying anything this flags."""
    tables = [t for t in rows_by_table if t in bsc.CONTENT_KEY_COLUMNS]
    if not tables:
        return {}
    con = sqlite3.connect(str(settings.DB_PATH))
    try:
        return {
            table: bsc.check_content_duplication(con, table, rows_by_table[table], schema_map)
            for table in tables
        }
    finally:
        con.close()


def build_report(package_dir: Path, target: str, dsp_root: Path, flavor: str,
                  lua_result: dict | None, sql_result: dict | None,
                  binding_result: dict, sanity_result: dict, collision_results: dict,
                  duplication_results: dict | None = None, schema_map: dict | None = None) -> str:
    lines = [f"# Backport report -- {package_dir.name}", "",
              f"Target: `{dsp_root}` (detected flavor: `{flavor}`)", ""]

    if lua_result is not None:
        lines.append("## Lua conversion")
        lines.append(f"{len(lua_result['converted'])} file(s) converted, "
                      f"{lua_result['total_flags']} line(s) flagged across "
                      f"{len(lua_result['flagged'])} file(s).")
        for rel, count in lua_result["flagged"]:
            lines.append(f"- `{rel}` -- {count} flagged line(s)")
        lines.append("")

    if sql_result is not None and sql_result["converted"]:
        lines.append("## SQL conversion")
        lines.append(f"{len(sql_result['converted'])} file(s) converted.")
        if sql_result["warnings"]:
            lines.append(f"{len(sql_result['warnings'])} warning(s):")
            for w in sql_result["warnings"]:
                lines.append(f"- `{w['file']}` (`{w['table']}`): {w['reason']}")
        lines.append("")

    lines.append("## Binding audit")
    lines.append(f"{len(binding_result['confirmed'])} confirmed, "
                 f"{len(binding_result['missing'])} missing.")
    for name, reason, files in binding_result["missing"]:
        file_list = ", ".join(f.name for f in files[:3])
        more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
        lines.append(f"- MISSING `:{name}(` -- {reason} [used in: {file_list}{more}]")
    lines.append("")

    lines.append("## Lua sanity check")
    if sanity_result["syntax_errors"]:
        lines.append(f"{len(sanity_result['syntax_errors'])} syntax error(s):")
        for f, err in sanity_result["syntax_errors"]:
            lines.append(f"- `{f.name}`: {err}")
    if sanity_result["undeclared_globals"]:
        lines.append(f"{len(sanity_result['undeclared_globals'])} undeclared global reference(s):")
        for f, name in sanity_result["undeclared_globals"]:
            lines.append(f"- `{f.name}` references undeclared `{name}`")
    if not sanity_result["syntax_errors"] and not sanity_result["undeclared_globals"]:
        lines.append("Clean -- no syntax errors, no undeclared global references.")
    lines.append("")

    if collision_results:
        lines.append("## SQL id-collision check (against real indexed DSP data)")
        for table, result in collision_results.items():
            lines.append(f"### `{table}` -> `{result['checked_table']}`")
            if result.get("note"):
                lines.append(result["note"])
            same = len(result.get("same_entity", []))
            mismatch = result.get("name_mismatch", [])
            unclassified = result.get("unclassified", [])
            if same:
                lines.append(f"- {same} id(s) already exist in DSP under the SAME name (safe).")
            if mismatch:
                lines.append(f"- **{len(mismatch)} id(s) collide under a DIFFERENT name -- real "
                             f"conflict, needs a human decision:**")
                for item in mismatch[:20]:
                    lines.append(f"  - {item}")
            if unclassified:
                lines.append(f"- {len(unclassified)} id(s) collide but couldn't be name-classified "
                             f"(no name column to compare) -- treat as needing a look.")
        lines.append("")

    duplication_results = duplication_results or {}
    if duplication_results:
        lines.append("## SQL content-duplication check (against real indexed DSP data)")
        lines.append("Checks whether this package's content (e.g. mob_groups' real identity, "
                      "(poolid, zoneid) -- NOT groupid, which is just DSP's storage-level id) "
                      "already exists in DSP under a DIFFERENT id. Added 2026-09-15 after a real "
                      "incident where id-collision checking alone missed this -- see "
                      "data/dsp_sql_schema_map.json's mob_groups warning for the full writeup.")
        for table, result in duplication_results.items():
            lines.append(f"### `{table}` -> `{result['checked_table']}`")
            if result.get("note"):
                lines.append(result["note"])
            dupes = result.get("duplicates", [])
            if dupes:
                lines.append(f"- **{len(dupes)} content key(s) already exist in DSP under a "
                             f"different id -- do not ship as new rows without reviewing first:**")
                id_col = (schema_map or {}).get(table, {}).get("id_column", "id")
                for d in dupes[:20]:
                    existing_ids = [e.get(id_col) for e in d["existing"]]
                    lines.append(f"  - content_key={d['content_key']} candidate_id={d['candidate_id']} "
                                 f"-- DSP already has this under id(s) {existing_ids}")
                lines.append("  Run `backport_sql_live_check.py --package <this dir>` against the "
                             "real live server for a real-impact classification (live spawns/loot) "
                             "before deciding whether to reuse or keep both.")
        lines.append("")

    overall_clean = (
        (lua_result is None or lua_result["total_flags"] == 0)
        and not binding_result["missing"]
        and not sanity_result["syntax_errors"]
        and not sanity_result["undeclared_globals"]
        and not any(r.get("name_mismatch") for r in collision_results.values())
        and not any(r.get("duplicates") for r in duplication_results.values())
    )
    lines.append("## Overall")
    lines.append("**Clean** -- nothing flagged, no missing bindings, no sanity errors, no real id "
                 "collisions, no content duplication." if overall_clean else
                 "**Needs review** -- see the sections above for what to check by hand before "
                 "treating this package as done.")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package_dir", type=Path, help="Folder with lua/ and optionally sql/")
    ap.add_argument("--target", default="old_dsp_reference", choices=["old_dsp_reference", "landsandboat"])
    ap.add_argument("--dsp-root", default=None, help="Real DSP checkout (else Settings' dsp_server_path)")
    ap.add_argument("--zone-table", default=None, help="Zone id-table name, applied to every .lua file")
    ap.add_argument("--id-shape", default="flat", help="Zone id-table shape, applied to every .lua file")
    ap.add_argument("--id-file-hint", default=None)
    ap.add_argument("--verify-only", action="store_true",
                     help="Skip conversion, just re-run the 3 checks against an existing lua-dsp/")
    args = ap.parse_args()

    package_dir: Path = args.package_dir
    if not package_dir.is_dir():
        ap.error(f"{package_dir} is not a directory")

    dsp_root = Path(args.dsp_root) if args.dsp_root else settings.get_dsp_root()
    if dsp_root is None:
        ap.error("No DSP checkout configured -- set Settings' dsp_server_path or pass --dsp-root.")
    flavor = blc.detect_target_flavor(dsp_root)
    if flavor is None:
        print(f"error: {dsp_root} does not fingerprint as either known DSP flavor -- refusing to "
              f"guess. Check the path.", file=sys.stderr)
        sys.exit(2)
    if flavor != args.target:
        print(f"error: {dsp_root} fingerprints as '{flavor}', but --target is '{args.target}'. "
              f"Pass --target {flavor} instead.", file=sys.stderr)
        sys.exit(2)

    lua_src, lua_dst = package_dir / "lua", package_dir / "lua-dsp"
    sql_src, sql_dst = package_dir / "sql", package_dir / "sql-dsp"

    lua_result = None
    sql_result = None
    if not args.verify_only:
        if lua_src.is_dir():
            print(f"Converting Lua: {lua_src} -> {lua_dst}")
            lua_result = convert_lua_tree(lua_src, lua_dst, args.target, args.zone_table,
                                           args.id_shape, args.id_file_hint)
            print(f"  {len(lua_result['converted'])} file(s), {lua_result['total_flags']} flagged line(s)")
        else:
            print(f"No lua/ found under {package_dir} -- skipping Lua conversion.")

        schema_map = bsc.load_schema_map()
        print(f"Converting SQL: {sql_src} -> {sql_dst}")
        sql_result = convert_sql_tree(sql_src, sql_dst, schema_map)
        if sql_result["converted"]:
            print(f"  {len(sql_result['converted'])} file(s), {len(sql_result['warnings'])} warning(s)")
    elif not lua_dst.is_dir():
        ap.error(f"--verify-only requires an existing {lua_dst}")

    print("Running binding audit...")
    binding_result = bba.audit_package(lua_dst, dsp_root, flavor) if lua_dst.is_dir() else \
        {"confirmed": [], "missing": []}

    print("Running Lua sanity check...")
    sanity_result = blsc.check_package(lua_dst) if lua_dst.is_dir() else \
        {"syntax_errors": [], "undeclared_globals": []}

    schema_map = bsc.load_schema_map()
    collision_results = {}
    duplication_results = {}
    if sql_result and sql_result["ids_by_table"]:
        print("Running SQL id-collision check against indexed DSP data...")
        collision_results = run_id_collision_checks(
            sql_result["ids_by_table"], sql_result["id_to_name_by_table"], schema_map)
        print("Running SQL content-duplication check against indexed DSP data...")
        duplication_results = run_content_duplication_checks(
            sql_result.get("rows_by_table", {}), schema_map)

    report = build_report(package_dir, args.target, dsp_root, flavor,
                           lua_result, sql_result, binding_result, sanity_result, collision_results,
                           duplication_results, schema_map)
    report_path = package_dir / "BACKPORT_REPORT.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    print(f"\nReport written to {report_path}")
    print("\n" + report)

    any_issue = (
        (lua_result and lua_result["total_flags"] > 0)
        or binding_result["missing"]
        or sanity_result["syntax_errors"] or sanity_result["undeclared_globals"]
        or any(r.get("name_mismatch") for r in collision_results.values())
        or any(r.get("duplicates") for r in duplication_results.values())
    )
    sys.exit(1 if any_issue else 0)


if __name__ == "__main__":
    main()
