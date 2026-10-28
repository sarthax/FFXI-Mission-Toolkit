"""#1409 typed action library: parity with the merged crosswalk fixture and phase-2 guard. Offline only."""
import copy
import importlib.util
import re
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
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}, "timeout": 5000}, "UNSUPPORTED", "unsupported field(s): timeout"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}, "note": "x", "extra": 1}, "UNSUPPORTED", "extra, note"),
    ({"name": "a"}, "UNSUPPORTED", "needs an action (do), a check (expect), or both"),
    ({"name": "a", "do": {}, "expect": {"x_near": 3}}, "UNSUPPORTED", "exactly one action is supported"),
    ({"name": "a", "expect": {}}, "UNSUPPORTED", "exactly one check is supported"),  # an empty check with no action asserts nothing
    ({"name": "a", "do": {"walk_to": [1, 2], "engage": 5}, "expect": {"x_near": 3}}, "UNSUPPORTED", "exactly one action"),
    ({"name": "a", "do": {"dance": 1}, "expect": {"zone": 3}}, "UNSUPPORTED", "no reviewed action 'dance'"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"made_up": 3}}, "UNSUPPORTED", "no reviewed check 'made_up'"),
    ({"name": "a", "do": {"talk_npc": -1}, "expect": {"event_active": True}}, "INVALID", "npc_id"),
    ({"name": "a", "do": {"talk_npc": 1}, "expect": {"event_active": "yes"}}, "INVALID", "event_active"),
    ({"name": "a", "do": {"walk_to": [float("nan"), 2]}, "expect": {"x_near": 3}}, "INVALID", "coordinates"),
    ({"name": "a", "do": "walk_to", "expect": {"x_near": 3}}, "INVALID", "do must be an object"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "expect": [1]}, "INVALID", "expect must be an object"),
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
    row = _one({"name": "a", "do": {"walk_to": [1, 2]}, "expect": {"x_near": 3}, "timeout": 5000})
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


# --- independent actions and checks (decision 1 of the native_steps proposal) ---------------------

def test_independent_actions_and_checks_cover_the_reviewed_native_keys():
    actions, checks = lib.list_actions(), lib.list_checks()
    assert len(actions) == 10 and len(checks) == 8
    assert {a["native_key"] for a in actions} == {r["native_action"] for r in CROSSWALK if r["native_action"] != "NONE"}
    assert {c["native_key"] for c in checks} == {r["native_expectation"] for r in CROSSWALK if r["native_expectation"] != "NONE"}
    assert {a["native_key"] for a in actions} == {n for n, _ in guard.ROWS.values() if n}
    assert {c["native_key"] for c in checks} == {e for _, e in guard.ROWS.values() if e}
    assert all(a["execution_enabled"] is False and a["support_tier"] == "HEADLESS_SCHEMA_ONLY" for a in actions + checks)
    assert all(a["param"]["constraint"] for a in actions + checks)


def test_independent_parts_carry_the_same_specs_and_picker_hints_as_the_templates():
    by_action = {a["native_key"]: a for a in lib.list_actions()}
    by_check = {c["native_key"]: c for c in lib.list_checks()}
    for template in action_templates():
        assert by_action[template["action"]["native_key"]]["param"] == template["action"]["param"]
        assert by_check[template["expectation"]["native_key"]]["param"] == template["expectation"]["param"]
    assert by_action["talk_npc"]["param"]["picker"] == "npc" and by_check["zone"]["param"]["picker"] == "zone"


def test_exports_are_unaliased_and_the_registry_lists_the_parts():
    registry = lib.export_registry()
    assert len(registry["actions"]) == 10 and len(registry["checks"]) == 8
    registry["actions"][0]["param"]["type"] = "bool"
    assert lib.list_actions()[0]["param"]["type"] != "bool"


def _valid_values():
    acts = {a["native_key"]: next(v for v in ACTION_VALUES[key(a["param"])] if lib.check_param(a["param"], v) is None)
            for a in lib.list_actions()}
    chks = {c["native_key"]: next(v for v in EXPECT_VALUES[key(c["param"])] if lib.check_param(c["param"], v) is None)
            for c in lib.list_checks()}
    return acts, chks


