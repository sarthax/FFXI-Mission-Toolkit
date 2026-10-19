"""Fail-closed preflight for the DSP !garden command's dual-container slot behavior.

The input is the complete, untruncated chat response to '!garden info'.
This module never sends commands; callers must separately authorize them.
"""
from __future__ import annotations

import re

_POT = re.compile(r"^\[c(?P<container>\d+) s(?P<slot>\d+)\] pot (?P<item>\d+): plant=(?P<plant>\d+) stage=(?P<stage>\d+)\(", re.M)
_MUTATIONS = frozenset({"plant", "stage", "grow", "mature", "wilt", "ready", "crystal1", "crystal2", "strength", "dry", "examined", "clean"})


def parse_garden_info(output: str) -> list[dict]:
    if not isinstance(output, str) or len(output) > 65536:
        raise ValueError("garden info transcript missing or too large")
    matches = [dict((k, int(v)) for k, v in m.groupdict().items()) for m in _POT.finditer(output)]
    identities = [(p["container"], p["slot"]) for p in matches]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate pot in garden info transcript")
    return matches


def preflight_garden_mutation(info: str, action: str, value: int, slot: int,
                              *, expected_container: int, expected_item: int) -> dict:
    """Only approve a single pot whose container, slot and item were verified.

    'allow' means the preflight *matches the observed snapshot*, never
    execution authorization or proof that the game/server state is unchanged.
    """
    if action not in _MUTATIONS:
        return {"allow": False, "reason": "unknown or non-mutation action"}
    if type(slot) is not int or not 0 <= slot <= 255:
        return {"allow": False, "reason": "explicit numeric slot required"}
    if type(value) is not int:
        return {"allow": False, "reason": "value must be an integer"}
    if action == "grow" and not 1 <= value <= 11:
        return {"allow": False, "reason": "grow count must be 1..11"}
    if action == "stage" and not 1 <= value <= 11:
        return {"allow": False, "reason": "stage must be 1..11"}
    if action == "plant" and not 1 <= value <= 8:
        return {"allow": False, "reason": "seed type must be 1..8"}
    if action in {"crystal1", "crystal2"} and not 0 <= value <= 8:
        return {"allow": False, "reason": "crystal element must be 0..8"}
    if action == "strength" and not 0 <= value <= 31:
        return {"allow": False, "reason": "strength must be 0..31"}
    if action in {"dry", "examined"} and value not in {0, 1}:
        return {"allow": False, "reason": "flag must be 0 or 1"}
    try:
        pots = parse_garden_info(info)
    except ValueError as exc:
        return {"allow": False, "reason": str(exc)}
    if not pots or "no flowerpot found" in info.lower():
        return {"allow": False, "reason": "no trustworthy flowerpot inventory"}
    matching = [pot for pot in pots if pot["slot"] == slot]
    if len(matching) != 1:
        return {"allow": False, "reason": "slot collides between Mog Safe and Safe 2 or is absent"}
    pot = matching[0]
    if (pot["container"], pot["item"]) != (expected_container, expected_item):
        return {"allow": False, "reason": "pot identity does not match expected container and item"}
    return {"allow": True, "reason": "unique pot observed; operator authorization still required",
            "pot": pot, "preview": f"!garden {action} {value} {slot}"}
