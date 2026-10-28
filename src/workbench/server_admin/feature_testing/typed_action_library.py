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
import re
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


def _derive_parts() -> tuple[dict[str, dict], dict[str, dict]]:
    """Independent action and check definitions, derived from the reviewed templates.

    Every action and every check was reviewed on its own (the guard validates them separately); the templates
    only fix which ones were reviewed *as pairs*. A check used by two templates must carry one identical spec.
    """
    actions: dict[str, dict] = {}
    checks: dict[str, dict] = {}
    for template in _TEMPLATES:
        if template["kind"] != "action_expectation":
            continue
        action, check = template["action"], template["expectation"]
        if action["native_key"] in actions:
            raise RuntimeError("an action must belong to exactly one reviewed template")
        actions[action["native_key"]] = {
            "native_key": action["native_key"], "label": template["label"], "param": action["param"],
            "limitations": template["limitations"], "source_ref": template["source_ref"]}
        known = checks.get(check["native_key"])
        if known is not None and known["param"] != check["param"]:
            raise RuntimeError("a check shared by two templates must have one parameter spec")
        checks.setdefault(check["native_key"], {
            "native_key": check["native_key"], "label": check["native_key"].replace("_", " "),
            "param": check["param"], "source_ref": template["source_ref"]})
    return actions, checks


_ACTION_DEFS, _CHECK_DEFS = _derive_parts()


# What the local verification observed when each native key was fed to XiHeadless' own loaders (an offline harness
# around ScenarioFileValidation.CheckStructure and ScenarioTaskTools.Start; nothing was executed against a client).
# This is an observation about acceptance, not about behaviour: a key the loader accepts may still not be dispatched.
_PATHS_SOURCE = ("xiheadless-main@e5e80350711d5d2ec814c893a17c63baf3ef98a9:Brains/ScenarioFileValidation.cs"
                 " + ScenarioTaskTools.Start, as recorded in sarthax/FFXI-Mission-Toolkit#1456")
_MCP_RESOURCE = "scenario_resource_actions_not_yet_supported"
_MCP_LEGACY = "scenario_legacy_actions_not_supported"
_MCP_EXPECT = "scenario_expectations_not_yet_supported"
_MCP_REJECTS = {"walk_to": _MCP_RESOURCE, "talk_npc": _MCP_RESOURCE, "examine_npc": _MCP_RESOURCE,
                "event_update": _MCP_RESOURCE, "event_finish": _MCP_RESOURCE, "rest_hp": _MCP_RESOURCE,
                "engage": _MCP_RESOURCE, "invite": _MCP_LEGACY, "accept_invite": _MCP_LEGACY,
                **{key: _MCP_EXPECT for key in ("x_near", "event_active", "event_id", "event_param0", "zone", "hpp",
                                                "party_members_gt", "entities_gt")}}


def _observed_paths(native_key: str) -> dict:
    reason = _MCP_REJECTS.get(native_key)
    mcp = {"status": "REJECTS", "reason": reason} if reason else {"status": "ACCEPTS"}
    return {"xiheadless_loader": {"status": "ACCEPTS",
                                  "note": "an action-only step is accepted only when exported with an empty expect"},
            "mcp_task_start": mcp, "source": _PATHS_SOURCE, "execution_tested": False}


def _public_part(part: dict) -> dict:
    out = copy.deepcopy(part)
    out["param"]["constraint"] = _constraint(out["param"])
    out["observed_paths"] = _observed_paths(out["native_key"])
    out.update({"support_tier": _HEADLESS, "execution_enabled": False})
    return out


def list_actions() -> list[dict]:
    """Every reviewed native action (10), as independent copies, in a stable order."""
    return [_public_part(a) for a in _ACTION_DEFS.values()]


def list_checks() -> list[dict]:
    """Every reviewed native check (8), as independent copies, in a stable order."""
    return [_public_part(c) for c in _CHECK_DEFS.values()]


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
            "headless_wire_contract_approved": False, "templates": list_templates(),
            "actions": list_actions(), "checks": list_checks()}


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


# --- reviewing native scenario JSON (e.g. written by an agent or copied from a scenario file) -------------------

