#!/usr/bin/env python3
"""Regression checks for Workbench plan scoping in backport_package."""
import json
from pathlib import Path
import tempfile

import backport_package
import backport_binding_audit
import backport_lua_sanity_check


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

        lua_root=Path(td)/"lua-dsp"
        (lua_root/"scripts").mkdir(parents=True)
        (lua_root/"scripts"/"a.lua").write_text("local x = player:getID()\n",encoding="utf-8")
        (lua_root/"scripts"/"stale.lua").write_text("local x = player:DefinitelyNotARealBinding()\n",encoding="utf-8")
        selected={"scripts/a.lua"}
        calls=backport_binding_audit.collect_method_calls(lua_root,selected)
        assert "getID" in calls and "DefinitelyNotARealBinding" not in calls,calls
        sanity=backport_lua_sanity_check.check_package(lua_root,selected)
        assert sanity["file_count"]==1,sanity

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
