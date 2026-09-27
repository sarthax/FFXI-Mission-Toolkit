#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path

from workbench.migrations.patch_operations import PatchOperation
from workbench.migrations.patch_plan import build_patch_plan_output
from workbench.migrations.patch_approval import assess_patch_plan_for_approval
from workbench.migrations.patch_approval_request import build_patch_approval_request
from workbench.migrations.patch_apply import apply_approved_patch_plan, rollback_patch_apply


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        target_root=root/"target"
        target_root.mkdir()
        target=target_root/"x.lua"
        original="before\nanchor\nafter\n"
        target.write_text(original,encoding="utf-8")

        plan=build_patch_plan_output(
            "fixture",
            {"x.lua":original},
            {"x.lua":(PatchOperation("op","x.lua","INSERT_BEFORE","anchor","inserted\n"),)},
        )
        readiness=assess_patch_plan_for_approval(plan.output.content,target_root)
        request=build_patch_approval_request(plan.output.content,readiness,request_id="fixture")

        try:
            apply_approved_patch_plan(
                plan.output.content,
                target_root,
                request.content,
                root/"journals"/"apply.json",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("PENDING approval must not allow apply")

        approved=json.loads(request.content)
        approved["status"]="APPROVED"
        journal_path=root/"journals"/"apply.json"
        journal=apply_approved_patch_plan(
            plan.output.content,
            target_root,
            approved,
            journal_path,
        )
        assert journal["status"]=="APPLIED",journal
        assert "inserted\nanchor" in target.read_text(encoding="utf-8")

        rolled=rollback_patch_apply(journal_path)
        assert rolled["status"]=="ROLLED_BACK",rolled
        assert target.read_text(encoding="utf-8")==original

    print("approved patch apply self-test: PASS")


if __name__=="__main__":
    main()
