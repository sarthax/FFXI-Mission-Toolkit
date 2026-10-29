"""#1411 saved typed steps: the optional `native_steps` draft field, its hash exclusion, and the draft store.
Synthetic drafts only; a temporary SQLite file; nothing is executed."""
import copy
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing import typed_action_library as lib
from workbench.server_admin.feature_testing.scenario_contract_v2 import base_spec_sha256, compatibility_report
from workbench.server_admin.feature_testing.spec_drafts import get_drafts, save_draft
from workbench.server_admin.feature_testing.test_specifications import specification, validate_spec
from workbench.server_admin.scenario_authoring.editor_router import validate_editor_spec

ROOT = Path(__file__).resolve().parents[1]
STEPS = {"library_version": 1, "steps": [
    {"name": "talk to guide", "do": {"talk_npc": 17719298}, "expect": {"event_active": True},
     "note": "npc_id from DSP catalog sql/npc_list.sql; not verified for this zone or client"},
    {"name": "walk to the gate", "do": {"walk_to": {"coords": [10.5, 3.25, -4.0], "timeout_ms": 60000}}},
    {"name": "check the zone", "expect": {"zone": 231}}]}


def draft():
    spec = copy.deepcopy(specification("inventory_observation", "INV-OBS-01"))
    spec["case_id"] = "INV-OBS-NATIVE-STEPS"
    return spec


@pytest.fixture()
def drafts_db(monkeypatch, tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "drafts.sqlite"))
    return tmp_path / "drafts.sqlite"


# --- validation -------------------------------------------------------------------------------------

def test_a_specification_with_native_steps_validates_and_the_field_is_optional():
    plain = draft()
    validate_spec(plain)
    with_steps = copy.deepcopy(plain)
    with_steps["native_steps"] = copy.deepcopy(STEPS)
    assert validate_spec(with_steps) is with_steps


def test_unknown_top_level_fields_are_still_rejected():
    spec = draft()
    spec["native_step"] = copy.deepcopy(STEPS)  # a typo of the field name must not pass
    with pytest.raises(ValueError, match="unexpected test specification fields"):
        validate_spec(spec)


@pytest.mark.parametrize("value,fragment", [
    ({"library_version": 2, "steps": STEPS["steps"]}, "unsupported native_steps library version"),
    ({"library_version": 1, "steps": []}, "1 to 50 steps"),
    ({"library_version": 1, "steps": [{"name": "a", "do": {"dance": 1}}]}, "no reviewed action"),
    ({"library_version": 1, "steps": [{"name": "a", "do": {"talk_npc": -1}}]}, "invalid"),
    ({"library_version": 1, "steps": [{"name": "a", "do": {"rest_hp": 5}, "execution_enabled": True}]}, "unsupported field"),
    (None, "invalid native_steps"),
])
def test_bad_native_steps_make_the_whole_specification_invalid(value, fragment):
    spec = draft()
    spec["native_steps"] = value
    with pytest.raises(ValueError, match=fragment):
        validate_spec(spec)


def test_the_guided_editor_validation_accepts_native_steps_and_stays_design_only():
    from test_scenario_guided_editor import synthetic_draft  # existing synthetic guided draft
    spec = synthetic_draft()
    spec["native_steps"] = copy.deepcopy(STEPS)
    result = validate_editor_spec(spec)
    assert result["canonical_specification"]["native_steps"] == STEPS
    assert result["execution_enabled"] is False and result["operator_review_required"] is True
    assert result["preview"]["maturity"].startswith("DESIGN_ONLY")
    assert result["preview"]["independent_verification"] == "NOT_ESTABLISHED"


# --- hash and v2 compatibility ------------------------------------------------------------------------

def test_native_steps_do_not_change_the_v1_fingerprint_but_real_changes_still_do():
    base = draft()
    baseline = base_spec_sha256(base)
    with_steps = copy.deepcopy(base)
    with_steps["native_steps"] = copy.deepcopy(STEPS)
    assert base_spec_sha256(with_steps) == baseline
    edited = copy.deepcopy(with_steps)
    edited["native_steps"]["steps"][0]["do"]["talk_npc"] = 5
    assert base_spec_sha256(edited) == baseline  # editing a step cannot invalidate recorded v2 fingerprints
    changed = copy.deepcopy(base)
    changed["name"] = changed["name"] + " (changed)"
    assert base_spec_sha256(changed) != baseline  # the exclusion is narrow: v1 core changes are still detected


