#!/usr/bin/env python3
from workbench.migrations.backend_probe import probe_lsb_to_dsp_lua
from workbench.migrations.backend_probe_plan import plan_lsb_dsp_lua_probe


def main():
    probe=probe_lsb_to_dsp_lua(
        "local mission = Mission:new(1,2)\n"
        "mission:setVar(player,'Status',1)\n"
        "local x = player:getLocalVar('x')\n"
    )
    action=plan_lsb_dsp_lua_probe(
        probe,
        "migration:test",
        artifact_id="artifact:test",
        source_path="scripts/test.lua",
    )
    assert action.action=="MANUAL_REVIEW",action
    assert action.status=="MANUAL_REQUIRED",action
    assert action.metadata["adaptation_type"]=="STRUCTURAL_FRAMEWORK_ADAPTATION",action
    assert "setVar" in action.metadata["framework_methods"],action
    assert "getLocalVar" in action.metadata["binding_candidate_methods"],action
    print("migration backend probe planner self-test: PASS")


if __name__=="__main__":
    main()
