#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.migrations.patch_operations import PatchOperation
from workbench.migrations.patch_plan import build_patch_plan_output
from workbench.migrations.patch_approval import assess_patch_plan_for_approval


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        target=root/"x.lua"
        target.write_text("before\nanchor\nafter\n",encoding="utf-8")
        plan=build_patch_plan_output(
            "fixture",
            {"x.lua":target.read_text(encoding="utf-8")},
            {
                "x.lua":(
                    PatchOperation("op1","x.lua","INSERT_BEFORE","anchor","inserted\n"),
                ),
            },
        )
        ready=assess_patch_plan_for_approval(plan.output.content,root)
        assert ready.status=="READY_FOR_APPROVAL",ready

        target.write_text("changed\nanchor\nafter\n",encoding="utf-8")
        drift=assess_patch_plan_for_approval(plan.output.content,root)
        assert drift.status=="DRIFTED",drift

    print("patch approval gate self-test: PASS")


if __name__=="__main__":
    main()