def test_every_reviewed_action_and_check_is_accepted_alone_and_in_every_combination():
    acts, chks = _valid_values()
    steps = []
    for a, av in acts.items():
        steps.append({"name": f"do {a}", "do": {a: av}})
    for c, cv in chks.items():
        steps.append({"name": f"check {c}", "expect": {c: cv}})
    review = lib.review_native_steps(steps)
    assert review["counts"] == {"SUPPORTED": 18, "UNSUPPORTED": 0, "INVALID": 0}
    for row in review["steps"]:  # single-sided steps carry only the side they have
        assert ("do" in row["step"]) != ("expect" in row["step"]) and row["template_id"] is None
    pairs = lib._template_by_pair()
    seen = 0
    for a, av in acts.items():
        for c, cv in chks.items():
            row = lib.review_native_steps([{"name": "x", "do": {a: av}, "expect": {c: cv}}])["steps"][0]
            assert row["status"] == "SUPPORTED", (a, c)
            assert (row["template_id"] is not None) == ((a, c) in pairs)  # only the 10 reviewed pairs get a template id
            seen += 1
    assert seen == 80


def test_a_bad_value_on_either_side_is_invalid_and_names_the_side():
    row = lib.review_native_steps([{"name": "x", "do": {"talk_npc": 1}, "expect": {"hpp": "high"}}])["steps"][0]
    assert row["status"] == "INVALID" and "check 'hpp'" in row["reasons"][0] and "must be an integer" in row["reasons"][0]
    row = lib.review_native_steps([{"name": "x", "do": {"rest_hp": 0}}])["steps"][0]
    assert row["status"] == "INVALID" and "action 'rest_hp'" in row["reasons"][0] and "1..100" in row["reasons"][0]


# --- the stored native_steps field ----------------------------------------------------------------

def stored(*steps, version=1):
    return {"library_version": version, "steps": list(steps)}


GOOD = {"name": "talk to guide", "do": {"talk_npc": 17719298}, "expect": {"event_active": True},
        "note": "npc_id from DSP catalog sql/npc_list.sql; not verified for this zone or client"}


def test_a_valid_stored_field_is_accepted_unchanged_including_single_sided_steps_and_notes():
    value = stored(GOOD, {"name": "just walk", "do": {"walk_to": [1, 2]}}, {"name": "just check", "expect": {"zone": 231}})
    assert lib.validate_native_steps(value) is value
    assert lib.validate_native_steps(stored({"name": "n" * 100, "do": {"rest_hp": 5}, "note": "x" * 300}))


@pytest.mark.parametrize("value,fragment", [
    (None, "expected exactly library_version and steps"), ([], "expected exactly"), ("x", "expected exactly"),
    ({"steps": [GOOD]}, "expected exactly"), ({"library_version": 1, "steps": [GOOD], "extra": 1}, "expected exactly"),
    (stored(GOOD, version=2), "unsupported native_steps library version"),
    (stored(GOOD, version=True), "unsupported native_steps library version"),
    (stored(GOOD, version="1"), "unsupported native_steps library version"),
    (stored(), "1 to 50 steps"), ({"library_version": 1, "steps": "x"}, "1 to 50 steps"),
    ({"library_version": 1, "steps": None}, "1 to 50 steps"),
])
def test_a_malformed_stored_field_is_rejected(value, fragment):
    with pytest.raises(ValueError, match=re.escape(fragment)):
        lib.validate_native_steps(value)


