#!/usr/bin/env python3
from pathlib import Path
import tempfile

from workbench.migrations.package_validation import build_validation_package
from workbench.migrations.apply_journal import apply_staged_files, rollback_apply


def main():
    manifest={
        "migration":{"migration_id":"migration:test","status":"READY"},
        "execution":{"steps":[
            {"backend":"lua","path":"lua/scripts/a.lua"},
            {"backend":"sql","path":"sql/mob_groups.sql"},
        ]},
    }
    validation=build_validation_package(manifest)
    kinds={c["validation_type"] for c in validation["checks"]}
    assert {"LUA_SANITY","BINDING_AUDIT","SQL_ID_COLLISION","SQL_CONTENT_DUPLICATION"} <= kinds,validation

    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        package=root/"package"
        target=root/"target"
        journal=root/"journal"/"apply.json"
        (package/"scripts").mkdir(parents=True)
        (package/"scripts"/"a.lua").write_text("new\n",encoding="utf-8")
        (target/"scripts").mkdir(parents=True)
        (target/"scripts"/"a.lua").write_text("old\n",encoding="utf-8")

        applied=apply_staged_files(package,target,["scripts/a.lua"],journal)
        assert applied["status"]=="APPLIED",applied
        assert (target/"scripts"/"a.lua").read_text()=="new\n"

        rolled=rollback_apply(journal)
        assert rolled["status"]=="ROLLED_BACK",rolled
        assert (target/"scripts"/"a.lua").read_text()=="old\n"

    print("validation package and apply journal self-test: PASS")


if __name__=="__main__":
    main()
