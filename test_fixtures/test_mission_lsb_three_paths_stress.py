#!/usr/bin/env python3
from pathlib import Path
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions, client_transport_effects, correlate_lsb_handlers, extract_dynamic_completion_gate, extract_mission_reward_metadata, extract_section_completion_gate,
)

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"test_fixtures"/"fixtures"/"lsb_three_paths.lua").read_text(encoding="utf-8")

def main():
    raw=correlate_lsb_handlers(SOURCE,feature_id="mission:cop:three_paths")
    chained=chain_event_transitions(raw)
    assert not raw.validate(),raw.validate()
    assert not chained.validate(),chained.validate()
    channels={c.channel_id:c for c in raw.channels}
    for channel in ("mission_status:LOUVERANCE","mission_status:TENZEN","mission_status:ULMIA","mission_var:Option","local_var:cidOption","local_var:hasKilled"):
        assert channel in channels,(channel,channels)

    events={(t.event.zone,t.event.event_id) for t in chained.transitions if t.event}
    expected={
        ("TAVNAZIAN_SAFEHOLD",118),("MINE_SHAFT_2716",3),("MINE_SHAFT_2716",32001),
        ("LA_THEINE_PLATEAU",203),("LOWER_DELKFUTTS_TOWER",25),
        ("BONEYARD_GULLY",32001),("BEARCLAW_PINNACLE",32001),
        ("METALWORKS",853),("METALWORKS",854),("METALWORKS",855),
    }
    assert expected <= events,expected-events
    assert "TRADE" in {t.trigger for t in chained.transitions}
    assert "MOB_DEATH" in {t.trigger for t in chained.transitions}
    completion=extract_dynamic_completion_gate(SOURCE)
    assert completion and completion.logic=="ALL",completion
    assert {c.subject for c in completion.conditions}=={"mission_status:LOUVERANCE","mission_status:TENZEN","mission_status:ULMIA"},completion
    assert all(c.value==14 for c in completion.conditions),completion
    assert any(c.operator=="NE" for t in raw.transitions if t.gate for c in t.gate.conditions),raw.transitions
    assert any(c.operator=="AT_POSITION" for t in raw.transitions if t.gate for c in t.gate.conditions),raw.transitions
    assert any(e.effect=="SPAWN_ENTITY" and "DISASTER_IDOL" in e.subject for t in raw.transitions for e in t.effects),raw.transitions
    assert any(e.effect=="COMPLETE_TRADE" for t in raw.transitions for e in t.effects),raw.transitions
    reward=extract_mission_reward_metadata(SOURCE)
    assert reward["title"]=="TREADER_OF_AN_ICY_PAST",reward
    transports=client_transport_effects(SOURCE)
    assert transports and transports[0].effect=="CLIENT_TRANSPORT",transports
    transport_event=next(t for t in raw.transitions if t.event and t.event.zone=="MINE_SHAFT_2716" and t.event.event_id==3 and t.trigger=="EVENT_FINISH")
    assert any(e.effect=="CLIENT_TRANSPORT" for e in transport_event.effects),transport_event
    assert transport_event.metadata.get("client_transport") is True,transport_event.metadata
    no_transport=next(t for t in raw.transitions if t.event and t.event.zone=="MINE_SHAFT_2716" and t.event.event_id==32001 and t.trigger=="EVENT_FINISH")
    assert not any(e.effect=="CLIENT_TRANSPORT" for e in no_transport.effects),no_transport
    assert any(t.metadata.get("priority")==995 for t in raw.transitions),raw.transitions
    complete_handlers=[t for t in raw.transitions if any(e.effect=="COMPLETE" for e in t.effects)]
    assert len(complete_handlers)>=3,complete_handlers
    convergence_subjects={"mission_status:LOUVERANCE","mission_status:TENZEN","mission_status:ULMIA"}
    terminal_events={853,854,855}
    terminal_complete=[
        t for t in complete_handlers
        if t.event and t.event.event_id in terminal_events
    ]
    assert {t.event.event_id for t in terminal_complete}==terminal_events,terminal_complete
    for transition in terminal_complete:
        assert transition.post_effect_gate is not None,transition
        assert {c.subject for c in transition.post_effect_gate.conditions}==convergence_subjects,transition
        assert all(c.value==14 for c in transition.post_effect_gate.conditions),transition
        pre_subjects={c.subject for c in transition.gate.conditions} if transition.gate else set()
        assert not convergence_subjects <= pre_subjects,transition
        written={
            e.subject for e in transition.effects
            if e.effect=="SET_CHANNEL" and e.value==14
        }
        assert written & convergence_subjects,transition
        assert transition.metadata.get("post_effect_gate_basis"),transition.metadata

    chained_terminal=[
        t for t in chained.transitions
        if t.metadata.get("logical_event_chain")
        and t.event and t.event.event_id in terminal_events
        and any(e.effect=="COMPLETE" for e in t.effects)
    ]
    assert {t.event.event_id for t in chained_terminal}==terminal_events,chained_terminal
    assert all(t.post_effect_gate is not None for t in chained_terminal),chained_terminal
    gaps={}
    print("Three Paths real-source stress: PASS")
    print("raw_transitions",len(raw.transitions),"chained_transitions",len(chained.transitions),"channels",len(raw.channels))
    print("exposed_gaps",",".join(gaps) or "none_in_current_probe")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
