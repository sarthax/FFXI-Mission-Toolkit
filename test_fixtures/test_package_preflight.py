#!/usr/bin/env python3
from pathlib import Path
import tempfile

from workbench.core.schema import Artifact, MigrationAction
from workbench.migrations.package_manifest import build_package_manifest
from workbench.migrations.package_plan import build_package_plan
from workbench.migrations.package_preflight import preflight_manifest_artifacts


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        (root/"lua").mkdir()
        (root/"lua"/"safe.lua").write_text("local x = 1\n",encoding="utf-8")
        (root/"lua"/"framework.lua").write_text("local mission = Mission:new(1, 2)\n",encoding="utf-8")

        artifacts=[
            Artifact("a:safe","LUA",path="lua/safe.lua"),
            Artifact("a:framework","LUA",path="lua/framework.lua"),
        ]
        actions=[
            MigrationAction("m:safe","migration:test","CONVERT","a:safe","AUTO_MIGRATABLE"),
            MigrationAction("m:framework","migration:test","CONVERT","a:framework","AUTO_MIGRATABLE"),
        ]
        manifest=build_package_manifest(
            build_package_plan(actions),
            artifacts,
            source_family="LSB",
            target_family="DSP",
        )
        assert all(step["conversion_status"]=="CONDITIONAL" for step in manifest["execution"]["steps"]),manifest

        updated,results=preflight_manifest_artifacts(manifest,root)
        by_path={r.path:r for r in results}
        assert by_path["lua/safe.lua"].status=="CONVERTED",results
        assert by_path["lua/framework.lua"].status=="MANUAL_REQUIRED",results

        by_step={s["path"]:s for s in updated["execution"]["steps"]}
        assert by_step["lua/safe.lua"]["conversion_status"]=="SUPPORTED",updated
        assert by_step["lua/framework.lua"]["conversion_status"]=="CONDITIONAL",updated

    print("conditional backend artifact preflight self-test: PASS")


if __name__=="__main__":
    main()
