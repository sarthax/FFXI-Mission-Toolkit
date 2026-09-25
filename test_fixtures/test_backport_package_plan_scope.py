#!/usr/bin/env python3
"""Regression checks for Workbench plan scoping in backport_package."""
import json
from pathlib import Path
import tempfile

import backport_package


def main():
    manifest={
        "schema":2,
        "kind":"WORKBENCH_MIGRATION_PACKAGE_PLAN",
        "migration":{"migration_id":"migration:test","status":"READY"},
        "execution":{"steps":[
            {"backend":"lua","path":"lua/scripts/a.lua"},
            {"backend":"sql","path":"sql/mob_groups.sql"},
            {"backend":"manual","path":"notes.md"},
        ]},
    }
    with tempfile.TemporaryDirectory() as td:
        path=Path(td)/"plan.json"
        path.write_text(json.dumps(manifest),encoding="utf-8")
        loaded=backport_package.load_workbench_plan(path)
        assert backport_package.planned_backend_paths(loaded,"lua")=={"scripts/a.lua"}
        assert backport_package.planned_backend_paths(loaded,"sql")=={"mob_groups.sql"}

        blocked=dict(manifest)
        blocked["migration"]=dict(manifest["migration"],status="BLOCKED")
        path.write_text(json.dumps(blocked),encoding="utf-8")
        try:
            backport_package.load_workbench_plan(path)
        except ValueError:
            pass
        else:
            raise AssertionError("BLOCKED plan must be rejected")

    print("backport package plan scope self-test: PASS")


if __name__=="__main__":
    main()
