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
    assert any(t.metadata.get("priority")==995 for t in raw.transitions),raw.transitions
    complete_handlers=[t for t in raw.transitions if any(e.effect=="COMPLETE" for e in t.effects)]
    assert complete_handlers,raw.transitions
    assert any(
        t.gate and {"mission_status:LOUVERANCE","mission_status:TENZEN","mission_status:ULMIA"} <= {c.subject for c in t.gate.conditions}
        for t in complete_handlers
    ),complete_handlers
    gaps={}
    print("Three Paths real-source stress: PASS")
    print("raw_transitions",len(raw.transitions),"chained_transitions",len(chained.transitions),"channels",len(raw.channels))
    print("exposed_gaps",",".join(gaps) or "none_in_current_probe")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
