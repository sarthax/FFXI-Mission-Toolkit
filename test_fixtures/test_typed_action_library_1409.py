"""#1409 typed action library: parity with the merged crosswalk fixture and phase-2 guard. Offline only."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing import typed_action_library as lib

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = json.loads((ROOT / "test_fixtures" / "scenario_suite_typed_registry_1409.json").read_text())["entries"]
_spec = importlib.util.spec_from_file_location("guard1409", ROOT / "tools" / "scenario_typed_library_contract_1409.py")
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

NAN, INF = float("nan"), float("inf")
# (action values, expectation values) worth trying for each parameter type, valid and invalid
ACTION_VALUES = {
    "walk_target": [[1.0, 2.0], [1, 2, 3], {"coords": [1.25, 2.5, 3.75], "stall_ms": 100},
                    {"coords": [1, 2], "timeout_ms": 3600000}, {"coords": [1, 2], "timeout_ms": 0},
                    {"coords": [1, 2], "timeout_ms": 3600001}, {"coords": [1, 2], "extra": 1}, {"timeout_ms": 5},
                    {"coords": [NAN, 2]}, [NAN, 2], [INF, 3], [True, 3], [1], [1, 2, 3, 4], [], "1,2",
                    [1e40, 2], [2, -1e40, 3], {"coords": [1e100, 2]}, None, 5],
    "uint32": [0, 1, 42, 4294967295, 4294967296, -1, True, False, 1.0, "1", None, [1]],
    "int_range:0:3600000": [0, 1, 3600000, 3600001, -1, True, 1.5, "5", None],
    "int_range:1:100": [1, 50, 100, 0, 101, -1, True, 2.5, None],
    "bool": [True, False, 0, 1, "true", None],
}
EXPECT_VALUES = {
    "finite_number": [0, 4.2, -3.5, NAN, INF, True, "4", None],
    "bool": [True, False, 0, 1, "true", None],
    "uint53": [0, 7, 2 ** 53, 2 ** 53 + 1, -1, True, 1.5, "7", None],
}


def key(param):
    return f"int_range:{param['min']}:{param['max']}" if param["type"] == "int_range" else param["type"]


def action_templates():
    return [t for t in lib.list_templates() if t["kind"] == "action_expectation"]


# --- registry vs the merged crosswalk fixture --------------------------------------------------

def test_registry_matches_the_reviewed_crosswalk_row_for_row():
    templates = lib.list_templates()
    assert [t["id"] for t in templates] == [r["id"] for r in CROSSWALK]
    assert 10 <= len(templates) <= 15
    for template, row in zip(templates, CROSSWALK):
        assert template["kind"] == row["kind"]
        assert template["label"] == row["human_label"]
        assert template["support_tier"] == row["support_tier"]
        assert template["source_ref"] == row["source_ref"]
        assert template["limitations"] == row["limitations"]
        # the crosswalk writes "NONE" where a readback has no native Headless key
        native_action = template["action"]["native_key"] if template["action"] else "NONE"
        native_expect = template["expectation"]["native_key"] if template["expectation"] else "NONE"
        assert (native_action, native_expect) == (row["native_action"], row["native_expectation"]), template["id"]


def test_parameter_names_match_the_crosswalk_text():
    for template, row in zip(lib.list_templates(), CROSSWALK):
        if template["action"]:
            assert row["typed_parameters"].startswith(template["action"]["param"]["name"] + ":"), template["id"]


# --- library vs the reviewed phase-2 guard ------------------------------------------------------

def test_native_pairs_match_the_guard():
    assert lib.NATIVE_SCHEMA_HEAD == guard.NATIVE
    for template in lib.list_templates():
        native = guard.ROWS[template["id"]]
        if template["kind"] == "observation":
            assert native == (None, None)
        else:
            assert native == (template["action"]["native_key"], template["expectation"]["native_key"])
    assert set(guard.ROWS) == {t["id"] for t in lib.list_templates()}


def _guard_recognizes(template_id, action_value, expect_value):
    native, expect = guard.ROWS[template_id]
    candidate = {"row_id": template_id, "phase1_head": guard.PHASE1, "native_head": guard.NATIVE,
                 "do": {native: action_value}, "expect": {expect: expect_value}, "execution_enabled": False,
                 "publish_enabled": False, "oracle_status": "UNAPPROVED", "verdict": "UNKNOWN"}
    return guard.validate(candidate).get("native_shape_recognized") is True


def test_library_accepts_exactly_what_the_guard_recognizes():
    checked = 0
    for template in action_templates():
        a_param, e_param = template["action"]["param"], template["expectation"]["param"]
        good_expect = next(v for v in EXPECT_VALUES[key(e_param)] if lib.check_param(e_param, v) is None)
        good_action = next(v for v in ACTION_VALUES[key(a_param)] if lib.check_param(a_param, v) is None)
        for value in ACTION_VALUES[key(a_param)]:
            mine = lib.check_param(a_param, value) is None
            assert mine == _guard_recognizes(template["id"], value, good_expect), (template["id"], "action", value)
            checked += 1
        for value in EXPECT_VALUES[key(e_param)]:
            mine = lib.check_param(e_param, value) is None
            assert mine == _guard_recognizes(template["id"], good_action, value), (template["id"], "expect", value)
            checked += 1
    assert checked >= 200


# --- build_step ---------------------------------------------------------------------------------

def test_build_step_produces_a_native_draft_step_the_guard_recognizes():
    step = lib.build_step("navigate_near", [1.5, 2.5], 4.2)
    assert step["do"] == {"walk_to": [1.5, 2.5]} and step["expect"] == {"x_near": 4.2}
    assert step["support_tier"] == "HEADLESS_SCHEMA_ONLY" and step["native_schema_head"] == lib.NATIVE_SCHEMA_HEAD
    assert (step["oracle_status"], step["verdict"], step["execution_enabled"]) == ("UNAPPROVED", "UNKNOWN", False)
    for template in action_templates():
        a, e = template["action"]["param"], template["expectation"]["param"]
        av = next(v for v in ACTION_VALUES[key(a)] if lib.check_param(a, v) is None)
        ev = next(v for v in EXPECT_VALUES[key(e)] if lib.check_param(e, v) is None)
        built = lib.build_step(template["id"], av, ev)
        assert _guard_recognizes(template["id"], built["do"][template["action"]["native_key"]],
                                 built["expect"][template["expectation"]["native_key"]])


def test_build_step_rejects_bad_values_naming_the_template_and_parameter():
    with pytest.raises(ValueError, match=r"talk_to_npc: action parameter 'npc_id' must be an integer 0\.\.4294967295"):
        lib.build_step("talk_to_npc", -1, True)
    with pytest.raises(ValueError, match=r"talk_to_npc: expectation parameter 'event_active' must be true or false"):
        lib.build_step("talk_to_npc", 7, "yes")
    with pytest.raises(ValueError, match="navigate_near: action parameter 'coordinates'"):
        lib.build_step("navigate_near", [NAN, 1], 1)
    with pytest.raises(ValueError, match="recover_hp: action parameter 'hp_percent' must be an integer 1..100"):
        lib.build_step("recover_hp", 0, 50)


def test_readbacks_and_unknown_templates_are_not_buildable_as_steps():
    for template_id in ("read_inventory", "read_progression"):
        with pytest.raises(ValueError, match="Toolkit readback .* not a Headless step"):
            lib.build_step(template_id, 1, 1)
    with pytest.raises(ValueError, match="unknown template"):
        lib.build_step("warp_target", 1, 1)
    with pytest.raises(ValueError, match="unknown template"):
        lib.get_template("../../etc/passwd")


def test_build_step_does_not_alias_its_inputs():
    coords = {"coords": [1, 2, 3], "timeout_ms": 100}
    step = lib.build_step("navigate_near", coords, 1)
    coords["coords"].append(9)
    assert step["do"]["walk_to"]["coords"] == [1, 2, 3]


# --- registry safety and shape ------------------------------------------------------------------

def test_readbacks_name_real_supervisor_routes_and_no_native_pair():
    routes = {t["id"]: t["readback"]["route"] for t in lib.list_templates() if t["kind"] == "observation"}
    assert routes == {"read_inventory": "/api/supervisor/test-character-inventory-v2",
                      "read_progression": "/api/supervisor/test-character-progression"}
    from workbench.server_admin.feature_testing import supervisor
    registered = {r.path for r in supervisor.router.routes if "GET" in getattr(r, "methods", ())}
    for route in routes.values():
        assert route in registered, route  # a real, GET-only supervisor route
    assert all(t["action"] is None and t["expectation"] is None for t in lib.list_templates() if t["kind"] == "observation")


def test_every_template_is_nonexecutable_and_authority_free():
    for template in lib.list_templates():
        assert (template["execution_enabled"], template["oracle_status"], template["verdict"]) == (False, "UNAPPROVED", "UNKNOWN")
        assert template["support_tier"] in {"HEADLESS_SCHEMA_ONLY", "TOOLKIT_READBACK_ONLY"}
    assert lib.export_registry()["headless_wire_contract_approved"] is False


def test_export_is_deterministic_serializable_and_unaliased():
    first = json.dumps(lib.export_registry(), sort_keys=True)
    assert first == json.dumps(lib.export_registry(), sort_keys=True)
    registry = lib.export_registry()
    assert registry["schema"] == lib.SCHEMA and registry["library_version"] == 1
    registry["templates"][0]["label"] = "tampered"
    registry["templates"][0]["action"]["param"]["type"] = "bool"
    assert json.dumps(lib.export_registry(), sort_keys=True) == first
    ids = [t["id"] for t in registry["templates"]]
    assert len(ids) == len(set(ids))


def test_picker_hints_are_exactly_the_npc_and_zone_id_parameters():
    """Picker hints are UI helpers for catalog lookup; they never change which values are valid."""
    hints = {}
    for template in lib.list_templates():
        for part in ("action", "expectation"):
            if template[part] and template[part]["param"].get("picker"):
                hints[(template["id"], part)] = (template[part]["param"]["name"], template[part]["param"]["picker"])
    assert hints == {("talk_to_npc", "action"): ("npc_id", "npc"), ("inspect_npc", "action"): ("npc_id", "npc"),
                     ("wait_for_state", "expectation"): ("zone", "zone")}
    for _, kind in hints.values():  # every hinted kind is one the catalog search route supports
        assert kind in {"item", "keyitem", "npc", "mob", "zone", "gm"}
    # a hint never changes validation: the same checks apply with or without it
    spec = lib.get_template("talk_to_npc")["action"]["param"]
    assert lib.check_param(spec, 7) is None and lib.check_param(spec, -1) is not None


# --- reviewing native scenario JSON -------------------------------------------------------------

def _native(step):
    return {"name": step["template_id"], "do": step["do"], "expect": step["expect"]}


def _all_valid_native_steps():
    steps = []
    for template in action_templates():
        a, e = template["action"]["param"], template["expectation"]["param"]
        av = next(v for v in ACTION_VALUES[key(a)] if lib.check_param(a, v) is None)
        ev = next(v for v in EXPECT_VALUES[key(e)] if lib.check_param(e, v) is None)
        steps.append(_native(lib.build_step(template["id"], av, ev)))
    return steps


def test_every_template_round_trips_through_the_review():
    native = _all_valid_native_steps()
    review = lib.review_native_steps(native)
    assert review["counts"] == {"SUPPORTED": 10, "UNSUPPORTED": 0, "INVALID": 0}
    for row, step in zip(review["steps"], native):
        assert row["status"] == "SUPPORTED" and row["reasons"] == [] and row["name"] == step["name"]
        assert row["template_id"] == step["name"]
        assert row["step"]["do"] == step["do"] and row["step"]["expect"] == step["expect"]
        assert (row["step"]["oracle_status"], row["step"]["verdict"], row["step"]["execution_enabled"]) == \
            ("UNAPPROVED", "UNKNOWN", False)


def test_native_pairs_are_unambiguous():
    pairs = lib._template_by_pair()
    assert len(pairs) == len(action_templates()) == 10  # a new template must not share an action/check pair


def _one(step):
    return lib.review_native_steps([step])["steps"][0]


@pytest.mark.parametrize("step,status,fragment", [
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}, "timeout_ms": 5000}, "UNSUPPORTED", "unsupported field(s): timeout_ms"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}, "note": "x", "extra": 1}, "UNSUPPORTED", "extra, note"),
    ({"name": "a", "do": {"walk_to": [1, 2]}}, "UNSUPPORTED", "needs both do and expect"),
    ({"name": "a", "expect": {"x_near": 3}}, "UNSUPPORTED", "needs both do and expect"),
    ({"name": "a", "do": {}, "expect": {"x_near": 3}}, "UNSUPPORTED", "exactly one action and one check"),
    ({"name": "a", "do": {"walk_to": [1, 2], "engage": 5}, "expect": {"x_near": 3}}, "UNSUPPORTED", "exactly one action"),
    ({"name": "a", "do": {"dance": 1}, "expect": {"zone": 3}}, "UNSUPPORTED", "no reviewed template for action 'dance'"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"hpp": 3}}, "UNSUPPORTED", "check 'hpp'"),
    ({"name": "a", "do": {"talk_npc": -1}, "expect": {"event_active": True}}, "INVALID", "npc_id"),
    ({"name": "a", "do": {"talk_npc": 1}, "expect": {"event_active": "yes"}}, "INVALID", "event_active"),
    ({"name": "a", "do": {"walk_to": [float("nan"), 2]}, "expect": {"x_near": 3}}, "INVALID", "coordinates"),
    ({"name": "a", "do": "walk_to", "expect": {"x_near": 3}}, "INVALID", "must each be an object"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": [1]}, "INVALID", "must each be an object"),
    ({"do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}}, "INVALID", "name must be non-empty"),
    ({"name": "   ", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}}, "INVALID", "name must be non-empty"),
    ({"name": "n" * 101, "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}}, "INVALID", "at most 100"),
    ({"name": 5, "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}}, "INVALID", "name must be non-empty"),
    ("not an object", "INVALID", "step is not an object"),
    (None, "INVALID", "step is not an object"),
    ([1], "INVALID", "step is not an object"),
])
def test_unsupported_and_invalid_steps_are_reported_with_reasons_and_never_built(step, status, fragment):
    row = _one(step)
    assert row["status"] == status and row["step"] is None
    assert any(fragment in reason for reason in row["reasons"]), row["reasons"]


def test_a_step_with_extra_fields_is_not_imported_even_though_its_do_and_expect_are_fine():
    row = _one({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}, "timeout_ms": 5000})
    assert row["status"] == "UNSUPPORTED" and row["step"] is None  # never trimmed down to a lossy copy


def test_names_are_trimmed_kept_as_data_and_duplicates_are_left_for_the_reviewer():
    hostile = "  <img src=x onerror=1>  "
    review = lib.review_native_steps([{"name": hostile, "do": {"rest_hp": 50}, "expect": {"hpp": 90}},
                                      {"name": "same", "do": {"rest_hp": 50}, "expect": {"hpp": 90}},
                                      {"name": "same", "do": {"rest_hp": 60}, "expect": {"hpp": 90}}])
    assert [r["name"] for r in review["steps"]] == ["<img src=x onerror=1>", "same", "same"]
    assert review["counts"]["SUPPORTED"] == 3


def test_review_rejects_bad_scenarios_outright_and_does_not_mutate_its_input():
    for bad in (None, {}, "x", 5, [], [None] * 101):
        with pytest.raises(ValueError, match="array of 1 to 100 steps"):
            lib.review_native_steps(bad)
    native = _all_valid_native_steps()
    snapshot = copy.deepcopy(native)
    lib.review_native_steps(native)
    assert native == snapshot
    assert lib.review_native_steps(native[:1])["source_trust"] == "UNREVIEWED_EXTERNAL_INPUT"
    assert len(lib.review_native_steps([native[0]] * 100)["steps"]) == 100


def test_review_counts_add_up_and_indexes_follow_the_input():
    review = lib.review_native_steps([{"name": "ok", "do": {"rest_hp": 5}, "expect": {"hpp": 1}}, 7,
                                      {"name": "u", "do": {"x": 1}, "expect": {"y": 2}}])
    assert [(r["index"], r["status"]) for r in review["steps"]] == [(0, "SUPPORTED"), (1, "INVALID"), (2, "UNSUPPORTED")]
    assert review["counts"] == {"SUPPORTED": 1, "UNSUPPORTED": 1, "INVALID": 1}