def test_existing_specifications_hash_exactly_as_before():
    # Pinned: a spec with no native_steps must keep its old fingerprint (nothing recorded in a draft may shift).
    spec = json.loads((ROOT / "test_fixtures" / "scenario_contract_v2_synthetic.json").read_text())["specification"]
    legacy = {k: v for k, v in spec.items() if k != "contract_v2"}
    import hashlib
    raw = json.dumps(legacy, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    assert base_spec_sha256(spec) == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_adding_native_steps_does_not_trip_the_v2_fingerprint_check():
    spec = json.loads((ROOT / "test_fixtures" / "scenario_contract_v2_synthetic.json").read_text())["specification"]
    spec["contract_v2"]["fingerprints"]["base_spec_sha256"] = base_spec_sha256(spec)
    before = compatibility_report(spec)
    assert "base specification SHA-256 mismatch" not in before["reasons"]
    spec["native_steps"] = copy.deepcopy(STEPS)
    after = compatibility_report(spec)
    assert after == before and "base specification SHA-256 mismatch" not in after["reasons"]
    spec["purpose"] = "a different purpose"  # control: a real v1 change is still a mismatch
    assert "base specification SHA-256 mismatch" in compatibility_report(spec)["reasons"]


# --- the draft store --------------------------------------------------------------------------------

def test_native_steps_survive_save_reload_and_revision(drafts_db):
    spec = draft()
    spec["native_steps"] = copy.deepcopy(STEPS)
    first = save_draft(spec, 0)
    assert first["revision"] == 1 and first["execution_enabled"] is False
    [stored] = get_drafts()
    assert stored["specification"]["native_steps"] == STEPS
    edited = copy.deepcopy(stored["specification"])
    edited["native_steps"]["steps"].append({"name": "one more", "do": {"rest_hp": 50}})
    assert save_draft(edited, 1)["revision"] == 2
    assert len(get_drafts()[0]["specification"]["native_steps"]["steps"]) == 4
    with pytest.raises(ValueError, match="revision conflict"):
        save_draft(edited, 1)


def test_an_invalid_native_steps_field_is_refused_and_nothing_is_written(drafts_db):
    spec = draft()
    spec["native_steps"] = {"library_version": 1, "steps": [{"name": "a", "do": {"say": "hi"}}]}
    with pytest.raises(ValueError, match="no reviewed action"):
        save_draft(spec, 0)
    assert get_drafts() == []


def test_native_steps_can_never_make_a_draft_executable_or_published(drafts_db):
    spec = draft()
    spec["native_steps"] = copy.deepcopy(STEPS)
    spec["runner"] = "xiheadless_observation_v1"
    with pytest.raises(ValueError, match="design_only"):
        save_draft(spec, 0)
    spec = draft()
    spec["native_steps"] = copy.deepcopy(STEPS)
    spec["execution_status"] = "verified_runner"
    with pytest.raises(ValueError, match="design_only"):
        save_draft(spec, 0)
    published = copy.deepcopy(specification("inventory_observation", "INV-OBS-01"))
    published["native_steps"] = copy.deepcopy(STEPS)
    with pytest.raises(ValueError, match="published"):
        save_draft(published, 0)
    assert get_drafts() == []


def _largest_steps():
    return {"library_version": 1, "steps": [
        {"name": f"{i:02d}-" + "n" * 97, "do": {"walk_to": {"coords": [-123456.789, 98765.4321, -0.000123],
                                                          "timeout_ms": 3600000, "stall_ms": 3600000}},
         "expect": {"x_near": -99999.99999}, "note": "x" * 300} for i in range(50)]}


def test_fifty_maximum_size_steps_still_fit_in_a_normal_draft(drafts_db):
    spec = draft()
    spec["native_steps"] = _largest_steps()
    size = len(json.dumps(spec, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8"))
    assert size < 32768, size  # the worst case the field allows leaves room for a normal draft
    assert save_draft(spec, 0)["revision"] == 1


def test_the_draft_size_cap_still_applies_when_everything_else_is_also_large(drafts_db):
    spec = draft()
    spec["native_steps"] = _largest_steps()
    spec["behavior"] = {phase: ["g" * 500] * 20 for phase in ("given", "when", "then")}  # 30,000 bytes of narrative
    with pytest.raises(ValueError, match="32"):  # the existing 32 KiB guard fires, unchanged
        save_draft(spec, 0)
    assert get_drafts() == []
