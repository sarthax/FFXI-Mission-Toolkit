from __future__ import annotations

import pytest

from workbench.devtools.domains.nyzul_lsb_instance import parse_instance_selection


INSTANCE = r"""
local function pickSetPoint(instance)
    local currentFloor = instance:getLocalVar('Nyzul_Current_Floor')
    instance:setLocalVar('Nyzul_Isle_FloorLayout', math.randomInt(1, (#xi.nyzul.FloorLayout - 1)))
    instance:setLocalVar('gearObjective', 0)

    if currentFloor % 20 == 0 then
        instance:setStage(xi.nyzul.objective.ELIMINATE_ENEMY_LEADER)
        instance:setLocalVar('Nyzul_Isle_FloorLayout', 0)
    elseif math.randomInt(1, 30) == 1 and instance:getLocalVar('freeFloor') == 0 then
        instance:setStage(xi.nyzul.objective.FREE_FLOOR)
        instance:setLocalVar('freeFloor', 1)
    else
        local objective = {}
        for i = xi.nyzul.objective.ELIMINATE_ENEMY_LEADER, xi.nyzul.objective.ELIMINATE_ALL_ENEMIES do
            table.insert(objective, i)
        end
        if instance:getStage() ~= 0 and instance:getStage() ~= 6 then
            table.remove(objective, instance:getStage())
        end
        instance:setStage(utils.randomEntry(objective))
        if math.randomInt(1, 30) <= 5 then
            instance:setLocalVar('gearObjective', math.randomInt(xi.nyzul.gearObjective.AVOID_AGRO, xi.nyzul.gearObjective.DO_NOT_DESTROY))
        end
    end
    instance:setLocalVar('menuChoice', math.randomInt(1, 20))
end
"""


def test_current_lsb_instance_selection_contract():
    data = parse_instance_selection(INSTANCE)
    assert data["non_boss_layout"] == {
        "first": 1,
        "last_expression": "#xi.nyzul.FloorLayout - 1",
        "floor_layout_count_subtract": 1,
    }
    assert data["boss_floor"] == {
        "interval": 20,
        "objective_symbol": "ELIMINATE_ENEMY_LEADER",
        "layout": 0,
    }
    assert data["free_floor"]["roll"] == [1, 30]
    assert data["free_floor"]["hit"] == 1
    assert data["free_floor"]["probability"] == pytest.approx(1 / 30)
    assert data["free_floor"]["once_per_run"] is True
    assert data["free_floor"]["guard_value"] == 0
    assert data["free_floor"]["sets_guard_to"] == 1
    assert data["normal_objectives"] == {
        "first_symbol": "ELIMINATE_ENEMY_LEADER",
        "last_symbol": "ELIMINATE_ALL_ENEMIES",
        "suppress_immediate_repeat": True,
    }
    assert data["gear_objective"]["roll"] == [1, 30]
    assert data["gear_objective"]["success_values"] == 5
    assert data["gear_objective"]["probability"] == pytest.approx(1 / 6)
    assert data["gear_objective"]["first_symbol"] == "AVOID_AGRO"
    assert data["gear_objective"]["last_symbol"] == "DO_NOT_DESTROY"
    assert data["rune_menu_choice"] == [1, 20]


def test_changed_instance_selection_construct_fails_closed():
    broken = INSTANCE.replace("math.randomInt(1, 30) == 1", "utils.chance(1, 30)")
    with pytest.raises(ValueError, match="free-floor selection"):
        parse_instance_selection(broken)


def test_missing_repeat_suppression_fails_closed():
    broken = INSTANCE.replace("table.remove(objective, instance:getStage())", "-- removed repeat guard")
    with pytest.raises(ValueError, match="immediate-repeat suppression"):
        parse_instance_selection(broken)
