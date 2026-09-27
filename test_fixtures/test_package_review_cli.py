#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from workbench.cli.package_review import package_review
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
        target=root/"target"
        source.mkdir()
        target.mkdir()

        action=MigrationAction(
            "a:review","migration:test","REVIEW_PROPOSALS","artifact:mission","MANUAL_REQUIRED"
        )
        manifest=build_package_manifest(
            build_package_plan((action,)),
            (Artifact("artifact:mission","LUA",path="mission.lua"),),
            feature_id="feature:test",
            source_family="LSB",
            target_family="DSP",
        )
        proposal=GeneratedOutput(
            "generated:proposal",
            "proposals/review.txt",
            "REPORT",
            "review\n",
            "fixture",
            {"proposal_only":True},
        )
        manifest=attach_generated_outputs(manifest,(proposal,))
        assemble_migration_package(
            manifest,
            source,
            package,
            generated_outputs=(proposal,),
        )

        result=package_review(package,target)
        assert result["migration_id"]=="migration:test",result
        assert result["feature_id"]=="feature:test",result
        assert result["cohesion_status"]=="COHERENT",result

    print("package review CLI self-test: PASS")


if __name__=="__main__":
    main()
