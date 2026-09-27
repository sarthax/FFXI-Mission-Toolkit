#!/usr/bin/env python3
"""Validate the Medusa dependency-proof truth set remains structurally complete."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "test_fixtures" / "fixtures" / "medusa_arrapago_dependency_truth.json"


def main():
    payload=json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["kind"]=="WORKBENCH_DEPENDENCY_TRUTH_SET",payload
    subject=payload["subject"]
    assert subject["name"]=="Medusa",subject
    assert subject["zone"]=="Arrapago Reef",subject
    assert subject["zone_id"]==54,subject
    assert subject["entity_id"]==16998862,subject

    facts=payload["verified_facts"]
    helpers=facts["helpers"]
    assert [row["entity_id"] for row in helpers]==[16998863,16998864,16998865,16998866],helpers
    assert {row["template"] for row in helpers}=={"Lamia_Exon"},helpers

    helper=facts["helper_template"]
    assert helper["spell_list_id"]==28,helper
    assert helper["skill_list_id"]==171,helper

    medusa_skills=facts["skill_list"]
    assert medusa_skills["id"]==725,medusa_skills
    assert medusa_skills["skill_ids"]==[1808,1809,1810,1812,1813,1814],medusa_skills

    definitions={row["id"]:row["name"] for row in facts["skill_definitions"]}
    assert definitions=={
        1808:"petrifaction",
        1809:"shadow_thrust",
        1810:"tail_slap",
        1812:"pinning_shot",
        1813:"calcifying_deluge",
        1814:"gorgon_dance",
    },definitions

    special=facts["job_special"]
    assert special["skill_id"]==1931,special
    assert special["enum_symbol"]=="xi.mobSkill.EES_LAMIA",special

    variants=facts["alternate_variants"]
    assert {row["zone"] for row in variants}=={"Al Zahbi","Bhaflau Thickets"},variants
    assert all(row["relation"]=="SYSTEM_COUPLED_CONDITIONAL_DEPENDENCY" for row in variants),variants
    assert facts["besieged_system"]["current_lsb_status"]=="HOOKS_PRESENT_BUT_EMPTY",facts["besieged_system"]

    required={row["key"]:row["expected_status"] for row in payload["required_dependency_classes"]}
    for key in (
        "root_entity_template",
        "helper_entities",
        "helper_template",
        "medusa_skill_list",
        "mob_skill_scripts",
        "job_special_mixin",
        "loot_items",
        "title_and_text",
        "lua_engine_calls",
        "alternate_medusa_variants",
    ):
        assert key in required,key
    assert required["alternate_medusa_variants"]=="QUESTIONABLE_SYSTEM_DEPENDENCY",required
    assert required["besieged_system"]=="REQUIRED_OR_EXPLICITLY_INCOMPLETE",required

    gaps=payload["known_current_toolkit_gaps"]
    assert any("mob_skill_lists" in gap for gap in gaps),gaps
    assert any("mob_spell_lists" in gap for gap in gaps),gaps
    assert any("MEDUSA + 1" in gap for gap in gaps),gaps
    assert any("YAML loot" in gap for gap in gaps),gaps

    print("Medusa dependency truth-set self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
