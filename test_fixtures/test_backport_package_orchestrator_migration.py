from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    canonical = importlib.import_module("workbench.packages.migration.orchestrator")
    assert not (REPO_ROOT / "backport_package.py").exists()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        lua_src = root / "lua"
        lua_dst = root / "lua-dsp"
        _write(lua_src / "scripts/globals/test.lua", "local job = tpz.job.COR\n")
        _write(lua_src / "scripts/globals/skip.lua", "local job = tpz.job.WAR\n")

        result = canonical.convert_lua_tree(
            lua_src,
            lua_dst,
            "old_dsp_reference",
            None,
            "flat",
            None,
            {"scripts/globals/test.lua"},
        )
        assert result["converted"] == ["scripts/globals/test.lua"]
        converted = (lua_dst / "scripts/globals/test.lua").read_text(encoding="utf-8")
        assert "JOBS.COR" in converted
        assert not (lua_dst / "scripts/globals/skip.lua").exists()

        empty_sql = canonical.convert_sql_tree(root / "missing-sql", root / "sql-dsp", {})
        assert empty_sql == {
            "converted": [],
            "warnings": [],
            "ids_by_table": {},
            "id_to_name_by_table": {},
            "rows_by_table": {},
        }
        assert canonical.run_id_collision_checks({}, {}, {}, root / "unused.db") == {}
        assert canonical.run_content_duplication_checks({}, {}, root / "unused.db") == {}

        blocked = root / "blocked-plan.json"
        blocked.write_text(
            json.dumps(
                {
                    "kind": "WORKBENCH_MIGRATION_PACKAGE_PLAN",
                    "schema": 2,
                    "migration": {"status": "BLOCKED"},
                }
            ),
            encoding="utf-8",
        )
        try:
            canonical.load_workbench_plan(blocked)
        except ValueError as exc:
            assert "BLOCKED" in str(exc)
        else:
            raise AssertionError("BLOCKED plan was accepted")

        clean_report = canonical.build_report(
            root,
            "old_dsp_reference",
            root / "dsp",
            "old_dsp_reference",
            {"converted": ["test.lua"], "flagged": [], "total_flags": 0},
            None,
            {"confirmed": [], "missing": []},
            {"syntax_errors": [], "undeclared_globals": []},
            {},
        )
        assert "**Clean**" in clean_report

        review_report = canonical.build_report(
            root,
            "old_dsp_reference",
            root / "dsp",
            "old_dsp_reference",
            {"converted": ["test.lua"], "flagged": [("test.lua", 1)], "total_flags": 1},
            None,
            {"confirmed": [], "missing": []},
            {"syntax_errors": [], "undeclared_globals": []},
            {},
        )
        assert "**Needs review**" in review_report

    code = (
        "from workbench.packages.migration import orchestrator; "
        "print(orchestrator.convert_lua_tree, orchestrator.build_report)"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("backport package orchestrator migration: PASS")


if __name__ == "__main__":
    main()
