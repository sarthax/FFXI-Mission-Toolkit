#!/usr/bin/env python3
from pathlib import Path
import tempfile

from workbench.core.schema import Artifact, MigrationAction
from workbench.migrations.package_assembly import assemble_migration_package
from workbench.migrations.generated_output import GeneratedOutput
from workbench.migrations.package_cohesion import verify_package_cohesion
from workbench.migrations.package_manifest import build_package_manifest
from workbench.migrations.package_plan import build_package_plan


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source=root/"source"
        package=root/"package"
        (source/"lua").mkdir(parents=True)
        (source/"lua"/"test.lua").write_text("return 1\n",encoding="utf-8")

        artifact=Artifact("artifact:test","LUA",path="lua/test.lua")
        action=MigrationAction("action:test","migration:test","COPY","artifact:test","AUTO_MIGRATABLE")
        manifest=build_package_manifest(build_package_plan([action]),[artifact])
        generated=GeneratedOutput(
            "generated:test",
            "proposals/test.patch",
            "LUA_PATCH_PROPOSAL",
            "-- proposal\n",
            "fixture",
            {"proposal_only":True},
        )
        assemble_migration_package(manifest,source,package,generated_outputs=[generated])

        result=verify_package_cohesion(package)
        assert result.status=="COHERENT",result

        (package/"lua"/"test.lua").write_text("tampered\n",encoding="utf-8")
        result=verify_package_cohesion(package)
        assert result.status=="FAILED",result
        assert any("Hash mismatch" in issue for issue in result.issues),result

    print("migration package cohesion self-test: PASS")


if __name__=="__main__":
    main()
