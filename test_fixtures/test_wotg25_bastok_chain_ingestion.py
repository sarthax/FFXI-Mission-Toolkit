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
from workbench.plugins.domain.quest_lsb_extract import (
    chain_quest_event_transitions,
    correlate_lsb_quest_handlers,
    quest_extraction_metrics,
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

    # Cross-nation Mission-26 OR gate still comes from the normalized truth fixture.
    normalized=ingest_branching_truth(truth)
    assert not normalized.validate(),normalized.validate()
    branch_gate=next(
        transition for transition in normalized.transitions
        if transition.transition_id=="mission:branch-gate"
    )
    assert branch_gate.gate is not None and branch_gate.gate.logic=="ANY",branch_gate

    # Bastok quest chain: both files must now be structurally reconstructed from Lua.
    q9_raw=correlate_lsb_quest_handlers(
        q9_lua,
        feature_id="quest:crystal_war:beneath_the_mask",
    )
    q9=chain_quest_event_transitions(q9_raw)
    q10_raw=correlate_lsb_quest_handlers(
        q10_lua,
        feature_id="quest:crystal_war:what_price_loyalty",
    )
    q10=chain_quest_event_transitions(q10_raw)
    assert not q9_raw.validate(),q9_raw.validate()
    assert not q9.validate(),q9.validate()
    assert not q10_raw.validate(),q10_raw.validate()
    assert not q10.validate(),q10.validate()

    assert q9.metadata.get("extractor")=="lsb_quest_static_literal",q9.metadata
    assert q10.metadata.get("extractor")=="lsb_quest_static_literal",q10.metadata
    assert q9.metadata.get("quest_symbol")=="BENEATH_THE_MASK",q9.metadata
    assert q10.metadata.get("quest_symbol")=="WHAT_PRICE_LOYALTY",q10.metadata
    assert q9.metadata.get("reward_item")=="SUPER_RERAISER",q9.metadata
    assert q10.metadata.get("reward_item")=="FOURTH_STAFF",q10.metadata

    q9_channels={channel.channel_id:channel for channel in q9.channels}
    q10_channels={channel.channel_id:channel for channel in q10.channels}
    assert set(q9_channels["quest_var:Prog"].values)==set(range(1,7)),q9_channels
    assert set(q10_channels["quest_var:Prog"].values)==set(range(1,7)),q10_channels
    assert set(q9_channels["quest_status"].values)=={"QUEST_ACCEPTED","QUEST_AVAILABLE"},q9_channels
    assert set(q10_channels["quest_status"].values)=={
        "QUEST_ACCEPTED","QUEST_AVAILABLE","QUEST_COMPLETED"
    },q10_channels

    q9_states={state.state_id for state in q9.states}
    q10_states={state.state_id for state in q10.states}
    for value in range(7):
        assert f"state:quest_var:Prog={value}" in q9_states,(value,q9_states)
        assert f"state:quest_var:Prog={value}" in q10_states,(value,q10_states)
    assert "state:quest_status=QUEST_AVAILABLE" in q9_states,q9_states
    assert "state:quest_status=QUEST_ACCEPTED" in q9_states,q9_states
    assert "state:quest_status=QUEST_COMPLETED" in q9_states,q9_states
    assert "state:quest_status=QUEST_COMPLETED" in q10_states,q10_states

    q9_events={(t.event.zone,t.event.actor,t.event.event_id) for t in q9.transitions if t.event}
    q10_events={(t.event.zone,t.event.actor,t.event.event_id) for t in q10.transitions if t.event}
    assert ("VUNKERL_INLET_S","Leadavox",2) in q9_events,q9_events
    assert ("BEAUCEDINE_GLACIER_S","Hoarfang",7) in q9_events,q9_events
    assert ("NORTH_GUSTABERG_S","Roderich",10) in q10_events,q10_events
    assert ("XARCABARD_S","Forbidding_Portal",9) in q10_events,q10_events
    assert ("EVERBLOOM_HOLLOW",None,10000) in q10_events,q10_events

    q9_effects={(effect.effect,effect.subject) for t in q9.transitions for effect in t.effects}
    q10_effects={(effect.effect,effect.subject) for t in q10.transitions for effect in t.effects}
    assert ("GRANT","key_item:WAX_SEAL") in q9_effects,q9_effects
    assert ("REMOVE","key_item:WAX_SEAL") in q9_effects,q9_effects
    assert ("COMPLETE_TRADE","trade") in q9_effects,q9_effects
    assert ("GRANT","key_item:SACK_OF_VICTUALS") in q10_effects,q10_effects
    assert ("REMOVE","key_item:SACK_OF_VICTUALS") in q10_effects,q10_effects
    assert ("GRANT","key_item:COMMANDERS_ENDORSEMENT") in q10_effects,q10_effects
    assert ("TELEPORT","player") in q10_effects,q10_effects

    q9_start=next(
        t for t in q9.transitions
        if t.event and t.event.zone=="BASTOK_MARKETS_S"
        and t.event.actor=="Gentle_Tiger" and t.event.event_id==345
    )
    assert any(
        row["subject"]=="quest:HONOR_UNDER_FIRE" and row["operator"]=="COMPLETE"
        for row in q9_start.metadata.get("section_eligibility_conditions",())
    ),q9_start.metadata
    assert any(
        row["subject"]=="mission:WOTG:current"
        and row["operator"]=="GE"
        and row["value"]=="FATE_IN_HAZE"
        for row in q9_start.metadata.get("section_eligibility_conditions",())
    ),q9_start.metadata

    q10_start=next(
        t for t in q10.transitions
        if t.event and t.event.zone=="BASTOK_MARKETS_S"
        and t.event.actor=="Gentle_Tiger" and t.event.event_id==348
    )
    assert any(
        row["subject"]=="quest:BENEATH_THE_MASK" and row["operator"]=="COMPLETE"
        for row in q10_start.metadata.get("section_eligibility_conditions",())
    ),q10_start.metadata

    implementation_gap=next(
        transition for transition in q10.transitions
        if transition.event
        and transition.event.zone=="EVERBLOOM_HOLLOW"
        and transition.event.event_id==10000
    )
    assert implementation_gap.implementation_status=="IMPLEMENTATION_GAP",implementation_gap
    assert "not implemented" in (
        implementation_gap.metadata.get("implementation_gap_note") or ""
    ).lower(),implementation_gap.metadata

    q9_metrics=quest_extraction_metrics(q9)
    q10_metrics=quest_extraction_metrics(q10)
    assert q9_metrics["event_chain_count"]>0,q9_metrics
    assert q10_metrics["event_chain_count"]>0,q10_metrics
    assert q9_metrics["unmodeled_source_handler_count"]==0,q9_metrics
    assert q10_metrics["unmodeled_source_handler_count"]==0,q10_metrics
    assert q10_metrics["implementation_gap_transition_count"]==1,q10_metrics

    # Source-alignment checks keep the structural extraction tied to current LSB Lua.
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

    modes={
        "root_mission":"lsb_structural",
        "bastok_quest9":"lsb_structural",
        "bastok_quest10":"lsb_structural",
    }
    assert set(modes.values())=={"lsb_structural"},modes

    print("WotG25 Bastok chain ingestion stress: PASS")
    print("root_transitions",len(chained.transitions),"root_event_chains",root_metrics["event_chains"])
    print("q9_transitions",len(q9.transitions),"q10_transitions",len(q10.transitions))
    print("q10_visible_gaps",q10_metrics["implementation_gap_transition_count"])
    print("next_gap","cross-feature mission-to-quest prerequisite closure")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
