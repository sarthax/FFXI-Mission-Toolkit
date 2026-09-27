#!/usr/bin/env python3
from workbench.plugins.domain.battlefield_dsp import (
    propose_dsp_battlefield_membership,
    propose_dsp_battlefield_policy,
    analyze_dsp_battlefield_callbacks,
    generated_outputs_for_dsp_battlefield,
    plan_dsp_battlefield_callback_adaptation,
)


def main():
    groups=((101,102),(103,))
    exact=[
        {"battlefield_id":960,"battlefield_number":1,"entity_id":101,"conditions":3},
        {"battlefield_id":960,"battlefield_number":1,"entity_id":102,"conditions":3},
        {"battlefield_id":960,"battlefield_number":2,"entity_id":103,"conditions":3},
    ]
    same=propose_dsp_battlefield_membership(960,groups,exact)
    assert same.status=="EQUIVALENT",same
    assert not same.insert_sql,same

    additive=propose_dsp_battlefield_membership(960,groups,exact[:-1])
    assert additive.status=="ADDITIVE",additive
    assert additive.safe_to_generate,additive
    assert len(additive.insert_sql)==1,additive
    assert "(960,2,103,3)" in additive.insert_sql[0],additive

    conflict=propose_dsp_battlefield_membership(
        960,
        groups,
        exact[:-1]+[{"battlefield_id":960,"battlefield_number":3,"entity_id":103,"conditions":3}],
    )
    assert conflict.status=="DRIFT",conflict
    assert not conflict.safe_to_generate,conflict
    assert not conflict.insert_sql,conflict
    assert conflict.missing_rows and conflict.extra_rows,conflict

    target_policy={
        "battlefield_id":960,
        "time_limit":1800,
        "level_cap":40,
        "party_size":6,
        "loot_drop_id":0,
        "rules":5,
        "is_mission":1,
    }
    same_policy=propose_dsp_battlefield_policy(
        960,
        {"time_limit":1800,"level_cap":40,"party_size":6,"is_mission":True},
        target_policy,
    )
    assert same_policy.status=="EQUIVALENT",same_policy
    assert same_policy.update_sql is None,same_policy

    update_policy=propose_dsp_battlefield_policy(
        960,
        {"level_cap":50,"party_size":6},
        target_policy,
    )
    assert update_policy.status=="UPDATE_PROPOSAL",update_policy
    assert "`levelCap`=50" in update_policy.update_sql,update_policy

    missing_policy=propose_dsp_battlefield_policy(
        960,
        {"level_cap":40},
        None,
    )
    assert missing_policy.status=="MISSING_TARGET",missing_policy
    assert not missing_policy.safe_to_generate,missing_policy

    callbacks=(
        "onBattlefieldTick",
        "onBattlefieldRegister",
        "onBattlefieldEnter",
        "onBattlefieldLeave",
        "onEventUpdate",
        "onEventFinish",
    )
    complete_text="\n".join(f"function {name}() end" for name in callbacks)
    complete=analyze_dsp_battlefield_callbacks(complete_text,callbacks)
    assert complete.status=="COVERAGE_ALIGNED",complete
    assert not complete.missing_callbacks,complete

    gap=analyze_dsp_battlefield_callbacks("function onBattlefieldTick() end",callbacks)
    assert gap.status=="CALLBACK_GAPS",gap
    assert "onEventFinish" in gap.missing_callbacks,gap

    aligned_plan=plan_dsp_battlefield_callback_adaptation(
        complete,
        source_framework_methods=("new","register"),
    )
    assert aligned_plan.status=="COVERAGE_ALIGNED",aligned_plan
    assert not aligned_plan.missing_callbacks,aligned_plan
    assert not aligned_plan.safe_to_generate,aligned_plan

    gap_plan=plan_dsp_battlefield_callback_adaptation(
        gap,
        source_framework_methods=("new","register"),
    )
    assert gap_plan.status=="MANUAL_REQUIRED",gap_plan
    assert "onEventFinish" in gap_plan.missing_callbacks,gap_plan
    assert not gap_plan.safe_to_generate,gap_plan

    generated=generated_outputs_for_dsp_battlefield(additive,update_policy)
    assert len(generated)==2,generated
    assert any("bcnm_battlefield" in output.relative_path for output in generated),generated
    assert any("bcnm_info" in output.relative_path for output in generated),generated

    no_change=generated_outputs_for_dsp_battlefield(same,same_policy)
    assert not no_change,no_change

    print("DSP battlefield reshape self-test: PASS")


if __name__=="__main__":
    main()
