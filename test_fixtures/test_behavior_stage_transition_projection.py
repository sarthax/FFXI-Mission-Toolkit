#!/usr/bin/env python3
"""Regression for fail-closed Behavior Inspector stage lifecycle projection."""
from __future__ import annotations

from workbench.devtools.behavior.stage_transition_projection import apply_stage_transition_evidence


SCRIPT = r'''
local entity = {}

entity.onTrigger = function(player, npc)
    local missionStage = player:getCharVar('MissionStage')
    if missionStage == 0 then
        player:startEvent(101)
    elseif missionStage == 1 then
        player:startEvent(102)
    end
end

entity.onEventFinish = function(player, csid, option, npc)
    if csid == 101 then
        player:setCharVar('MissionStage', 1)
    elseif csid == 102 then
        if option == 1 then
            player:setCharVar('MissionStage', 99)
        end
        player:setCharVar('MissionStage', 2)
    elseif csid == 999 then
        player:setCharVar('MissionStage', 100)
    end
end

return entity
'''


def main():
    projection = {
        "source_branch_evidence": [
            {
                "hook": "onTrigger",
                "state_id": "state:PLAYER_CHAR:player:MissionStage",
                "state_name": "MissionStage",
                "literal": "0",
                "event_id": 101,
                "guard_line": 6,
                "event_line": 7,
            },
            {
                "hook": "onTrigger",
                "state_id": "state:PLAYER_CHAR:player:MissionStage",
                "state_name": "MissionStage",
                "literal": "1",
                "event_id": 102,
                "guard_line": 8,
                "event_line": 9,
            },
        ],
        "event_handoffs": [
            {
                "event_id": 101,
                "ordering": "UNPROVEN",
                "handler_branches": [{"branch_id": "finish-101", "trigger_label": "A cutscene or event finishes"}],
            },
            {
                "event_id": 102,
                "ordering": "UNPROVEN",
                "handler_branches": [{"branch_id": "finish-102", "trigger_label": "A cutscene or event finishes"}],
            },
        ],
        "summary": {},
        "safety": {},
    }

    result = apply_stage_transition_evidence(projection, SCRIPT)
    rows = {str(row["event_id"]): row for row in result["stage_lifecycles"]}
    assert set(rows) == {"101", "102"}, rows

    row101 = rows["101"]
    assert row101["state_id"] == "state:PLAYER_CHAR:player:MissionStage", row101
    assert row101["from_value"] == "0", row101
    assert row101["ordering"] == "UNPROVEN", row101
    assert {str(write["value"]) for write in row101["handler_writes"]} == {"1"}, row101

    row102 = rows["102"]
    values = {str(write["value"]) for write in row102["handler_writes"]}
    assert values == {"2"}, row102
    assert "99" not in values, row102
    assert all(write["state_id"] == row102["state_id"] for write in row102["handler_writes"]), row102

    assert result["summary"]["stage_lifecycle_count"] == 2, result["summary"]
    assert result["safety"]["stage_lifecycle_cross_hook_ordering"] == "UNPROVEN", result["safety"]
    assert "direct same-state write" in result["safety"]["stage_lifecycle_scope"], result["safety"]

    print("Behavior Inspector stage transition projection regression: PASS")


if __name__ == "__main__":
    main()
