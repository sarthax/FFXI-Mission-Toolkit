#!/usr/bin/env python3
from workbench.plugins.domain.battlefield_dsp import (
    propose_dsp_battlefield_membership,
    propose_dsp_battlefield_policy,
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

    print("DSP battlefield membership/policy proposal self-test: PASS")


if __name__=="__main__":
    main()
