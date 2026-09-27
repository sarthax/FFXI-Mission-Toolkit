#!/usr/bin/env python3
from workbench.plugins.domain.battlefield_dsp import (
    propose_dsp_battlefield_membership,
    propose_dsp_battlefield_policy,
)
from workbench.plugins.domain.battlefield_validation import validate_dsp_battlefield_proposals


def main():
    target=[
        {"battlefield_id":960,"battlefield_number":1,"entity_id":101,"conditions":3},
    ]
    additive=propose_dsp_battlefield_membership(960,((101,102),),target)
    policy=propose_dsp_battlefield_policy(
        960,
        {"level_cap":40},
        {"battlefield_id":960,"level_cap":50},
    )
    results=validate_dsp_battlefield_proposals(additive,policy)
    assert len(results)==2,results
    assert all(result.status=="READY" for result in results),results

    drift=propose_dsp_battlefield_membership(
        960,
        ((101,),),
        target+[{"battlefield_id":960,"battlefield_number":2,"entity_id":999,"conditions":3}],
    )
    drift_result=validate_dsp_battlefield_proposals(drift,None)[0]
    assert drift_result.status=="MANUAL_REQUIRED",drift_result

    exact=propose_dsp_battlefield_policy(
        960,
        {"level_cap":40},
        {"battlefield_id":960,"level_cap":40},
    )
    assert validate_dsp_battlefield_proposals(None,exact)[0].status=="NOT_REQUIRED"

    print("generated DSP battlefield SQL validation self-test: PASS")


if __name__=="__main__":
    main()