@pytest.mark.parametrize("step,fragment", [
    ({"name": "a", "do": {"dance": 1}}, "unsupported: no reviewed action"),
    ({"name": "a", "expect": {"made_up": 1}}, "unsupported: no reviewed check"),
    ({"name": "a", "do": {"talk_npc": -1}}, "invalid:"),
    ({"name": "a"}, "needs an action"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "timeout": 5}, "unsupported field(s): timeout"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "provenance": "x"}, "unsupported field(s): provenance"),
    ({"do": {"walk_to": [1, 2]}}, "name must be non-empty"),
    ({"name": " padded ", "do": {"walk_to": [1, 2]}}, "leading or trailing whitespace"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "note": ""}, "note must be 1 to 300"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "note": "x" * 301}, "note must be 1 to 300"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "note": 5}, "note must be 1 to 300"),
    ({"name": "a", "do": {"walk_to": [1, 2]}, "note": "line\nbreak"}, "note must be 1 to 300"),
    ("not an object", "invalid: step is not an object"),
])
def test_an_unreviewed_or_malformed_stored_step_is_rejected_not_trimmed(step, fragment):
    with pytest.raises(ValueError, match=re.escape(fragment)):
        lib.validate_native_steps(stored(step))


def test_stored_names_must_be_unique_and_the_limit_is_fifty():
    with pytest.raises(ValueError, match="duplicates the name 'a'"):
        lib.validate_native_steps(stored({"name": "a", "do": {"rest_hp": 5}}, {"name": "a", "do": {"rest_hp": 6}}))
    fifty = [{"name": f"s{i}", "do": {"rest_hp": 5}} for i in range(50)]
    assert lib.validate_native_steps(stored(*fifty))
    with pytest.raises(ValueError, match="1 to 50 steps"):
        lib.validate_native_steps(stored(*fifty, {"name": "s50", "do": {"rest_hp": 5}}))


def test_a_stored_note_is_allowed_but_an_imported_native_step_may_not_carry_one():
    assert lib.review_native_steps([{"name": "a", "do": {"rest_hp": 5}, "note": "x"}])["steps"][0]["status"] == "UNSUPPORTED"
    assert lib.validate_native_steps(stored({"name": "a", "do": {"rest_hp": 5}, "note": "x"}))


# --- #1457: the export form of an action-only step, and #1459: observed execution paths --------------------------

def test_exported_action_only_form_is_read_back_as_action_only():
    """XiHeadless needs `expect` to be an object, so the export writes `"expect": {}` for an action-only step.
    Importing that export must give the same step back, with no empty side kept."""
    review = lib.review_native_steps([{"name": "a", "do": {"walk_to": [1, 2]}, "expect": {}}])
    row = review["steps"][0]
    assert row["status"] == "SUPPORTED", row
    assert "expect" not in row["step"] and row["step"]["do"] == {"walk_to": [1, 2]}


def test_empty_expect_is_never_stored():
    with pytest.raises(ValueError):
        lib.validate_native_steps({"library_version": 1, "steps": [{"name": "a", "do": {"walk_to": [1, 2]}, "expect": {}}]})


def test_observed_paths_cover_exactly_the_library_keys_and_never_claim_execution():
    parts = lib.list_actions() + lib.list_checks()
    assert len(parts) == 18 and len({p["native_key"] for p in parts}) == 18
    for part in parts:
        paths = part["observed_paths"]
        assert paths["execution_tested"] is False
        assert paths["xiheadless_loader"]["status"] == "ACCEPTS"
        assert paths["source"].startswith("xiheadless-main@e5e80350711d5d2ec814c893a17c63baf3ef98a9")
    mcp = {p["native_key"]: p["observed_paths"]["mcp_task_start"] for p in parts}
    assert [k for k, v in mcp.items() if v["status"] == "ACCEPTS"] == ["wait_ms"]
    assert {mcp[k]["reason"] for k in ("invite", "accept_invite")} == {"scenario_legacy_actions_not_supported"}
    assert {mcp[k]["reason"] for k in ("x_near", "zone", "hpp")} == {"scenario_expectations_not_yet_supported"}
    assert mcp["walk_to"]["reason"] == "scenario_resource_actions_not_yet_supported"
    # the registry export carries the same data the UI reads
    exported = {p["native_key"]: p["observed_paths"] for p in lib.export_registry()["actions"] + lib.export_registry()["checks"]}
    assert exported.keys() == mcp.keys()
