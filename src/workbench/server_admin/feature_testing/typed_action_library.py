"""Versioned typed action / expectation / readback library for scenario authoring (#1409).

This is the machine-readable registry that the merged phase-1 crosswalk
(``docs/workbench/SCENARIO_SUITE_TYPED_LIBRARY_1409.md``) and phase-2 guard
(``tools/scenario_typed_library_contract_1409.py``) describe in prose and hard-coded checks. Each
template has a human label, structured parameter specs, the native Headless ``do`` / ``expect`` keys,
source references, a support tier and the limits of what it establishes.

It is DATA plus validation. It never dispatches an action, calls a server or a GM command, emits a
packet, reads a database or promotes a verdict. A built step is a *draft candidate*: its oracle stays
``UNAPPROVED`` and its verdict ``UNKNOWN`` until something independent establishes otherwise. Packet
opcodes are never used to infer behaviour, and a Headless action, a state readback and an oracle remain
three different things.

Tiers: ``HEADLESS_SCHEMA_ONLY`` means the native key and its parameter/expectation shape were verified
against the pinned XIHeadless schemas; whether the runner dispatches it, and what it proves, is not
established here. ``TOOLKIT_READBACK_ONLY`` means a documented, authenticated, SELECT-only Toolkit
supervisor route exists for the readback; it is not a Headless step and has no native pair.
"""
from __future__ import annotations

import copy
import math
import struct

SCHEMA = "toolkit-typed-action-library/1"
LIBRARY_VERSION = 1
# XIHeadless commit whose native schemas the parameter and expectation shapes were checked against
# (the phase-2 guard's pin). The crosswalk's own per-row references are carried verbatim per template.
NATIVE_SCHEMA_HEAD = "159a5b9d4b4e43397bd509a816a7241a97511319"
_UINT32_MAX = 4294967295
_MS_MAX = 3600000
_UINT53_MAX = 2 ** 53


# --- parameter checks ----------------------------------------------------------------------------

def _is_int(value: object) -> bool:
    return type(value) is int  # bool is rejected on purpose


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def _finite_float32(value: object) -> bool:
    """Mirror the native single-precision read: finite as a double AND finite after narrowing."""
    if not _finite(value):
        return False
    try:
        return math.isfinite(struct.unpack("!f", struct.pack("!f", value))[0])
    except (OverflowError, ValueError, struct.error):
        return False


def _coords_ok(value: object) -> bool:
    return isinstance(value, list) and len(value) in (2, 3) and all(_finite_float32(n) for n in value)


def _check_walk_target(value: object, spec: dict) -> str | None:
    if isinstance(value, list):
        return None if _coords_ok(value) else "coordinates must be [x, z] or [x, y, z] of finite single-precision numbers"
    if isinstance(value, dict):
        if not set(value) <= {"coords", "timeout_ms", "stall_ms"} or "coords" not in value:
            return "object form allows only coords (required), timeout_ms and stall_ms"
        if not _coords_ok(value["coords"]):
            return "coords must be [x, z] or [x, y, z] of finite single-precision numbers"
        if not all(_is_int(v) and 1 <= v <= _MS_MAX for k, v in value.items() if k != "coords"):
            return f"timeout_ms and stall_ms must be integers 1..{_MS_MAX}"
        return None
    return "must be a coordinate list or an object with coords"


def _range_check(low: int, high: int):
    def check(value: object, spec: dict) -> str | None:
        return None if _is_int(value) and low <= value <= high else f"must be an integer {low}..{high}"
    return check


_CHECKS = {
    "uint32": lambda v, s: None if _is_int(v) and 0 <= v <= _UINT32_MAX else f"must be an integer 0..{_UINT32_MAX}",
    "uint53": lambda v, s: None if _is_int(v) and 0 <= v <= _UINT53_MAX else f"must be an integer 0..{_UINT53_MAX}",
    "int_range": lambda v, s: _range_check(s["min"], s["max"])(v, s),
    "bool": lambda v, s: None if type(v) is bool else "must be true or false",
    "finite_number": lambda v, s: None if _finite(v) else "must be a finite number",
    "walk_target": _check_walk_target,
}


class TypedStepError(ValueError):
    """A step could not be built. ``part`` says what was wrong: ``template``, ``action`` or ``expectation``."""

    def __init__(self, message: str, part: str):
        super().__init__(message)
        self.part = part


def check_param(spec: dict, value: object) -> str | None:
    """Return None if ``value`` satisfies the parameter spec, else a short reason."""
    return _CHECKS[spec["type"]](value, spec)


# --- the registry --------------------------------------------------------------------------------

_HEADLESS = "HEADLESS_SCHEMA_ONLY"
_READBACK = "TOOLKIT_READBACK_ONLY"
_CROSSWALK = ("xiheadless-main@e5e80350711d5d2ec814c893a17c63baf3ef98a9:Brains/ScenarioActionSchema.cs"
              " + Brains/ScenarioExpectationSchema.cs")
_R7 = ("toolkit-main@7bb970af4a21b5ffd4d31d4646528e33ad88b3a8:"
       "docs/workbench/R7_OBSERVATION_CLOSEOUT_AND_NEXT_READBACK_2026-10-22.md")


def _action(tid, label, key, pname, ptype, expect_key, etype, limitation, picker=None, expect_picker=None, **extra):
    """``picker`` / ``expect_picker`` name a catalog kind ("npc", "zone") the editor may offer as a search
    helper for that parameter. It is a UI hint only: it never changes what values are valid."""
    action_param = {"name": pname, "type": ptype, **extra}
    expect_param = {"name": expect_key, "type": etype}
    if picker:
        action_param["picker"] = picker
    if expect_picker:
        expect_param["picker"] = expect_picker
    return {"id": tid, "kind": "action_expectation", "label": label, "support_tier": _HEADLESS,
            "action": {"native_key": key, "param": action_param},
            "expectation": {"native_key": expect_key, "param": expect_param},
            "source_ref": _CROSSWALK, "limitations": limitation}


