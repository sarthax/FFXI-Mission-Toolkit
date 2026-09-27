#!/usr/bin/env python3
import json

from workbench.migrations.patch_operations import PatchOperation
from workbench.migrations.patch_plan import build_patch_plan_output


def main():
    result=build_patch_plan_output(
        "fixture",
        {"x.lua":"before\nanchor\nafter\n"},
        {
            "x.lua":(
                PatchOperation(
                    "op1","x.lua","INSERT_BEFORE","anchor","inserted\n"
                ),
            ),
        },
    )
    assert result.status=="READY",result
    payload=json.loads(result.output.content)
    assert payload["kind"]=="WORKBENCH_PATCH_PLAN",payload
    assert payload["targets"][0]["source_sha256"],payload
    assert payload["targets"][0]["preview_sha256"],payload
    assert result.output.metadata["proposal_only"] is True,result
    print("patch plan output self-test: PASS")


if __name__=="__main__":
    main()
