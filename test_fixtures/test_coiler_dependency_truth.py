#!/usr/bin/env python3
"""Validate the Coiler dependency-proof truth set."""
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"test_fixtures"/"fixtures"/"coiler_attachment_dependency_truth.json"

def main():
    payload=json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["kind"]=="WORKBENCH_DEPENDENCY_TRUTH_SET",payload
    assert payload["subject"]["name"]=="Coiler",payload

    facts=payload["verified_facts"]
    assert facts["inventory_item"]["item_id"]==2413,facts
    puppet=facts["puppet_equipment_record"]
    assert puppet["item_id"]==8583,puppet
    assert puppet["internal_attachment_index"]==135,puppet
    assert puppet["equip_slot"]==3,puppet
    assert puppet["element_slots_raw"]==131072,puppet

    mod=facts["automaton_modifier"]
    assert mod["modifier"]=="xi.mod.DOUBLE_ATTACK",mod
    assert mod["values_by_maneuvers"]==[3,10,20,30],mod
    assert mod["optic_fiber_eligible"] is True,mod

    assert len(facts["weapon_skill_consumers"])>=7,facts["weapon_skill_consumers"]
    classes={x["key"]:x["expected_status"] for x in payload["required_dependency_classes"]}
    assert classes["acquisition_paths"]=="QUESTIONABLE_USER_SCOPE",classes
    assert classes["conditional_interactions"]=="CONDITIONAL",classes
    assert classes["identity_mapping"]=="REQUIRED",classes

    gaps=payload["known_current_toolkit_gaps"]
    assert any("item_puppet" in x for x in gaps),gaps
    assert any("dynamic C++ Lua dispatch" in x for x in gaps),gaps
    assert any("Conditional interactions" in x for x in gaps),gaps

    print("Coiler dependency truth-set self-test: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
