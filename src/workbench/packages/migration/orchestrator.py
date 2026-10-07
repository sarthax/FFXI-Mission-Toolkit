#!/usr/bin/env python3
r"""End-to-end orchestration for converting and validating one assembled backport package.

The canonical implementation is package-safe: checkout and indexed-database locations are explicit
inputs for programmatic callers, while the CLI lazily resolves the historical Settings/database
defaults when explicit values are not supplied.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from workbench.migrations.package_manifest import converter_scope
from workbench.packages.migration import lua_convert as blc
from workbench.packages.migration import sql_convert as bsc
from workbench.validation.packages import binding_audit as bba
from workbench.validation.packages import lua_sanity as blsc


def load_workbench_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("kind") != "WORKBENCH_MIGRATION_PACKAGE_PLAN" or plan.get("schema") != 2:
        raise ValueError("Unsupported Workbench migration package plan")
    if plan.get("migration", {}).get("status") == "BLOCKED":
        raise ValueError("Workbench migration package plan is BLOCKED")
    blocked_conversion = [
        step
        for step in plan.get("execution", {}).get("steps", [])
        if step.get("backend") in {"lua", "sql"}
        and step.get("conversion_status") in {"UNSUPPORTED", "CONDITIONAL"}
    ]
    if blocked_conversion:
        routes = sorted(
            {
                f"{step.get('conversion_status')}:{step.get('artifact_type')}:{step.get('path')}"
                for step in blocked_conversion
            }
        )
        raise ValueError(
            "Workbench plan contains converter steps that are not cleared for execution: "
            + ", ".join(routes)
        )
    return plan


def planned_backend_paths(plan: dict, backend: str) -> set[str]:
    prefix = f"{backend}/"
    result = set()
    for path in converter_scope(plan, backend):
        normalized = path.replace("\\", "/")
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
        result.add(normalized)
    return result


def convert_lua_tree(
    src_root: Path,
    dst_root: Path,
    target: str,
    zone_table: str | None,
    id_shape: str | None,
    id_file_hint: str | None,
    include_paths: set[str] | None = None,
) -> dict:
    """Convert every selected Lua file into the mirrored destination tree."""
    converted, flagged = [], []
    total_flags = 0
    for src in sorted(src_root.rglob("*.lua")):
        rel = src.relative_to(src_root)
        if include_paths is not None and rel.as_posix() not in include_paths:
            continue
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        result = blc.convert(
            text,
            zone_table=zone_table,
            id_shape=id_shape,
            id_file_hint=id_file_hint,
            target=target,
        )
        dst.write_text(result.converted, encoding="utf-8", newline="\n")
        converted.append(str(rel))
        if result.flagged:
            flagged.append((str(rel), len(result.flagged)))
            total_flags += len(result.flagged)
    return {"converted": converted, "flagged": flagged, "total_flags": total_flags}


def convert_sql_tree(
    src_root: Path,
    dst_root: Path,
    schema_map: dict,
    include_paths: set[str] | None = None,
) -> dict:
    """Convert selected SQL files and retain source rows for collision/duplication checks."""
    if not src_root.is_dir():
        return {
            "converted": [],
            "warnings": [],
            "ids_by_table": {},
            "id_to_name_by_table": {},
            "rows_by_table": {},
        }

    converted, warnings = [], []
    ids_by_table: dict[str, list[str]] = {}
    id_to_name_by_table: dict[str, dict[int, str]] = {}
    rows_by_table: dict[str, list[list[str]]] = {}
    for src in sorted(src_root.glob("*.sql")):
        rel = src.relative_to(src_root).as_posix()
        if include_paths is not None and rel not in include_paths:
            continue
        table = src.stem
        dst = dst_root / src.name
        dst_root.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        rows = [row for parsed_table, row in bsc.parse_insert_values(text) if parsed_table == table]
        if rows:
            rows_by_table.setdefault(table, []).extend(rows)
        result = bsc.convert_table(table, rows, schema_map)
        dst.write_text(result.converted_sql, encoding="utf-8", newline="\n")
        converted.append(src.name)
        for warning in result.warnings:
            warnings.append({"file": src.name, **warning})
        if result.converted_ids:
            ids_by_table.setdefault(table, []).extend(result.converted_ids)
            id_to_name_by_table.setdefault(table, {}).update(result.id_to_name)
    return {
        "converted": converted,
        "warnings": warnings,
        "ids_by_table": ids_by_table,
        "id_to_name_by_table": id_to_name_by_table,
        "rows_by_table": rows_by_table,
    }


def run_id_collision_checks(
    ids_by_table: dict,
    id_to_name_by_table: dict,
    schema_map: dict,
    db_path: Path,
) -> dict:
    """Run indexed-DSP id-collision checks for every converted table."""
    if not ids_by_table:
        return {}
    con = sqlite3.connect(str(db_path))
    try:
        return {
            table: bsc.check_id_collisions(
                con,
                table,
                ids,
                schema_map,
                id_to_name=id_to_name_by_table.get(table),
            )
            for table, ids in ids_by_table.items()
        }
    finally:
        con.close()


def run_content_duplication_checks(rows_by_table: dict, schema_map: dict, db_path: Path) -> dict:
    """Run indexed-DSP content-key duplication checks for supported tables."""
    tables = [table for table in rows_by_table if table in bsc.CONTENT_KEY_COLUMNS]
    if not tables:
        return {}
    con = sqlite3.connect(str(db_path))
    try:
        return {
            table: bsc.check_content_duplication(con, table, rows_by_table[table], schema_map)
            for table in tables
        }
    finally:
        con.close()


def build_report(
    package_dir: Path,
    target: str,
    dsp_root: Path,
    flavor: str,
    lua_result: dict | None,
    sql_result: dict | None,
    binding_result: dict,
    sanity_result: dict,
    collision_results: dict,
    duplication_results: dict | None = None,
    schema_map: dict | None = None,
) -> str:
    lines = [
        f"# Backport report -- {package_dir.name}",
        "",
        f"Target: `{dsp_root}` (detected flavor: `{flavor}`)",
        "",
    ]

    if lua_result is not None:
        lines.append("## Lua conversion")
        lines.append(
            f"{len(lua_result['converted'])} file(s) converted, "
            f"{lua_result['total_flags']} line(s) flagged across "
            f"{len(lua_result['flagged'])} file(s)."
        )
        for rel, count in lua_result["flagged"]:
            lines.append(f"- `{rel}` -- {count} flagged line(s)")
        lines.append("")

    if sql_result is not None and sql_result["converted"]:
        lines.append("## SQL conversion")
        lines.append(f"{len(sql_result['converted'])} file(s) converted.")
        if sql_result["warnings"]:
            lines.append(f"{len(sql_result['warnings'])} warning(s):")
            for warning in sql_result["warnings"]:
                lines.append(
                    f"- `{warning['file']}` (`{warning['table']}`): {warning['reason']}"
                )
        lines.append("")

    lines.append("## Binding audit")
    lines.append(
        f"{len(binding_result['confirmed'])} confirmed, {len(binding_result['missing'])} missing."
    )
    for name, reason, files in binding_result["missing"]:
        file_list = ", ".join(file.name for file in files[:3])
        more = f" (+{len(files) - 3} more)" if len(files) > 3 else ""
        lines.append(f"- MISSING `:{name}(` -- {reason} [used in: {file_list}{more}]")
    lines.append("")

    lines.append("## Lua sanity check")
    if sanity_result["syntax_errors"]:
        lines.append(f"{len(sanity_result['syntax_errors'])} syntax error(s):")
        for file, error in sanity_result["syntax_errors"]:
            lines.append(f"- `{file.name}`: {error}")
    if sanity_result["undeclared_globals"]:
        lines.append(f"{len(sanity_result['undeclared_globals'])} undeclared global reference(s):")
        for file, name in sanity_result["undeclared_globals"]:
            lines.append(f"- `{file.name}` references undeclared `{name}`")
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
                lines.append(
                    f"- **{len(mismatch)} id(s) collide under a DIFFERENT name -- real conflict, "
                    "needs a human decision:**"
                )
                for item in mismatch[:20]:
                    lines.append(f"  - {item}")
            if unclassified:
                lines.append(
                    f"- {len(unclassified)} id(s) collide but couldn't be name-classified "
                    "(no name column to compare) -- treat as needing a look."
                )
        lines.append("")

    duplication_results = duplication_results or {}
    if duplication_results:
        lines.append("## SQL content-duplication check (against real indexed DSP data)")
        lines.append(
            "Checks whether this package's content already exists in DSP under a DIFFERENT id, "
            "rather than relying only on storage-level id collision checks."
        )
        for table, result in duplication_results.items():
            lines.append(f"### `{table}` -> `{result['checked_table']}`")
            if result.get("note"):
                lines.append(result["note"])
            dupes = result.get("duplicates", [])
            if dupes:
                lines.append(
                    f"- **{len(dupes)} content key(s) already exist in DSP under a different id "
                    "-- review before shipping new rows:**"
                )
                id_col = (schema_map or {}).get(table, {}).get("id_column", "id")
                for duplicate in dupes[:20]:
                    existing_ids = [entry.get(id_col) for entry in duplicate["existing"]]
                    lines.append(
                        f"  - content_key={duplicate['content_key']} "
                        f"candidate_id={duplicate['candidate_id']} -- DSP already has this under "
                        f"id(s) {existing_ids}"
                    )
                lines.append(
                    "  Run `python -m workbench.validation.live_db.sql_check --package <this dir>` against the live "
                    "server before deciding whether to reuse or keep both."
                )
        lines.append("")

    overall_clean = (
        (lua_result is None or lua_result["total_flags"] == 0)
        and not binding_result["missing"]
        and not sanity_result["syntax_errors"]
        and not sanity_result["undeclared_globals"]
        and not any(result.get("name_mismatch") for result in collision_results.values())
        and not any(result.get("duplicates") for result in duplication_results.values())
    )
    lines.append("## Overall")
    lines.append(
        "**Clean** -- nothing flagged, no missing bindings, no sanity errors, no real id "
        "collisions, no content duplication."
        if overall_clean
        else "**Needs review** -- see the sections above for what to check by hand before "
        "treating this package as done."
    )
    return "\n".join(lines) + "\n"


def _default_dsp_root() -> Path | None:
    from workbench.runtime.legacy_settings import get_dsp_root

    return get_dsp_root()


def _default_db_path() -> Path:
    from workbench.runtime.paths import DATABASE_PATH

    return DATABASE_PATH


def main(
    argv: list[str] | None = None,
    *,
    default_dsp_root: Path | None = None,
    default_db_path: Path | None = None,
) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package_dir", type=Path, help="Folder with lua/ and optionally sql/")
    ap.add_argument("--target", default="old_dsp_reference", choices=["old_dsp_reference", "landsandboat"])
    ap.add_argument("--dsp-root", default=None, help="Real DSP checkout; defaults to the configured Settings DSP path")
    ap.add_argument("--db-path", default=None, help="Indexed DSP SQLite database; defaults to the Workbench database path")
    ap.add_argument("--zone-table", default=None, help="Zone id-table name, applied to every .lua file")
    ap.add_argument("--id-shape", default="flat", help="Zone id-table shape, applied to every .lua file")
    ap.add_argument("--id-file-hint", default=None)
    ap.add_argument("--verify-only", action="store_true", help="Skip conversion and re-run checks against existing lua-dsp/")
    ap.add_argument("--plan", type=Path, default=None, help="Optional Workbench schema-2 migration package plan")
    args = ap.parse_args(argv)

    package_dir: Path = args.package_dir
    if not package_dir.is_dir():
        ap.error(f"{package_dir} is not a directory")

    dsp_root = Path(args.dsp_root) if args.dsp_root else (default_dsp_root or _default_dsp_root())
    if dsp_root is None:
        ap.error("No DSP checkout configured -- pass --dsp-root or configure Settings dsp_server_path.")
    flavor = blc.detect_target_flavor(dsp_root)
    if flavor is None:
        print(
            f"error: {dsp_root} does not fingerprint as either known DSP flavor -- refusing to guess. Check the path.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if flavor != args.target:
        print(
            f"error: {dsp_root} fingerprints as '{flavor}', but --target is '{args.target}'. Pass --target {flavor} instead.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    db_path = Path(args.db_path) if args.db_path else (default_db_path or _default_db_path())
    lua_src, lua_dst = package_dir / "lua", package_dir / "lua-dsp"
    sql_src, sql_dst = package_dir / "sql", package_dir / "sql-dsp"

    lua_scope = None
    sql_scope = None
    if args.plan is not None:
        try:
            workbench_plan = load_workbench_plan(args.plan)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            ap.error(f"Invalid --plan: {exc}")
        lua_scope = planned_backend_paths(workbench_plan, "lua")
        sql_scope = planned_backend_paths(workbench_plan, "sql")
        print(f"Using Workbench plan scope: {len(lua_scope)} Lua, {len(sql_scope)} SQL artifact(s).")

    lua_result = None
    sql_result = None
    if not args.verify_only:
        if lua_src.is_dir():
            print(f"Converting Lua: {lua_src} -> {lua_dst}")
            lua_result = convert_lua_tree(
                lua_src,
                lua_dst,
                args.target,
                args.zone_table,
                args.id_shape,
                args.id_file_hint,
                lua_scope,
            )
            print(f"  {len(lua_result['converted'])} file(s), {lua_result['total_flags']} flagged line(s)")
        else:
            print(f"No lua/ found under {package_dir} -- skipping Lua conversion.")

        schema_map = bsc.load_schema_map()
        print(f"Converting SQL: {sql_src} -> {sql_dst}")
        sql_result = convert_sql_tree(sql_src, sql_dst, schema_map, sql_scope)
        if sql_result["converted"]:
            print(f"  {len(sql_result['converted'])} file(s), {len(sql_result['warnings'])} warning(s)")
    elif not lua_dst.is_dir():
        ap.error(f"--verify-only requires an existing {lua_dst}")

    print("Running binding audit...")
    binding_result = (
        bba.audit_package(lua_dst, dsp_root, flavor, lua_scope)
        if lua_dst.is_dir()
        else {"confirmed": [], "missing": []}
    )

    print("Running Lua sanity check...")
    sanity_result = (
        blsc.check_package(lua_dst, lua_scope)
        if lua_dst.is_dir()
        else {"syntax_errors": [], "undeclared_globals": []}
    )

    schema_map = bsc.load_schema_map()
    collision_results = {}
    duplication_results = {}
    if sql_result and sql_result["ids_by_table"]:
        if db_path is None:
            ap.error("SQL collision checks require --db-path or the root compatibility CLI Settings database path.")
        print("Running SQL id-collision check against indexed DSP data...")
        collision_results = run_id_collision_checks(
            sql_result["ids_by_table"],
            sql_result["id_to_name_by_table"],
            schema_map,
            db_path,
        )
        print("Running SQL content-duplication check against indexed DSP data...")
        duplication_results = run_content_duplication_checks(
            sql_result.get("rows_by_table", {}),
            schema_map,
            db_path,
        )

    report = build_report(
        package_dir,
        args.target,
        dsp_root,
        flavor,
        lua_result,
        sql_result,
        binding_result,
        sanity_result,
        collision_results,
        duplication_results,
        schema_map,
    )
    report_path = package_dir / "BACKPORT_REPORT.md"
    report_path.write_text(report, encoding="utf-8", newline="\n")
    print(f"\nReport written to {report_path}")
    print("\n" + report)

    any_issue = (
        (lua_result and lua_result["total_flags"] > 0)
        or binding_result["missing"]
        or sanity_result["syntax_errors"]
        or sanity_result["undeclared_globals"]
        or any(result.get("name_mismatch") for result in collision_results.values())
        or any(result.get("duplicates") for result in duplication_results.values())
    )
    raise SystemExit(1 if any_issue else 0)


if __name__ == "__main__":
    main()
