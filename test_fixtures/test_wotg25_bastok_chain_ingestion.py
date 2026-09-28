#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

from workbench.plugins.domain.mission_ingest import ingest_branching_truth
from workbench.plugins.domain.mission_feature_closure import (
    build_feature_requirement_closure,
    dependency_summary,
)
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions,
    correlate_lsb_handlers,
    mission_extraction_metrics,
)
from workbench.plugins.domain.quest_lsb_extract import quest_extraction_metrics
from workbench.plugins.domain.mission_source_catalog import LsbFeatureSourceCatalog

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

    # Bastok quest chain: source catalog discovery must load dependencies on demand.
    catalog=LsbFeatureSourceCatalog(FIX)
    assert catalog.source_for("quest:WHAT_PRICE_LOYALTY") is not None,catalog.subjects()
    assert catalog.source_for("quest:BENEATH_THE_MASK") is not None,catalog.subjects()
    assert catalog.source_for("quest:HONOR_UNDER_FIRE") is not None,catalog.subjects()
    assert catalog.source_for("quest:QUELLING_THE_STORM") is not None,catalog.subjects()
    assert catalog.source_for("quest:FIRE_IN_THE_HOLE") is not None,catalog.subjects()
    assert catalog.source_for("quest:STORM_ON_THE_HORIZON") is not None,catalog.subjects()
    assert catalog.source_for("quest:BURDEN_OF_SUSPICION") is not None,catalog.subjects()
    assert catalog.source_for("quest:LIGHT_IN_THE_DARKNESS") is not None,catalog.subjects()

    closure=build_feature_requirement_closure(
        chained,
        entry_gates=(branch_gate.gate,),
        selected_any_subjects=("quest:WHAT_PRICE_LOYALTY",),
        resolver=catalog.resolve_machine,
    )
    closure_summary=dependency_summary(closure)
    assert set(closure.feature_ids)=={
        "mission:wotg:the_will_of_the_world",
        "quest:crystal_war:what_price_loyalty",
        "quest:crystal_war:beneath_the_mask",
        "quest:crystal_war:honor_under_fire",
        "quest:crystal_war:quelling_the_storm",
        "quest:crystal_war:fire_in_the_hole",
        "quest:crystal_war:storm_on_the_horizon",
        "quest:crystal_war:burden_of_suspicion",
        "quest:crystal_war:light_in_the_darkness",
    },closure
    assert catalog.cached_subjects()==(
        "quest:BENEATH_THE_MASK",
        "quest:BURDEN_OF_SUSPICION",
        "quest:FIRE_IN_THE_HOLE",
        "quest:HONOR_UNDER_FIRE",
        "quest:LIGHT_IN_THE_DARKNESS",
        "quest:QUELLING_THE_STORM",
        "quest:STORM_ON_THE_HORIZON",
        "quest:WHAT_PRICE_LOYALTY",
    ),catalog.cached_subjects()
    assert "quest:BLOOD_OF_HEROES" in closure.skipped_alternatives,closure
    assert "quest:HOWL_FROM_THE_HEAVENS" in closure.skipped_alternatives,closure
    assert closure.unresolved_subjects==("mission:BACK_TO_THE_BEGINNING","quest:FIRES_OF_DISCONTENT"),closure

    q10=catalog.cached_machine("quest:WHAT_PRICE_LOYALTY")
    q9=catalog.cached_machine("quest:BENEATH_THE_MASK")
    q8=catalog.cached_machine("quest:HONOR_UNDER_FIRE")
    q7=catalog.cached_machine("quest:QUELLING_THE_STORM")
    q6=catalog.cached_machine("quest:FIRE_IN_THE_HOLE")
    q5=catalog.cached_machine("quest:STORM_ON_THE_HORIZON")
    q4=catalog.cached_machine("quest:BURDEN_OF_SUSPICION")
    q3=catalog.cached_machine("quest:LIGHT_IN_THE_DARKNESS")
    assert all(machine is not None for machine in (q10,q9,q8,q7,q6,q5,q4,q3)),(q10,q9,q8,q7,q6,q5,q4,q3)

    assert q9.metadata.get("catalog_discovered") is True,q9.metadata
    assert q10.metadata.get("catalog_discovered") is True,q10.metadata
    assert q8.metadata.get("catalog_discovered") is True,q8.metadata
    assert q7.metadata.get("catalog_discovered") is True,q7.metadata
    assert q6.metadata.get("catalog_discovered") is True,q6.metadata
    assert q5.metadata.get("catalog_discovered") is True,q5.metadata
    assert q4.metadata.get("catalog_discovered") is True,q4.metadata
    assert q3.metadata.get("catalog_discovered") is True,q3.metadata
    assert q9.metadata.get("quest_symbol")=="BENEATH_THE_MASK",q9.metadata
    assert q10.metadata.get("quest_symbol")=="WHAT_PRICE_LOYALTY",q10.metadata
    assert q8.metadata.get("quest_symbol")=="HONOR_UNDER_FIRE",q8.metadata
    assert q7.metadata.get("quest_symbol")=="QUELLING_THE_STORM",q7.metadata
    assert q6.metadata.get("quest_symbol")=="FIRE_IN_THE_HOLE",q6.metadata
    assert q5.metadata.get("quest_symbol")=="STORM_ON_THE_HORIZON",q5.metadata
    assert q4.metadata.get("quest_symbol")=="BURDEN_OF_SUSPICION",q4.metadata
    assert q3.metadata.get("quest_symbol")=="LIGHT_IN_THE_DARKNESS",q3.metadata
    assert q9.metadata.get("reward_item")=="SUPER_RERAISER",q9.metadata
    assert q10.metadata.get("reward_item")=="FOURTH_STAFF",q10.metadata
    assert q8.metadata.get("reward_item")=="ELIXIR_TANK",q8.metadata
    assert q7.metadata.get("reward_item")=="GOBLIN_BELT",q7.metadata
    assert q6.metadata.get("reward_item")=="REPUBLICAN_SILVER_MEDAL",q6.metadata
    assert q5.metadata.get("reward_item")=="ICARUS_WING",q5.metadata
    assert q3.metadata.get("reward_item")=="ADAMAN_INGOT",q3.metadata

    q9_channels={channel.channel_id:channel for channel in q9.channels}
    q10_channels={channel.channel_id:channel for channel in q10.channels}
    assert set(q9_channels["quest_var:Prog"].values)==set(range(1,7)),q9_channels
    assert set(q10_channels["quest_var:Prog"].values)==set(range(1,7)),q10_channels

    q9_states={state.state_id for state in q9.states}
    q10_states={state.state_id for state in q10.states}
    for value in range(7):
        assert f"state:quest_var:Prog={value}" in q9_states,(value,q9_states)
        assert f"state:quest_var:Prog={value}" in q10_states,(value,q10_states)

    q9_events={(t.event.zone,t.event.actor,t.event.event_id) for t in q9.transitions if t.event}
    q10_events={(t.event.zone,t.event.actor,t.event.event_id) for t in q10.transitions if t.event}
    assert ("VUNKERL_INLET_S","Leadavox",2) in q9_events,q9_events
    assert ("BEAUCEDINE_GLACIER_S","Hoarfang",7) in q9_events,q9_events
    assert ("BEADEAUX_S",None,1) in q9_events,q9_events
    assert ("NORTH_GUSTABERG_S","Roderich",10) in q10_events,q10_events
    assert ("XARCABARD_S","Forbidding_Portal",9) in q10_events,q10_events
    assert ("XARCABARD_S",None,8) in q10_events,q10_events
    assert ("XARCABARD_S",None,10) in q10_events,q10_events
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

    implementation_gap=next(
        transition for transition in q10.transitions
        if transition.event
        and transition.event.zone=="EVERBLOOM_HOLLOW"
        and transition.event.event_id==10000
    )
    assert implementation_gap.implementation_status=="IMPLEMENTATION_GAP",implementation_gap

    assert any(
        dependency.source_feature_id=="mission:wotg:the_will_of_the_world"
        and dependency.subject=="quest:WHAT_PRICE_LOYALTY"
        and dependency.logic=="ANY"
        and dependency.resolved_feature_id=="quest:crystal_war:what_price_loyalty"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:what_price_loyalty"
        and dependency.subject=="quest:BENEATH_THE_MASK"
        and dependency.resolved_feature_id=="quest:crystal_war:beneath_the_mask"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:beneath_the_mask"
        and dependency.subject=="quest:HONOR_UNDER_FIRE"
        and dependency.resolved_feature_id=="quest:crystal_war:honor_under_fire"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:honor_under_fire"
        and dependency.subject=="quest:QUELLING_THE_STORM"
        and dependency.status=="RESOLVED"
        and dependency.resolved_feature_id=="quest:crystal_war:quelling_the_storm"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:quelling_the_storm"
        and dependency.subject=="quest:FIRE_IN_THE_HOLE"
        and dependency.status=="RESOLVED"
        and dependency.resolved_feature_id=="quest:crystal_war:fire_in_the_hole"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:fire_in_the_hole"
        and dependency.subject=="quest:STORM_ON_THE_HORIZON"
        and dependency.status=="RESOLVED"
        and dependency.resolved_feature_id=="quest:crystal_war:storm_on_the_horizon"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:storm_on_the_horizon"
        and dependency.subject=="quest:BURDEN_OF_SUSPICION"
        and dependency.status=="RESOLVED"
        and dependency.resolved_feature_id=="quest:crystal_war:burden_of_suspicion"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:burden_of_suspicion"
        and dependency.subject=="quest:LIGHT_IN_THE_DARKNESS"
        and dependency.status=="RESOLVED"
        and dependency.resolved_feature_id=="quest:crystal_war:light_in_the_darkness"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:light_in_the_darkness"
        and dependency.subject=="quest:FIRES_OF_DISCONTENT"
        and dependency.status=="UNRESOLVED"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert any(
        dependency.source_feature_id=="quest:crystal_war:light_in_the_darkness"
        and dependency.subject=="mission:BACK_TO_THE_BEGINNING"
        and dependency.status=="UNRESOLVED"
        for dependency in closure.dependencies
    ),closure.dependencies
    assert closure_summary=={
        "root_feature_id":"mission:wotg:the_will_of_the_world",
        "feature_count":9,
        "dependency_count":17,
        "resolved_dependency_count":8,
        "unresolved_dependency_count":2,
        "skipped_alternative_count":2,
        "cycle_count":0,
    },closure_summary

    q3_metrics=quest_extraction_metrics(q3)
    q4_metrics=quest_extraction_metrics(q4)
    q5_metrics=quest_extraction_metrics(q5)
    q6_metrics=quest_extraction_metrics(q6)
    q7_metrics=quest_extraction_metrics(q7)
    q9_metrics=quest_extraction_metrics(q9)
    q10_metrics=quest_extraction_metrics(q10)
    assert q3_metrics["unmodeled_source_handler_count"]==0,q3_metrics
    assert q4_metrics["unmodeled_source_handler_count"]==0,q4_metrics
    assert q5_metrics["unmodeled_source_handler_count"]==0,q5_metrics
    assert q6_metrics["unmodeled_source_handler_count"]==0,q6_metrics
    assert q6_metrics["event_relay_count"]==1,q6_metrics
    assert q7_metrics["unmodeled_source_handler_count"]==0,q7_metrics
    assert q9_metrics["unmodeled_source_handler_count"]==0,q9_metrics
    assert q10_metrics["unmodeled_source_handler_count"]==0,q10_metrics

    fire_relay=next(
        transition for transition in q6.transitions
        if transition.metadata.get("logical_event_chain")
        and transition.event
        and transition.event.zone=="BASTOK_MARKETS_S"
        and transition.event.event_id==60
    )
    assert any(
        effect.effect=="START" and effect.subject=="event" and effect.value==77
        for effect in fire_relay.effects
    ),fire_relay
    assert any(
        effect.effect=="START" and effect.subject=="quest"
        for effect in fire_relay.effects
    ),fire_relay

    light_trade=next(
        transition for transition in q3.transitions
        if transition.trigger=="TRADE"
        and transition.event
        and transition.event.zone=="BASTOK_MARKETS_S"
        and transition.event.actor=="Blatherix"
        and transition.event.event_id==23
        and transition.gate is not None
        and transition.gate.logic=="ANY"
    )
    trade_values={condition.value for condition in light_trade.gate.conditions}
    assert (("CHUNK_OF_GOBLIN_CHOCOLATE",30),) in trade_values,trade_values
    assert (("gil",5000),) in trade_values,trade_values

    light_complete=next(
        transition for transition in q3.transitions
        if transition.event
        and transition.event.zone=="BASTOK_MARKETS_S"
        and transition.event.actor=="Gentle_Tiger"
        and transition.event.event_id==27
    )
    assert any(
        effect.effect=="SET_VAR"
        and effect.subject=="quest:BURDEN_OF_SUSPICION:var:Timer"
        for effect in light_complete.effects
    ),light_complete
    assert any(
        effect.effect=="SET_STATE"
        and effect.subject=="quest:BURDEN_OF_SUSPICION:must_zone"
        and effect.value is True
        for effect in light_complete.effects
    ),light_complete

    burden_start=next(
        transition for transition in q4.transitions
        if transition.event
        and transition.event.zone=="BASTOK_MARKETS_S"
        and transition.event.actor=="Gentle_Tiger"
        and transition.event.event_id==30
    )
    assert burden_start.gate is not None,burden_start
    burden_conditions={
        (condition.subject,condition.operator,condition.value)
        for condition in burden_start.gate.conditions
    }
    assert ("quest_must_zone","EQ",False) in burden_conditions,burden_conditions
    assert ("quest_var:Timer","LE","VanadielUniqueDay()") in burden_conditions,burden_conditions
    assert any(
        effect.effect=="REMOVE"
        and effect.subject=="key_item:WARNING_LETTER"
        for effect in burden_start.effects
    ),burden_start

    storm_zone_in=next(
        transition for transition in q5.transitions
        if transition.trigger=="ZONE_IN"
        and transition.event
        and transition.event.zone=="BASTOK_MARKETS_S"
        and transition.event.event_id==56
    )
    assert storm_zone_in.gate is not None,storm_zone_in
    storm_conditions={
        (condition.subject,condition.operator,condition.value)
        for condition in storm_zone_in.gate.conditions
    }
    assert ("quest_var:Prog","EQ",1) in storm_conditions,storm_conditions
    assert ("previous_zone","EQ","NORTH_GUSTABERG_S") in storm_conditions,storm_conditions
    assert ("quest_must_zone","EQ",False) in storm_conditions,storm_conditions
    assert ("quest_var:Timer","LE","VanadielUniqueDay()") in storm_conditions,storm_conditions

    storm_start=next(
        transition for transition in q5.transitions
        if transition.event
        and transition.event.zone=="BASTOK_MARKETS_S"
        and transition.event.event_id==37
        and transition.trigger=="NPC_INTERACT"
    )
    assert any(
        effect.effect=="SET_STATE"
        and effect.subject=="quest_must_zone"
        and effect.value is True
        for effect in storm_start.effects
    ),storm_start

    solitary_paths=[
        transition for transition in q6.transitions
        if transition.event
        and transition.event.actor=="Solitary_Ant"
        and transition.trigger=="NPC_INTERACT"
    ]
    assert any(
        transition.gate
        and any(
            condition.subject=="quest_var:Prog"
            and condition.operator=="GE"
            and condition.value==0
            for condition in transition.gate.conditions
        )
        for transition in solitary_paths
    ),solitary_paths
    assert any(
        transition.gate
        and any(
            condition.subject=="quest_var:Prog"
            and condition.operator=="GE"
            and condition.value==2
            for condition in transition.gate.conditions
        )
        for transition in solitary_paths
    ),solitary_paths

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
    print("closure_features",closure_summary["feature_count"],"unresolved",closure.unresolved_subjects)
    print("catalog_loaded",catalog.cached_subjects())
    print("q7_transitions",len(q7.transitions),"q7_unmodeled",q7_metrics["unmodeled_source_handler_count"])
    print("q6_transitions",len(q6.transitions),"q6_relays",q6_metrics["event_relay_count"])
    print("q5_transitions",len(q5.transitions),"q5_unmodeled",q5_metrics["unmodeled_source_handler_count"])
    print("q4_transitions",len(q4.transitions),"q4_unmodeled",q4_metrics["unmodeled_source_handler_count"])
    print("q3_transitions",len(q3.transitions),"q3_unmodeled",q3_metrics["unmodeled_source_handler_count"])
    print("next_gap","resolve Light in the Darkness mission and quest prerequisites")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
