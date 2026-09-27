#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from workbench.cli.patch_status import patch_status
from workbench.migrations.generated_output import materialize_generated_outputs, write_generated_output_journal
from workbench.migrations.patch_operations import PatchOperation
from workbench.migrations.patch_plan import build_patch_plan_output
from workbench.migrations.patch_approval import assess_patch_plan_for_approval
from workbench.migrations.patch_approval_request import build_patch_approval_request


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        package=root/"package"
        target=root/"target"
        package.mkdir()
        target.mkdir()
        (target/"x.lua").write_text("anchor\n",encoding="utf-8")

        plan=build_patch_plan_output(
            "fixture",
            {"x.lua":"anchor\n"},
            {"x.lua":(PatchOperation("op","x.lua","INSERT_BEFORE","anchor","x\n"),)},
        )
        readiness=assess_patch_plan_for_approval(plan.output.content,target)
        request=build_patch_approval_request(plan.output.content,readiness,request_id="fixture")
        generated=materialize_generated_outputs((plan.output,request),package)
        write_generated_output_journal(package,generated)
        (package/"WORKBENCH_PACKAGE_MANIFEST.json").write_text(
            json.dumps({"migration":{"migration_id":"fixture"}})+"\n",encoding="utf-8"
        )
        (package/"WORKBENCH_VALIDATION_PACKAGE.json").write_text(
            json.dumps({"migration":{"migration_id":"fixture"},"status":"MANUAL_REQUIRED"})+"\n",encoding="utf-8"
        )
        (package/"WORKBENCH_MATERIALIZATION.json").write_text(
            json.dumps({"migration":{"migration_id":"fixture"},"artifacts":[]})+"\n",encoding="utf-8"
        )

        result=patch_status(package,target)
        assert result["status"]=="AWAITING_APPROVAL",result
        assert result["patch_plan_path"].endswith("fixture.json"),result

    print("patch lifecycle CLI self-test: PASS")


if __name__=="__main__":
    main()
