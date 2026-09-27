#!/usr/bin/env python3
from pathlib import Path
from workbench.plugins.domain.mission_lsb_extract import correlate_lsb_handlers, chain_event_transitions

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/"test_fixtures"/"fixtures"/"lsb_the_road_forks.lua").read_text(encoding="utf-8")

def main():
    raw=correlate_lsb_handlers(SOURCE,feature_id="mission:cop:the_road_forks")
    chained=chain_event_transitions(raw)
    assert not raw.validate(),raw.validate()
    assert not chained.validate(),chained.validate()

    channels={c.channel_id:c for c in raw.channels}
    assert "mission_status:SANDORIA" in channels,channels
    assert "mission_status:WINDURST" in channels,channels
    assert "mission_var:Status" in channels,channels
    assert "local_var:ivyDefeated" in channels,channels
    assert "local_var:Timer" in channels,channels

    event_ids={(t.event.zone,t.event.event_id) for t in chained.transitions if t.event}
    for pair in [("NORTHERN_SAN_DORIA",14),("NORTHERN_SAN_DORIA",51),("WINDURST_WATERS",871),("WINDURST_WALLS",470),("ATTOHWA_CHASM",2),("METALWORKS",847)]:
        assert pair in event_ids,(pair,event_ids)

    logical=[t for t in chained.transitions if t.metadata.get("logical_event_chain")]
    assert any(t.event.event_id==847 and any(e.effect=="COMPLETE" for e in t.effects) for t in logical),logical
    assert any(t.event.event_id==2 and any(e.subject=="key_item:MIMEO_FEATHER" for e in t.effects) for t in logical),logical

    kinds={t.trigger for t in chained.transitions}
    assert "MOB_DEATH" in kinds,kinds

    # Known parser gaps intentionally asserted so later fixes must update this test.
    source_gap={
        "zone_out_handler":"onZoneOut = function" in SOURCE and "ZONE_OUT" not in kinds,
        "local_alias_conditions":"local missionStatus =" in SOURCE,
        "timer_helper_outside_sections":"jewelTimer = function" in SOURCE,
        "entity_spawn_state_guard":":isSpawned()" in SOURCE,
        "message_return":"mission:messageSpecial" in SOURCE or "mission:messageName" in SOURCE,
        "completion_section_check":"SANDORIA) == 14" in SOURCE and "WINDURST) == 14" in SOURCE,
    }
    assert all(source_gap.values()),source_gap
    print("Road Forks real-source stress: PASS")
    print("raw_transitions",len(raw.transitions),"logical_chains",len(logical),"channels",len(raw.channels))
    print("known_gaps",",".join(k for k,v in source_gap.items() if v))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
