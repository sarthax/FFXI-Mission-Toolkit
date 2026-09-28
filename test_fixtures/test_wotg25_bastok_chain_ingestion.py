#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from workbench.plugins.domain.mission_ingest import ingest_branching_truth
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions,
    correlate_lsb_handlers,
    mission_extraction_metrics,
)

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"test_fixtures"/"fixtures"
TRUTH=FIX/"wotg25_branching_mission_truth.json"
MISSION=FIX/"lsb_wotg25_the_will_of_the_world.lua"
Q9=FIX/"lsb_wotg_bastok9_beneath_the_mask.lua"
Q10=FIX/"lsb_wotg_bastok10_what_price_loyalty.lua"


def _quest_prog_checks(lua: str) -> set[int]:
    return {int(value) for value in re.findall(r"vars\.Prog\s*==\s*(\d+)",lua)}


def _quest_prog_writes(lua: str) -> set[int]:
    return {
        int(value)
        for value in re.findall(r"quest:setVar\(player,\s*'Prog',\s*(\d+)\)",lua)
    }


def _quest_events(lua: str) -> set[int]:
    out={
        int(value)
        for value in re.findall(r"quest:(?:progressEvent|event|progressCutscene)\((\d+)",lua)
    }
    out.update(int(value) for value in re.findall(r"\[(\d+)\]\s*=\s*function\(player,\s*csid",lua))
    return out


def main():
    truth=json.loads(TRUTH.read_text(encoding="utf-8"))
    mission_lua=MISSION.read_text(encoding="utf-8")
    q9_lua=Q9.read_text(encoding="utf-8")
    q10_lua=Q10.read_text(encoding="utf-8")

    # Root mission: current structural Mission DSL extraction.
    raw=correlate_lsb_handlers(
        mission_lua,
        feature_id="mission:wotg:the_will_of_the_world",
    )
    chained=chain_event_transitions(raw)
    assert not raw.validate(),raw.validate()
    assert not chained.validate(),chained.validate()

    root=next(
        transition for transition in chained.transitions
        if transition.metadata.get("logical_event_chain")
        and transition.event
        and transition.event.zone=="SOUTHERN_SAN_DORIA_S"
        and transition.event.actor=="Raustigne"
        and transition.event.event_id==149
    )
    assert any(effect.effect=="COMPLETE" for effect in root.effects),root
    assert root.metadata.get("section_eligibility_status")=="NO_STATUS_REQUIREMENTS",root.metadata
    root_metrics=mission_extraction_metrics(chained)
    assert root_metrics["event_chains"]==1,root_metrics
    assert root_metrics["section_eligibility_status_counts"].get("NO_STATUS_REQUIREMENTS",0)>=1,root_metrics

    # Branch chain: normalized evidence ingestion remains the explicit fallback until
    # Quest DSL source extraction exists.
    normalized=ingest_branching_truth(truth)
    assert not normalized.validate(),normalized.validate()
    branch_gate=next(
        transition for transition in normalized.transitions
        if transition.transition_id=="mission:branch-gate"
    )
    assert branch_gate.gate is not None and branch_gate.gate.logic=="ANY",branch_gate

    bastok_q9_states={
        state.state_id for state in normalized.states
        if state.state_id.startswith("branch:bastok_branch:quest9:prog:")
    }
    bastok_q10_states={
        state.state_id for state in normalized.states
        if state.state_id.startswith("branch:bastok_branch:quest10:prog:")
    }
    assert {int(state.rsplit(":",1)[-1]) for state in bastok_q9_states}==set(range(7)),bastok_q9_states
    assert {int(state.rsplit(":",1)[-1]) for state in bastok_q10_states}==set(range(7)),bastok_q10_states
    implementation_gap=next(
        transition for transition in normalized.transitions
        if transition.transition_id=="bastok_branch:quest10:implementation-gap"
    )
    assert implementation_gap.implementation_status=="IMPLEMENTATION_GAP",implementation_gap

    # Source-alignment checks keep the normalized fallback tied to current LSB Lua.
    assert "Quest:new" in q9_lua and "BENEATH_THE_MASK" in q9_lua,q9_lua[:200]
    assert "Quest:new" in q10_lua and "WHAT_PRICE_LOYALTY" in q10_lua,q10_lua[:200]
    assert _quest_prog_checks(q9_lua)==set(range(7)),_quest_prog_checks(q9_lua)
    assert _quest_prog_checks(q10_lua)==set(range(7)),_quest_prog_checks(q10_lua)
    assert _quest_prog_writes(q9_lua)==set(range(1,7)),_quest_prog_writes(q9_lua)
    assert _quest_prog_writes(q10_lua)==set(range(1,7)),_quest_prog_writes(q10_lua)

    expected_q9_events={345,351,346,352,42,44,2,43,45,347,353,1,7}
    expected_q10_events={348,354,10,11,349,355,8,9,357,10000,350,356}
    assert expected_q9_events <= _quest_events(q9_lua),expected_q9_events-_quest_events(q9_lua)
    assert expected_q10_events <= _quest_events(q10_lua),expected_q10_events-_quest_events(q10_lua)

    assert "LUMP_OF_BEESWAX" in q9_lua and "JAR_OF_RED_TEXTILE_DYE" in q9_lua
    assert "WAX_SEAL" in q9_lua
    assert "SACK_OF_VICTUALS" in q10_lua
    assert "COMMANDERS_ENDORSEMENT" in q10_lua
    assert "What Price Loyalty instance is not implemented currently." in q10_lua
    assert "[10000] = function" in q10_lua
    assert "xi.zone.XARCABARD_S" in q10_lua

    # The test intentionally records the current ingestion boundary. Quest source is
    # present and verified, but structural Quest DSL extraction is still the next gap.
    modes={
        "root_mission":"lsb_structural",
        "bastok_quest9":"normalized_truth_fallback",
        "bastok_quest10":"normalized_truth_fallback",
    }
    assert modes["root_mission"]=="lsb_structural"
    assert modes["bastok_quest9"]==modes["bastok_quest10"]=="normalized_truth_fallback"

    print("WotG25 Bastok chain ingestion stress: PASS")
    print("root_transitions",len(chained.transitions),"root_event_chains",root_metrics["event_chains"])
    print("normalized_states",len(normalized.states),"normalized_transitions",len(normalized.transitions))
    print("next_gap","Quest DSL structural extraction")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
