#!/usr/bin/env python3
from workbench.migrations.patch_operations import PatchOperation, preview_patch_operations


def main():
    source="a\nanchor\nz\n"
    ready=preview_patch_operations(
        source,
        (PatchOperation("op1","x.lua","INSERT_BEFORE","anchor","inserted\n"),),
    )
    assert ready.status=="READY",ready
    assert "inserted\nanchor" in ready.output,ready

    ambiguous=preview_patch_operations(
        "anchor\nanchor\n",
        (PatchOperation("op2","x.lua","INSERT_AFTER","anchor","x\n"),),
    )
    assert ambiguous.status=="MANUAL_REQUIRED",ambiguous
    assert ambiguous.output=="anchor\nanchor\n",ambiguous

    print("patch operation preview self-test: PASS")


if __name__=="__main__":
    main()
