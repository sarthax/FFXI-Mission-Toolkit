#!/usr/bin/env python3
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from workbench.migrations.patch_operations import PatchOperation
from workbench.migrations.patch_plan import build_patch_plan_output
from workbench.migrations.patch_approval import assess_patch_plan_for_approval
from workbench.migrations.patch_approval_request import (
    build_patch_approval_request,
    assess_patch_execution_eligibility,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        target=root/"x.lua"
        target.write_text("anchor\n",encoding="utf-8")
        plan=build_patch_plan_output(
            "fixture",
            {"x.lua":"anchor\n"},
            {"x.lua":(PatchOperation("op","x.lua","INSERT_BEFORE","anchor","x\n"),)},
        )
        readiness=assess_patch_plan_for_approval(plan.output.content,root)
        assert readiness.status=="READY_FOR_APPROVAL",readiness

        request=build_patch_approval_request(
            plan.output.content,
            readiness,
            request_id="fixture",
        )
        pending=assess_patch_execution_eligibility(
            plan.output.content,
            readiness,
            request.content,
        )
        assert pending.status=="AWAITING_APPROVAL",pending

        approved=json.loads(request.content)
        approved["status"]="APPROVED"
        eligible=assess_patch_execution_eligibility(
            plan.output.content,
            readiness,
            approved,
        )
        assert eligible.status=="ELIGIBLE_FOR_DETERMINISTIC_APPLY",eligible

        approved["patch_plan_sha256"]="wrong"
        blocked=assess_patch_execution_eligibility(
            plan.output.content,
            readiness,
            approved,
        )
        assert blocked.status=="BLOCKED",blocked

    print("patch approval request self-test: PASS")


if __name__=="__main__":
    main()
