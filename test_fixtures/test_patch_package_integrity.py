#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from workbench.migrations.generated_output import materialize_generated_outputs, write_generated_output_journal
from workbench.migrations.patch_operations import PatchOperation
from workbench.migrations.patch_plan import build_patch_plan_output
from workbench.migrations.patch_approval import PatchApprovalResult, PatchApprovalTarget
from workbench.migrations.patch_approval_request import build_patch_approval_request
from workbench.migrations.patch_package_integrity import verify_patch_package_integrity


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        plan=build_patch_plan_output(
            "fixture",
            {"x.lua":"anchor\n"},
            {"x.lua":(PatchOperation("op","x.lua","INSERT_BEFORE","anchor","x\n"),)},
        )
        readiness=PatchApprovalResult(
            "READY_FOR_APPROVAL",
            (PatchApprovalTarget("x.lua","READY_FOR_APPROVAL"),),
        )
        request=build_patch_approval_request(
            plan.output.content,
            readiness,
            request_id="fixture",
        )
        result=materialize_generated_outputs((plan.output,request),root)
        write_generated_output_journal(root,result)
        coherent=verify_patch_package_integrity(root)
        assert coherent.status=="COHERENT",coherent

        approval_path=root/request.relative_path
        payload=json.loads(approval_path.read_text(encoding="utf-8"))
        payload["patch_plan_sha256"]="wrong"
        approval_path.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
        failed=verify_patch_package_integrity(root)
        assert failed.status=="FAILED",failed

    print("patch package integrity self-test: PASS")


if __name__=="__main__":
    main()
