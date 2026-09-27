#!/usr/bin/env python3
from pathlib import Path
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions, correlate_lsb_handlers, extract_section_completion_gate,
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
    completion=extract_section_completion_gate(SOURCE)
    # Existing two-channel heuristic is not sufficient for helper-loop convergence.
    gaps={
        "helper_completion_function":"local function isMissionComplete" in SOURCE,
        "dynamic_status_channel_loop":"for pathArg = xi.mission.status.COP.LOUVERANCE" in SOURCE,
        "not_equal_guard":"~=" in SOURCE,
        "position_guard":"player:getXPos() == 220" in SOURCE,
        "pop_from_qm":"npcUtil.popFromQM" in SOURCE,
        "trade_complete":"player:tradeComplete()" in SOURCE,
        "client_transport":"handled by the client" in SOURCE,
        "reward_title":"mission.reward" in SOURCE and "title" in SOURCE,
        "priority":"setPriority" in SOURCE,
    }
    assert all(gaps.values()),gaps
    print("Three Paths real-source stress: PASS")
    print("raw_transitions",len(raw.transitions),"chained_transitions",len(chained.transitions),"channels",len(raw.channels))
    print("exposed_gaps",",".join(gaps))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
