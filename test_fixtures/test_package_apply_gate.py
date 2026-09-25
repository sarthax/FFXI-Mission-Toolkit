#!/usr/bin/env python3
from pathlib import Path
import json
import tempfile

from workbench.core.schema import Artifact, MigrationAction
from workbench.migrations.package_assembly import assemble_migration_package
from workbench.migrations.package_apply_gate import assess_apply_readiness
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
        assemble_migration_package(manifest,source,package)

        ready=assess_apply_readiness(package)
        assert ready.status=="READY",ready

        validation_path=package/"WORKBENCH_VALIDATION_PACKAGE.json"
        validation=json.loads(validation_path.read_text(encoding="utf-8"))
        validation["status"]="MANUAL_REQUIRED"
        validation_path.write_text(json.dumps(validation,indent=2)+"\n",encoding="utf-8")
        manual=assess_apply_readiness(package)
        assert manual.status=="MANUAL_REQUIRED",manual

        (package/"lua"/"test.lua").write_text("tampered\n",encoding="utf-8")
        blocked=assess_apply_readiness(package)
        assert blocked.status=="BLOCKED",blocked

    print("migration package apply-readiness self-test: PASS")


if __name__=="__main__":
    main()
