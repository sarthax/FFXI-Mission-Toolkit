#!/usr/bin/env python3
from workbench.core.schema import MigrationAction
from workbench.plugins.domain import (
    DspBattlefieldRepresentationPlan,
    apply_plugin_reshape_findings,
    battlefield_representation_finding,
)


def main():
    actions=(
        MigrationAction(
            "a:battlefield","migration:test","MANUAL_REVIEW",None,"MANUAL_REQUIRED",
            metadata={"source_role":"battlefield_script"},
        ),
        MigrationAction(
            "a:mission","migration:test","MANUAL_REVIEW",None,"MANUAL_REQUIRED",
            metadata={"source_role":"mission_script"},
        ),
    )
    plan=DspBattlefieldRepresentationPlan(
        status="READY",
        sql_policy_status="EQUIVALENT",
        sql_membership_status="EQUIVALENT",
        callback_status="NOT_REQUIRED",
        safe_generated_surfaces=(),
        manual_surfaces=(),
    )
    finding=battlefield_representation_finding("feature:test",plan)
    refined=apply_plugin_reshape_findings(actions,(finding,))
    by_id={a.action_id:a for a in refined}
    assert by_id["a:battlefield"].action=="NOT_REQUIRED",refined
    assert by_id["a:battlefield"].status=="COMPATIBLE",refined
    assert by_id["a:mission"].action=="MANUAL_REVIEW",refined
    print("plugin reshape action refinement self-test: PASS")


if __name__=="__main__":
    main()
