#!/usr/bin/env python3
"""Regression smoke for unsupported-route probing."""
from workbench.migrations.backend_probe import probe_lsb_to_dsp_lua


def main():
    probe=probe_lsb_to_dsp_lua(
        "local mission = Mission:new(1, 2)\n"
        "local x = player:getLocalVar('x')\n"
        "mission:setVar(player, 'Status', 1)\n"
        "function content:entryRequirement(player) return true end\n"
    )
    assert probe.route=="LSB->DSP:LUA",probe
    assert probe.status=="FRAMEWORK_ADAPTATION_REQUIRED",probe
    assert isinstance(probe.converted_text,str),probe
    assert probe.method_surface is not None,probe
    assert "new" in probe.method_surface.framework_methods,probe
    assert "setVar" in probe.method_surface.framework_methods,probe
    assert "getLocalVar" in probe.method_surface.binding_candidate_methods,probe
    assert "entryRequirement" in probe.method_surface.method_definitions,probe
    print("migration backend probe self-test: PASS")


if __name__=="__main__":
    main()
