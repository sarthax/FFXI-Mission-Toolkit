#!/usr/bin/env python3
"""Regression for conservative Capture Timeline interaction-candidate reconstruction."""
from pathlib import Path

from workbench.runtime.interaction_reconstruction import reconstruct_interaction_candidates


def main():
    rows = [
        {"zone_db":"Test_Zone","seq":1,"direction":"Incoming","opcode":"0x017",
         "opcode_name":"NPC Chat","entity_id":100,"entity_name":"Fixture NPC",
         "event_hex":None,"option":None,"message_id":50,"dialog_text":"Hello."},
        {"zone_db":"Test_Zone","seq":2,"direction":"Incoming","opcode":"0x034",
         "opcode_name":"CS Event + Params","entity_id":100,"entity_name":"Fixture NPC",
         "event_hex":"0x0010","option":None,"message_id":None},
        {"zone_db":"Test_Zone","seq":3,"direction":"Outgoing","opcode":"0x05B",
         "opcode_name":"Event Option","entity_id":None,"entity_name":None,
         "event_hex":None,"option":1,"message_id":None},
        # A different explicit CSID is a new candidate even for the same entity.
        {"zone_db":"Test_Zone","seq":4,"direction":"Incoming","opcode":"0x032",
         "opcode_name":"CS Event","entity_id":100,"entity_name":"Fixture NPC",
         "event_hex":"0x0011","option":None,"message_id":None},
        # A large sequence gap cannot be silently bridged.
        {"zone_db":"Test_Zone","seq":10,"direction":"Incoming","opcode":"0x017",
         "opcode_name":"NPC Chat","entity_id":100,"entity_name":"Fixture NPC",
         "event_hex":None,"option":None,"message_id":51,"dialog_text":"Later."},
        # Zone sequence spaces are independent.
        {"zone_db":"Other_Zone","seq":1,"direction":"Incoming","opcode":"0x017",
         "opcode_name":"NPC Chat","entity_id":200,"entity_name":"Other NPC",
         "event_hex":None,"option":None,"message_id":60,"dialog_text":"Other."},
    ]
    groups = reconstruct_interaction_candidates(rows)
    assert len(groups) == 4, groups

    first = groups[0]
    assert (first["start_seq"], first["end_seq"], first["row_count"]) == (1,3,3), first
    assert first["entity_id"] == 100 and first["csid"] == "0x0010", first
    assert first["options"] == [1], first
    assert first["messages"][0]["message_id"] == 50, first
    assert first["complete_signal"] is True, first

    assert groups[1]["csid"] == "0x0011" and groups[1]["row_count"] == 1, groups[1]
    assert groups[1]["complete_signal"] is False, groups[1]
    assert groups[2]["start_seq"] == 10, groups[2]
    assert groups[3]["zone_db"] == "Other_Zone", groups[3]

    root = Path(__file__).resolve().parents[1]
    template = (root/"gui/templates/capture_timeline.html").read_text(encoding="utf-8")
    gui = (root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert "Interaction candidates" in template
    assert "not</strong> asserted as canonical gameplay transactions" in template
    assert "reconstruct_interaction_candidates(events)" in gui

    print("capture timeline interaction reconstruction self-test: PASS")


if __name__ == "__main__":
    main()
