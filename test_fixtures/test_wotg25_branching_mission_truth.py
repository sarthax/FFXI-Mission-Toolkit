#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"test_fixtures"/"fixtures"/"wotg25_branching_mission_truth.json"

def main():
    p=json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert p["kind"]=="WORKBENCH_MISSION_TRUTH_SET",p
    assert p["subject"]["mission"]=="The Will of the World",p
    branches=p["wiki_truth"]["branch_requirement"]["branches"]
    assert {x["nation"] for x in branches}=={"Bastok","San d'Oria","Windurst"},branches

    server=p["verified_server_state_machine"]
    gate=server["mission26_gate"]
    assert gate["logic"]=="OR",gate
    assert set(gate["accepted_quest_completions"])=={
        "WHAT_PRICE_LOYALTY","BLOOD_OF_HEROES","HOWL_FROM_THE_HEAVENS"
    },gate

    bastok=server["bastok_branch"]
    q9=bastok["quest9"]
    q10=bastok["quest10"]
    assert q9["vars"]["Prog"]==[0,1,2,3,4,5,6],q9
    assert q10["vars"]["Prog"]==[0,1,2,3,4,5,6],q10
    assert any(x["symbol"]=="WAX_SEAL" for x in q9["key_items"]),q9
    assert any(x["symbol"]=="COMMANDERS_ENDORSEMENT" for x in q10["key_items"]),q10
    assert "not implemented" in q10["implementation_gap"].lower(),q10

    wind=server["windurst_branch"]
    assert wind["scripts_found"] is False,wind
    assert wind["status"]=="EXPECTED_BRANCH_MISSING_OR_UNIMPLEMENTED_IN_CURRENT_SOURCE",wind

    classes={x["key"]:x["expected_status"] for x in p["required_dependency_classes"]}
    assert classes["cross_branch_alternatives"]=="OR_BRANCH",classes
    assert classes["expected_missing_content"]=="VISIBLE_GAP",classes
    assert classes["event_csids"]=="REQUIRED",classes
    assert classes["key_item_lifecycle"]=="REQUIRED",classes

    rules=p["package_scope_rules"]
    assert any("CSID" in x for x in rules),rules
    assert any("placeholder event" in x for x in rules),rules

    print("WotG branching mission truth-set self-test: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
