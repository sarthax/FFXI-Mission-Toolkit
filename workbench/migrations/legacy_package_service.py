"""Service boundary for the legacy folder-based backport package workflow.

This preserves the mature converter/audit/report behavior while moving orchestration out
of gui_server.py. It does not replace the newer semantic migration package pipeline.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import backport_binding_audit
import backport_lua_convert
import backport_lua_sanity_check
import backport_package
import backport_sql_convert


def run_legacy_package_workflow(
    package_dir: Path,
    dsp_root: Path,
    *,
    target: str = "old_dsp_reference",
    zone_table: str | None = None,
    id_shape: str = "flat",
    id_file_hint: str | None = None,
    verify_only: bool = False,
) -> dict[str, Any]:
    package_dir=Path(package_dir)
    dsp_root=Path(dsp_root)

    if not package_dir.is_dir():
        return {"status":"ERROR","error":f"No such package directory: {package_dir}"}
    if not dsp_root.is_dir():
        return {"status":"ERROR","error":f"No such DSP checkout: {dsp_root}"}

    flavor=backport_lua_convert.detect_target_flavor(dsp_root)
    if flavor is None:
        return {
            "status":"ERROR",
            "error":f"{dsp_root} does not fingerprint as a known DSP flavor.",
        }
    if flavor != target:
        return {
            "status":"ERROR",
            "error":f"Configured DSP checkout fingerprints as '{flavor}', but target is '{target}'.",
            "flavor":flavor,
        }

    lua_src,lua_dst=package_dir/"lua",package_dir/"lua-dsp"
    sql_src,sql_dst=package_dir/"sql",package_dir/"sql-dsp"
    schema_map=backport_sql_convert.load_schema_map()

    lua_result=None
    sql_result=None
    if not verify_only:
        if lua_src.is_dir():
            lua_result=backport_package.convert_lua_tree(
                lua_src,lua_dst,target,zone_table,id_shape,id_file_hint
            )
        sql_result=backport_package.convert_sql_tree(sql_src,sql_dst,schema_map)
    elif not lua_dst.is_dir():
        return {
            "status":"ERROR",
            "error":f"Verify-only needs an existing {lua_dst} -- run a real conversion first.",
            "flavor":flavor,
        }

    binding_result=(
        backport_binding_audit.audit_package(lua_dst,dsp_root,flavor)
        if lua_dst.is_dir() else {"confirmed":[],"missing":[]}
    )
    sanity_result=(
        backport_lua_sanity_check.check_package(lua_dst)
        if lua_dst.is_dir() else {"syntax_errors":[],"undeclared_globals":[]}
    )

    collision_results={}
    duplication_results={}
    if sql_result and sql_result.get("ids_by_table"):
        collision_results=backport_package.run_id_collision_checks(
            sql_result["ids_by_table"],
            sql_result["id_to_name_by_table"],
            schema_map,
        )
        duplication_results=backport_package.run_content_duplication_checks(
            sql_result.get("rows_by_table",{}),
            schema_map,
        )

    report_md=backport_package.build_report(
        package_dir,target,dsp_root,flavor,lua_result,sql_result,
        binding_result,sanity_result,collision_results,duplication_results,schema_map
    )
    report_path=package_dir/"BACKPORT_REPORT.md"
    report_path.write_text(report_md,encoding="utf-8",newline="\n")

    overall_clean=(
        (lua_result is None or lua_result["total_flags"]==0)
        and not binding_result["missing"]
        and not sanity_result["syntax_errors"]
        and not sanity_result["undeclared_globals"]
        and not any(row.get("name_mismatch") for row in collision_results.values())
        and not any(row.get("duplicates") for row in duplication_results.values())
    )

    return {
        "status":"VERIFIED" if overall_clean else "MANUAL_REQUIRED",
        "error":None,
        "flavor":flavor,
        "lua_result":lua_result,
        "sql_result":sql_result,
        "binding_result":binding_result,
        "sanity_result":sanity_result,
        "collision_results":collision_results,
        "duplication_results":duplication_results,
        "overall_clean":overall_clean,
        "report_path":str(report_path),
        "report_md":report_md,
        "schema_map":schema_map,
    }
