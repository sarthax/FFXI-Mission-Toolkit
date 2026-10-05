"""Parse source-derived Nyzul Isle Investigation floor-selection semantics for modern LSB."""
from __future__ import annotations

import re
from typing import Any


def _required(pattern: str, text: str, label: str, flags: int = 0) -> re.Match[str]:
    match = re.search(pattern, text, flags)
    if not match:
        raise ValueError(f"modern LSB Nyzul {label} could not be mapped deterministically")
    return match


def parse_instance_selection(text: str) -> dict[str, Any]:
    """Return the deterministic selection contract encoded by nyzul_isle_investigation.lua.

    This deliberately recognizes only the current simple literal constructs. If LSB
    changes them into a different expression, the adapter fails closed instead of
    silently retaining stale DSP/Topaz assumptions.
    """
    layout = _required(
        r"Nyzul_Isle_FloorLayout'\s*,\s*math\.randomInt\(\s*(\d+)\s*,\s*\(#xi\.nyzul\.FloorLayout\s*-\s*(\d+)\)\s*\)",
        text,
        "non-boss layout selection",
    )
    boss = _required(
        r"currentFloor\s*%\s*(\d+)\s*==\s*0[\s\S]*?setStage\(xi\.nyzul\.objective\.([A-Z0-9_]+)\)[\s\S]*?Nyzul_Isle_FloorLayout'\s*,\s*(\d+)\)",
        text,
        "boss-floor selection",
    )
    free = _required(
        r"math\.randomInt\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*==\s*(\d+)\s*and\s*instance:getLocalVar\('freeFloor'\)\s*==\s*(\d+)[\s\S]*?setStage\(xi\.nyzul\.objective\.([A-Z0-9_]+)\)[\s\S]*?setLocalVar\('freeFloor'\s*,\s*(\d+)\)",
        text,
        "free-floor selection",
    )
    objectives = _required(
        r"for\s+i\s*=\s*xi\.nyzul\.objective\.([A-Z0-9_]+)\s*,\s*xi\.nyzul\.objective\.([A-Z0-9_]+)\s*do[\s\S]*?table\.insert\(objective\s*,\s*i\)",
        text,
        "normal objective range",
    )
    repeat_suppression = bool(
        re.search(
            r"instance:getStage\(\)\s*~=\s*0\s*and\s*instance:getStage\(\)\s*~=\s*6[\s\S]*?table\.remove\(objective\s*,\s*instance:getStage\(\)\)",
            text,
        )
    )
    if not repeat_suppression:
        raise ValueError("modern LSB Nyzul immediate-repeat suppression could not be mapped deterministically")

    gear = _required(
        r"math\.randomInt\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*<=\s*(\d+)[\s\S]*?gearObjective'\s*,\s*math\.randomInt\(xi\.nyzul\.gearObjective\.([A-Z0-9_]+)\s*,\s*xi\.nyzul\.gearObjective\.([A-Z0-9_]+)\)\)",
        text,
        "gear-objective selection",
    )
    menu = _required(
        r"menuChoice'\s*,\s*math\.randomInt\(\s*(\d+)\s*,\s*(\d+)\s*\)\)",
        text,
        "Rune menu selection",
    )

    layout_first = int(layout.group(1))
    layout_subtract = int(layout.group(2))
    free_first, free_last, free_hit = map(int, free.group(1, 2, 3))
    gear_first, gear_last, gear_hits = map(int, gear.group(1, 2, 3))

    if layout_first < 0 or layout_subtract < 0 or free_last < free_first or gear_last < gear_first:
        raise ValueError("modern LSB Nyzul selection contract contains invalid literal ranges")
    if not (free_first <= free_hit <= free_last) or not (0 <= gear_hits <= gear_last - gear_first + 1):
        raise ValueError("modern LSB Nyzul selection probabilities contain invalid literal ranges")

    return {
        "non_boss_layout": {
            "first": layout_first,
            "last_expression": f"#xi.nyzul.FloorLayout - {layout_subtract}",
            "floor_layout_count_subtract": layout_subtract,
        },
        "boss_floor": {
            "interval": int(boss.group(1)),
            "objective_symbol": boss.group(2),
            "layout": int(boss.group(3)),
        },
        "free_floor": {
            "roll": [free_first, free_last],
            "hit": free_hit,
            "probability": 1 / (free_last - free_first + 1),
            "guard_local_var": "freeFloor",
            "guard_value": int(free.group(4)),
            "objective_symbol": free.group(5),
            "sets_guard_to": int(free.group(6)),
            "once_per_run": True,
        },
        "normal_objectives": {
            "first_symbol": objectives.group(1),
            "last_symbol": objectives.group(2),
            "suppress_immediate_repeat": True,
        },
        "gear_objective": {
            "roll": [gear_first, gear_last],
            "success_values": gear_hits,
            "probability": gear_hits / (gear_last - gear_first + 1),
            "first_symbol": gear.group(4),
            "last_symbol": gear.group(5),
        },
        "rune_menu_choice": [int(menu.group(1)), int(menu.group(2))],
    }