def _readback(tid, label, route, params, limitation):
    return {"id": tid, "kind": "observation", "label": label, "support_tier": _READBACK,
            "action": None, "expectation": None,
            "readback": {"method": "GET", "route": route, "parameters": params},
            "source_ref": _R7, "limitations": limitation}


_TEMPLATES = (
    _action("navigate_near", "navigate near", "walk_to", "coordinates", "walk_target", "x_near", "finite_number",
            "Headless scenario state; no independent position readback in this slice"),
    _action("talk_to_npc", "talk to npc", "talk_npc", "npc_id", "uint32", "event_active", "bool",
            "NPC ID is unverified for a particular zone/client", picker="npc"),
    _action("inspect_npc", "inspect npc", "examine_npc", "npc_id", "uint32", "event_id", "uint53",
            "Event ID requires authenticated observed event evidence", picker="npc"),
    _action("advance_event", "advance event", "event_update", "event_value", "uint32", "event_param0", "uint53",
            "Event param must be captured as observation, not assumed from action"),
    _action("finish_event", "finish event", "event_finish", "event_value", "uint32", "event_active", "bool",
            "Completion request cannot establish event completion"),
    _action("wait_for_state", "wait for state", "wait_ms", "duration_ms", "int_range", "zone", "uint53",
            "Time elapsed is not evidence of a zone transition", expect_picker="zone", min=0, max=_MS_MAX),
    _action("recover_hp", "recover hp", "rest_hp", "hp_percent", "int_range", "hpp", "uint53",
            "HP state requires observed snapshot, not dispatch success", min=1, max=100),
    _action("invite_party", "invite party", "invite", "entity_id", "uint32", "party_members_gt", "uint53",
            "Party membership requires independent observed party roster"),
    _action("accept_party_invite", "accept party invite", "accept_invite", "accepted", "bool", "party_members_gt",
            "uint53", "Invitation and roster outcomes not proven"),
    _action("engage_target", "engage target", "engage", "target_id", "uint32", "entities_gt", "uint53",
            "Entity count is not combat success; oracle mapping unapproved"),
    _readback("read_inventory", "read inventory", "/api/supervisor/test-character-inventory-v2",
              ["charid", "location", "cursor", "limit"],
              "Authorized SELECT-only inventory response can be INCOMPLETE; not atomic"),
    _readback("read_progression", "read progression", "/api/supervisor/test-character-progression",
              ["charid", "names", "include_keyitems"],
              "No jobs/quest/currencies; persisted value != client-observed result"),
)


def _constraint(param: dict) -> str:
    kind = param["type"]
    if kind == "int_range":
        return f"integer {param['min']}..{param['max']}"
    return {"uint32": f"integer 0..{_UINT32_MAX}", "uint53": f"integer 0..{_UINT53_MAX}", "bool": "true or false",
            "finite_number": "finite number",
            "walk_target": ("finite single-precision [x, z] or [x, y, z], or {coords, timeout_ms?, stall_ms?} "
                            f"with the millisecond fields integers 1..{_MS_MAX}")}[kind]


def _public(template: dict) -> dict:
    out = copy.deepcopy(template)
    for part in ("action", "expectation"):
        if out[part]:
            out[part]["param"]["constraint"] = _constraint(out[part]["param"])
    out.update({"execution_enabled": False, "oracle_status": "UNAPPROVED", "verdict": "UNKNOWN"})
    return out


def list_templates() -> list[dict]:
    """Every template, in a stable order, as independent copies."""
    return [_public(t) for t in _TEMPLATES]


def get_template(template_id: str) -> dict:
    for template in _TEMPLATES:
        if template["id"] == template_id:
            return _public(template)
    raise TypedStepError(f"unknown template: {template_id!r}", "template")


def export_registry() -> dict:
    """The full versioned registry as plain JSON-serializable data (deterministic)."""
    return {"schema": SCHEMA, "library_version": LIBRARY_VERSION, "native_schema_head": NATIVE_SCHEMA_HEAD,
            "headless_wire_contract_approved": False, "templates": list_templates()}


def build_step(template_id: str, action_value: object, expectation_value: object) -> dict:
    """Build a native ``do`` / ``expect`` draft step from a template after validating both values.

    Raises ``ValueError`` naming the template and parameter. The result is a draft candidate: it is not
    sent anywhere, its oracle is UNAPPROVED and its verdict UNKNOWN.
    """
    template = get_template(template_id)
    if template["kind"] != "action_expectation":
        raise TypedStepError(f"{template_id} is a Toolkit readback ({template['readback']['route']}), "
                             "not a Headless step; it has no native action or expectation", "template")
    for part, value in (("action", action_value), ("expectation", expectation_value)):
        param = template[part]["param"]
        problem = check_param(param, value)
        if problem:
            raise TypedStepError(f"{template_id}: {part} parameter {param['name']!r} {problem}", part)
    return {"template_id": template_id,
            "do": {template["action"]["native_key"]: copy.deepcopy(action_value)},
            "expect": {template["expectation"]["native_key"]: copy.deepcopy(expectation_value)},
            "support_tier": template["support_tier"], "native_schema_head": NATIVE_SCHEMA_HEAD,
            "oracle_status": "UNAPPROVED", "verdict": "UNKNOWN", "execution_enabled": False}
