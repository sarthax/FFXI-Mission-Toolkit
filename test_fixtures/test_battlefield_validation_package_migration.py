#!/usr/bin/env python3
import os
import subprocess
import sys
import tempfile

from workbench.packages.battlefields import dsp as canonical_dsp
from workbench.plugins.domain import battlefield_dsp as legacy_dsp
from workbench.validation import battlefields as canonical_validation
from workbench.plugins.domain import battlefield_validation as legacy_validation


def main():
    assert legacy_dsp is canonical_dsp
    assert legacy_validation is canonical_validation

    target=[
        {"battlefield_id":960,"battlefield_number":1,"entity_id":101,"conditions":3},
    ]
    additive=canonical_dsp.propose_dsp_battlefield_membership(960,((101,102),),target)
    assert additive.status=="ADDITIVE",additive
    assert additive.insert_sql==("INSERT INTO `bcnm_battlefield` VALUES (960,1,102,3);",),additive

    policy=canonical_dsp.propose_dsp_battlefield_policy(
        960,
        {"level_cap":40,"is_mission":True},
        {"battlefield_id":960,"level_cap":50,"is_mission":1},
    )
    assert policy.status=="UPDATE_PROPOSAL",policy
    assert policy.update_sql=="UPDATE `bcnm_info` SET `levelCap`=40 WHERE `bcnmId`=960;",policy

    outputs=canonical_dsp.generated_outputs_for_dsp_battlefield(additive,policy)
    assert len(outputs)==2,outputs
    assert {item.artifact_type for item in outputs}=={"SQL"},outputs

    results=canonical_validation.validate_dsp_battlefield_proposals(additive,policy)
    assert [item.status for item in results]==["READY","READY"],results

    drift=canonical_dsp.propose_dsp_battlefield_membership(
        960,
        ((101,),),
        target+[{"battlefield_id":960,"battlefield_number":2,"entity_id":999,"conditions":3}],
    )
    assert canonical_validation.validate_dsp_battlefield_proposals(drift,None)[0].status=="MANUAL_REQUIRED"

    callback_surface=canonical_dsp.analyze_dsp_battlefield_callbacks(
        "function onBattlefieldInitialise()\nend\n",
        ("onBattlefieldInitialise","onBattlefieldWin"),
    )
    callback_plan=canonical_dsp.plan_dsp_battlefield_callback_adaptation(callback_surface)
    assert callback_plan.status=="MANUAL_REQUIRED",callback_plan
    assert callback_plan.safe_to_generate is False,callback_plan

    with tempfile.TemporaryDirectory() as tmp:
        code=(
            "import workbench.packages.battlefields.dsp as d; "
            "import workbench.validation.battlefields as v; "
            "import workbench.plugins.domain.battlefield_dsp as ld; "
            "import workbench.plugins.domain.battlefield_validation as lv; "
            "assert ld is d; assert lv is v; "
            "p=d.propose_dsp_battlefield_policy(1, {'level_cap':40}, {'battlefield_id':1,'level_cap':50}); "
            "assert v.validate_dsp_battlefield_proposals(None,p)[0].status=='READY'"
        )
        env=dict(os.environ)
        completed=subprocess.run([sys.executable,"-c",code],cwd=tmp,env=env,check=False)
        assert completed.returncode==0,completed.returncode

    print("battlefield Validation/Packages migration: PASS")


if __name__=="__main__":
    main()
