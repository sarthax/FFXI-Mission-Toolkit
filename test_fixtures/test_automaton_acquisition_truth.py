#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"test_fixtures"/"fixtures"/"automaton_acquisition_dependency_truth.json"

def main():
    p=json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert p["kind"]=="WORKBENCH_ACQUISITION_TRUTH_SET",p
    subjects={x["name"]:x for x in p["subjects"]}
    assert {"Economizer","Heat Seeker"} <= set(subjects),subjects

    econ=subjects["Economizer"]
    assert any(x["type"]=="SHOP" for x in econ["verified_server_acquisition"]),econ
    assert any(x["type"]=="QUEST_OR_INSTANCE_REWARD" for x in econ["external_retail_acquisition"]),econ
    assert any(x["type"]=="ANNM_REWARD" for x in econ["external_retail_acquisition"]),econ

    heat=subjects["Heat Seeker"]
    assert sum(1 for x in heat["verified_server_acquisition"] if x["type"]=="DROP_POOL")>=2,heat
    synth=next(x for x in heat["external_retail_acquisition"] if x["type"]=="SYNTHESIS")
    assert synth["craft"]=="Alchemy",synth
    assert synth["required_key_item"]=="Iatrochemistry",synth
    assert len(synth["ingredients"])==5,synth

    relations={x["relation"] for x in p["required_acquisition_relations"]}
    for rel in ("SOLD_BY","DROPPED_BY","CRAFTED_BY","REWARDED_BY","REQUIRES_INGREDIENT","ALTERNATE_ACQUISITION"):
        assert rel in relations,relations

    print("automaton acquisition truth-set self-test: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
