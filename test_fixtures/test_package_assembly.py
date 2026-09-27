#!/usr/bin/env python3
from pathlib import Path
import tempfile

from workbench.core.schema import Artifact, MigrationAction
from workbench.migrations.generated_output import GeneratedOutput
from workbench.migrations.package_assembly import assemble_migration_package
from workbench.migrations.package_manifest import build_package_manifest, attach_generated_outputs
from workbench.migrations.package_plan import build_package_plan


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source=root/"source"
        package=root/"package"
        (source/"lua").mkdir(parents=True)
        (source/"lua"/"test.lua").write_text("return 1\n",encoding="utf-8")

        artifact=Artifact("artifact:test","LUA",path="lua/test.lua")
        action=MigrationAction(
            "action:test","migration:test","CONVERT","artifact:test","AUTO_MIGRATABLE"
        )
        plan=build_package_plan([action])
        manifest=build_package_manifest(plan,[artifact])
        generated=GeneratedOutput(
            "generated:test",
            "sql-dsp/test.sql",
            "SQL",
            "INSERT INTO `x` VALUES (1);\n",
            "fixture",
        )
        manifest=attach_generated_outputs(manifest,[generated])

        result=assemble_migration_package(
            manifest,
            source,
            package,
            generated_outputs=[generated],
        )
        assert result.status=="ASSEMBLED",result
        assert (package/"lua"/"test.lua").exists(),result
        assert (package/"sql-dsp"/"test.sql").exists(),result
        assert result.manifest_path.exists(),result
        assert result.validation_path.exists(),result
        assert result.source_journal_path.exists(),result
        assert result.generated_journal_path.exists(),result

    print("migration package assembly self-test: PASS")


if __name__=="__main__":
    main()