MAX_IMPORT_STEPS = 100
MAX_NATIVE_STEPS = 50  # steps stored with one draft
_MAX_NAME = 100
_MAX_NOTE = 300
_NATIVE_FIELDS = {"name", "do", "expect"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _template_by_pair() -> dict[tuple[str, str], str]:
    return {(t["action"]["native_key"], t["expectation"]["native_key"]): t["id"]
            for t in _TEMPLATES if t["kind"] == "action_expectation"}


# How XiHeadless e5e8035 treats several keys in one step (Brains/ScenarioBrain.cs, ScenarioExpectationSchema.cs):
# every key in `expect` must hold (AND, order irrelevant), and the runner executes the keys of `do` in a FIXED order
# written into its code, not in file order: walk_to, talk_npc, invite, accept_invite, wait_ms, then the "control"
# group (engage, examine_npc, event_update, event_finish, rest_hp). The control group is dispatched by iterating a
# dictionary built from the file, so the order inside it is the dictionary's enumeration order. That is not a stated
# contract, so a step with two control actions is refused (open question, see the docs) and every multi-action step
# must be written in the runner's order so that file order and execution order agree.
RUNNER_ACTION_ORDER = ("walk_to", "talk_npc", "invite", "accept_invite", "wait_ms")
RUNNER_CONTROL_GROUP = ("engage", "examine_npc", "event_update", "event_finish", "rest_hp")


def _action_order_problem(keys: list[str]) -> str | None:
    """Why a multi-action ``do`` cannot be accepted, or None. Single actions are always fine."""
    if len(keys) < 2:
        return None
    controls = [k for k in keys if k in RUNNER_CONTROL_GROUP]
    if len(controls) > 1:
        return ("actions " + ", ".join(controls) + " belong to one runner group whose execution order is the "
                "enumeration order of a dictionary built from the file, which is not a stated contract; "
                "at most one of them is supported per step")
    runner_order = [k for k in (*RUNNER_ACTION_ORDER, *RUNNER_CONTROL_GROUP) if k in keys]
    if keys != runner_order:
        return ("the runner executes these actions as " + " -> ".join(runner_order) + " regardless of file order; "
                "write them in that order so the step reads the way it runs")
    return None


def _side(kind: str, part: object, registry: dict[str, dict]) -> tuple[str, list[str], list[str]]:
    """Review one side (``do`` or ``expect``): returns (status, reasons, native keys in file order).

    One or more keys are allowed. Every key must be reviewed and its value must pass; an invalid value outranks an
    unsupported key. Several ``expect`` keys are all required to hold (order is irrelevant); several ``do`` keys are
    checked by ``_action_order_problem``.
    """
    noun = "action" if kind == "do" else "check"
    if not isinstance(part, dict):
        return "INVALID", [f"{kind} must be an object"], []
    if not part:
        return "UNSUPPORTED", [f"at least one {noun} is needed"], []
    keys = list(part)
    invalid, unsupported = [], []
    for key in keys:
        definition = registry.get(key)
        if definition is None:
            unsupported.append(f"no reviewed {noun} {key!r}")
            continue
        problem = check_param(definition["param"], part[key])
        if problem:
            invalid.append(f"{noun} {key!r}: parameter {definition['param']['name']!r} {problem}")
    if invalid:
        return "INVALID", invalid + unsupported, keys
    if unsupported:
        return "UNSUPPORTED", unsupported, keys
    if kind == "do":
        problem = _action_order_problem(keys)
        if problem:
            return "UNSUPPORTED", [problem], keys
    return "SUPPORTED", [], keys


def _review_one(index: int, step: object, pairs: dict[tuple[str, str], str], *, stored: bool = False) -> dict:
    """Review one native step. ``stored=True`` is the draft field: it also allows an optional ``note``."""
    def row(status, reasons, name=None, built=None, template_id=None):
        return {"index": index, "name": name, "status": status, "template_id": template_id,
                "step": built, "reasons": reasons}

    if not isinstance(step, dict):
        return row("INVALID", ["step is not an object"])
    name = step.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > _MAX_NAME:
        return row("INVALID", [f"name must be non-empty text of at most {_MAX_NAME} characters"])
    name = name.strip()
    extra = sorted(str(k) for k in set(step) - _NATIVE_FIELDS - ({"note"} if stored else set()))
    if extra:  # never drop fields silently: a step the library cannot keep whole is not imported or stored
        return row("UNSUPPORTED", ["unsupported field(s): " + ", ".join(extra) +
                                   " (they cannot be kept, so the step is not accepted)"], name)
    if not stored and step.get("expect") == {} and "do" in step:
        # The export form of an action-only step (XiHeadless requires an expect object); it means "no check".
        step = {k: v for k, v in step.items() if k != "expect"}
    if "do" not in step and "expect" not in step:
        return row("UNSUPPORTED", ["needs an action (do), a check (expect), or both"], name)
    built: dict = {}
    keys: dict[str, list[str]] = {}
    statuses, reasons = [], []
    for kind, registry in (("do", _ACTION_DEFS), ("expect", _CHECK_DEFS)):
        if kind not in step:
            continue
        status, why, key = _side(kind, step[kind], registry)
        statuses.append(status)
        reasons += why
        if status == "SUPPORTED":
            keys[kind] = key
            built[kind] = copy.deepcopy(step[kind])
    if "INVALID" in statuses:
        return row("INVALID", reasons, name)
    if "UNSUPPORTED" in statuses:
        return row("UNSUPPORTED", reasons, name)
    single = {k: v[0] for k, v in keys.items() if len(v) == 1}
    pair = (single.get("do"), single.get("expect")) if len(single) == len(keys) else None
    built.update({"template_id": pairs.get(pair) if pair else None,
                  "support_tier": _HEADLESS, "native_schema_head": NATIVE_SCHEMA_HEAD,
                  "oracle_status": "UNAPPROVED", "verdict": "UNKNOWN", "execution_enabled": False})
    return row("SUPPORTED", [], name, built, built["template_id"])


def review_native_steps(steps: object) -> dict:
    """Review native scenario steps against the typed library without trusting them.

    A step may have an action (``do``), a check (``expect``), or both, each holding one or more reviewed native
    keys (several checks must all hold; several actions follow the runner-order rules above). Every step is reported as ``SUPPORTED`` (reviewed shape, values pass), ``UNSUPPORTED`` (well formed but
    outside what the library models) or ``INVALID`` (malformed, or a value that is rejected), with reasons.
    Nothing is accepted automatically: the result is for a human reviewer. A passing step has only had its
    *shape* checked; its source stays unreviewed, its oracle UNAPPROVED and its verdict UNKNOWN.
    """
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_IMPORT_STEPS:
        raise ValueError(f"a native scenario must be an array of 1 to {MAX_IMPORT_STEPS} steps")
    pairs = _template_by_pair()
    rows = [_review_one(i, step, pairs) for i, step in enumerate(steps)]
    counts = {status: sum(1 for r in rows if r["status"] == status) for status in ("SUPPORTED", "UNSUPPORTED", "INVALID")}
    return {"schema": "toolkit-typed-native-review/1", "source_trust": "UNREVIEWED_EXTERNAL_INPUT",
            "native_schema_head": NATIVE_SCHEMA_HEAD, "steps": rows, "counts": counts}


def validate_native_steps(value: object) -> object:
    """Validate the ``native_steps`` field stored with a draft; returns ``value`` unchanged or raises ValueError.

    Shape: ``{"library_version": 1, "steps": [...]}`` with 1 to 50 steps. Every stored step must be SUPPORTED by
    this library (so nothing malformed or unreviewed is ever saved), have a unique name with no surrounding
    whitespace, and may carry a short ``note`` (provenance text). Nothing is trimmed or ignored.
    """
    if not isinstance(value, dict) or set(value) != {"library_version", "steps"}:
        raise ValueError("invalid native_steps: expected exactly library_version and steps")
    if type(value["library_version"]) is not int or value["library_version"] != LIBRARY_VERSION:
        raise ValueError("unsupported native_steps library version")
    steps = value["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_NATIVE_STEPS:
        raise ValueError(f"native_steps must have 1 to {MAX_NATIVE_STEPS} steps")
    pairs, names = _template_by_pair(), set()
    for index, step in enumerate(steps):
        result = _review_one(index, step, pairs, stored=True)
        if result["status"] != "SUPPORTED":
            raise ValueError(f"native_steps[{index}] is {result['status'].lower()}: " + "; ".join(result["reasons"]))
        name = step["name"]
        if name != name.strip():
            raise ValueError(f"native_steps[{index}] name must not have leading or trailing whitespace")
        if name in names:
            raise ValueError(f"native_steps[{index}] duplicates the name {name!r}")
        names.add(name)
        if "note" in step:
            note = step["note"]
            if not isinstance(note, str) or not 1 <= len(note) <= _MAX_NOTE or _CONTROL.search(note):
                raise ValueError(f"native_steps[{index}] note must be 1 to {_MAX_NOTE} characters of plain text")
    return value
