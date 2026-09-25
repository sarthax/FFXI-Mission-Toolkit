#!/usr/bin/env python3
"""Regression smoke for unsupported-route probing."""
from workbench.migrations.backend_probe import probe_lsb_to_dsp_lua


def main():
    probe=probe_lsb_to_dsp_lua("local x = xi.status.NORMAL\n")
    assert probe.route=="LSB->DSP:LUA",probe
    assert probe.status in {"GAPS_FOUND","CANDIDATE_CLEAN"},probe
    assert isinstance(probe.converted_text,str),probe
    print("migration backend probe self-test: PASS")


if __name__=="__main__":
    main()
