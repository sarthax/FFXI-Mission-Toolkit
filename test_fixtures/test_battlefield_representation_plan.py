#!/usr/bin/env python3
from workbench.plugins.domain import (
    analyze_dsp_battlefield_callbacks,
    plan_dsp_battlefield_callback_adaptation,
    plan_dsp_battlefield_representation,
    propose_dsp_battlefield_membership,
    propose_dsp_battlefield_policy,
)


def main():
    membership=propose_dsp_battlefield_membership(
        960,
        ((101,102,103),),
        [{"battlefield_id":960,"battlefield_number":1,"entity_id":101,"conditions":3}],
    )
    policy=propose_dsp_battlefield_policy(
        960,
        {"level_cap":40},
        {"battlefield_id":960,"level_cap":50},
    )
    callbacks=plan_dsp_battlefield_callback_adaptation(
        analyze_dsp_battlefield_callbacks(
            "function onBattlefieldEnter(player,battlefield) end\n",
            ("onBattlefieldEnter",),
        ),
        source_framework_methods=("entryRequirement",),
    )
    plan=plan_dsp_battlefield_representation(membership,policy,callbacks)
    assert plan.status=="READY",plan
    assert set(plan.safe_generated_surfaces)=={"bcnm_battlefield","bcnm_info"},plan
    assert plan.callback_status=="NOT_REQUIRED",plan
    assert not plan.manual_surfaces,plan

    callback_gap=plan_dsp_battlefield_callback_adaptation(
        analyze_dsp_battlefield_callbacks("",("onBattlefieldEnter",)),
        source_framework_methods=("entryRequirement",),
    )
    manual=plan_dsp_battlefield_representation(membership,policy,callback_gap)
    assert manual.status=="MANUAL_REQUIRED",manual
    assert "battlefield_callbacks" in manual.manual_surfaces,manual

    print("DSP battlefield representation planning self-test: PASS")


if __name__=="__main__":
    main()
