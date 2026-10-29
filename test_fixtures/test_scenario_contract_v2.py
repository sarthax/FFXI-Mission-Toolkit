"""Offline, explicitly SYNTHETIC metadata-contract tests; no gameplay data.

The legacy MOG-09 and INV-OBS-01 inputs are read from the existing canonical
catalog but are NOT edited, re-signed or executed.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing.scenario_contract_v2 import (
    base_spec_sha256, compatibility_report, deserialize_spec, serialize_spec,
)
from workbench.server_admin.feature_testing.test_specifications import (
    specification, specifications, validate_spec,
)
from workbench.server_admin.feature_testing.scenario_presentation import scenario_presentation

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "test_fixtures" / "scenario_contract_v2_synthetic.json"
SYNTH_SHA = "a" * 40
SYNTH_HASH = "b" * 64


def synthetic() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["_fixture_note"].startswith("SYNTHETIC")
    return data["specification"]


def metadata() -> dict:
    return synthetic()["contract_v2"]


def pinned_source(spec: dict) -> dict:
    src = spec["contract_v2"]["sources"][0]
    src.update(revision=SYNTH_SHA, sha256=SYNTH_HASH)
    return src


def test_legacy_canonical_examples_remain_exactly_v1_without_migration():
    old = specifications()
    assert [(x["feature_id"], x["case_id"]) for x in old] == [
        ("moghancement", "MOG-09"), ("inventory_observation", "INV-OBS-01")
    ]
    for feature_id, case_id in (("moghancement", "MOG-09"),
                                ("inventory_observation", "INV-OBS-01")):
        v1 = copy.deepcopy(specification(feature_id, case_id))
        unchanged = copy.deepcopy(v1)
        assert validate_spec(v1) is v1
        assert "contract_v2" not in v1
        assert deserialize_spec(serialize_spec(v1)) == unchanged
        assert v1 == unchanged
        assert compatibility_report(v1)["state"] == "UNKNOWN"
        assert compatibility_report(v1)["execution_enabled"] is False
    assert specification("moghancement", "MOG-09")["execution_status"] == "verified_runner"
    assert specification("inventory_observation", "INV-OBS-01")["execution_status"] == "design_only"


def test_synthetic_fixture_validates_and_round_trips_losslessly():
    spec = synthetic()
    before = copy.deepcopy(spec)
    assert validate_spec(spec) is spec
    serialized = serialize_spec(spec)
    assert deserialize_spec(serialized) == before
    assert serialize_spec(deserialize_spec(serialized)) == serialized
    assert spec["runner"] == "unassigned"
    assert spec["contract_v2"]["step_requirements"][0]["execution_gate"] == "blocked"
    assert spec["contract_v2"]["oracles"][0]["oracle_type"] == "unknown"
    assert spec["contract_v2"]["parameters"][0]["binding_state"] == "ambiguous"


def test_v1_scenario_viewer_outputs_are_identical_with_optional_metadata():
    mog = copy.deepcopy(specification("moghancement", "MOG-09"))
    before = scenario_presentation(mog)
    mog["contract_v2"] = {
        "contract_version": 2, "sources": [], "parameters": [],
        "oracles": [], "step_requirements": [], "fingerprints": {
            "base_spec_sha256": None, "dsp_commit": None,
            "headless_commit": None, "toolkit_commit": None,
        },
    }
    validate_spec(mog)
    assert scenario_presentation(mog) == before
    assert before["independent_verification"] == "NOT_ESTABLISHED"


def test_design_only_draft_validation_and_storage_preserve_metadata(monkeypatch, tmp_path):
    from workbench.server_admin.feature_testing.spec_drafts import (
        _validate_draft, get_drafts, save_draft,
    )
    fixture = synthetic()
    assert _validate_draft(copy.deepcopy(fixture)) == fixture
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB", str(tmp_path / "v2-drafts.sqlite"))
    response = save_draft(fixture, 0)
    assert response["revision"] == 1
    assert response["execution_enabled"] is False
    stored = get_drafts()
    assert stored[0]["specification"]["contract_v2"] == fixture["contract_v2"]
    assert stored[0]["specification"]["execution_status"] == "design_only"


def test_v2_cannot_enable_new_verified_runner():
    spec = synthetic()
    spec["runner"] = "xiheadless_observation_v1"
    spec["execution_status"] = "verified_runner"
    with pytest.raises(ValueError, match="no verified"):
        validate_spec(spec)


def test_missing_source_digest_keeps_candidate_and_unknown_oracle():
    spec = synthetic()
    report = compatibility_report(spec)
    assert report["state"] == "UNKNOWN"
    assert report["independent_verification"] == "NOT_ESTABLISHED"
    assert spec["contract_v2"]["sources"][0]["sha256"] is None
    assert spec["contract_v2"]["parameters"][0]["binding_state"] == "ambiguous"


def test_binding_claim_requires_revision_content_hash_identity_namespace_and_zone():
    spec = synthetic()
    par = spec["contract_v2"]["parameters"][0]
    par.update(binding_state="independently_source_verified", identity=101,
               namespace="synthetic_dsp", zone_id=77)
    with pytest.raises(ValueError, match="pinned"):
        validate_spec(spec)
    pinned_source(spec)
    assert validate_spec(spec) is spec
    assert compatibility_report(spec)["independent_verification"] == "NOT_ESTABLISHED"
    par["zone_id"] = None
    with pytest.raises(ValueError, match="zone scope"):
        validate_spec(spec)


def test_ambiguous_binding_cannot_silently_pick_identity():
    spec = synthetic()
    spec["contract_v2"]["parameters"][0]["identity"] = "synthetic-choice-1"
    with pytest.raises(ValueError, match="ambiguous"):
        validate_spec(spec)
    spec["contract_v2"]["parameters"][0]["binding_state"] = "candidate"
    assert validate_spec(spec)


def test_unresolved_cannot_pick_identity_even_if_source_exists():
    spec = synthetic()
    par = spec["contract_v2"]["parameters"][0]
    par["binding_state"] = "unresolved"
    par["identity"] = 123
    with pytest.raises(ValueError, match="unresolved"):
        validate_spec(spec)


@pytest.mark.parametrize("field,value", [
    ("kind", "packet"), ("binding_state", "approved_for_execution"),
    ("kind", ["npc"]), ("namespace", "../fake"), ("zone_id", -1),
    ("identity", True),
])
def test_invalid_parameter_typing_or_status_is_rejected(field, value):
    spec = synthetic()
    spec["contract_v2"]["parameters"][0][field] = value
    with pytest.raises(ValueError):
        validate_spec(spec)


@pytest.mark.parametrize("field,value", [
    ("path", "../relative_escape.lua"), ("path", "C:/absolute.lua"),
    ("path", "/absolute.lua"), ("line_start", -2),
    ("line_end", False), ("revision", "not-a-commit"),
    ("sha256", "not-a-content-digest"), ("classification", "operator_verified"),
    ("classification", ["dsp_source"]),
])
def test_invalid_source_provenance_is_rejected(field, value):
    spec = synthetic()
    spec["contract_v2"]["sources"][0][field] = value
    with pytest.raises(ValueError):
        validate_spec(spec)


def test_source_cited_oracle_requires_pinned_normative_source():
    spec = synthetic()
    oracle = spec["contract_v2"]["oracles"][0]
    oracle.update(oracle_type="source_rule", confidence="source_cited",
                  source_refs=["synthetic-source-1"])
    with pytest.raises(ValueError, match="pinned normative"):
        validate_spec(spec)
    pinned_source(spec)
    assert validate_spec(spec)
    spec["contract_v2"]["sources"][0]["classification"] = "capture_observation"
    with pytest.raises(ValueError, match="normative code source"):
        validate_spec(spec)




def test_capture_only_sources_can_never_become_normative_expected_oracle():
    """Even a plausible captured PASS is not independent normative source."""
    spec = synthetic()
    pinned_source(spec)
    spec["contract_v2"]["sources"][0]["classification"] = "capture_observation"
    oracle = spec["contract_v2"]["oracles"][0]
    oracle.update(oracle_type="source_rule", confidence="candidate",
                  source_refs=["synthetic-source-1"])
    with pytest.raises(ValueError, match="normative code source"):
        validate_spec(spec)

def test_unknown_oracle_refuses_verified_confidence_or_attached_sources():
    spec = synthetic()
    spec["contract_v2"]["oracles"][0]["confidence"] = "source_cited"
    with pytest.raises(ValueError, match="unknown v2 oracle"):
        validate_spec(spec)
    spec = synthetic()
    spec["contract_v2"]["oracles"][0]["source_refs"] = ["synthetic-source-1"]
    with pytest.raises(ValueError, match="unknown v2 oracle"):
        validate_spec(spec)


def test_oracle_and_step_references_must_exist_in_v1():
    spec = synthetic()
    spec["contract_v2"]["oracles"][0]["assertion_id"] = "imaginary_oracle"
    with pytest.raises(ValueError, match="oracle assertion"):
        validate_spec(spec)
    spec = synthetic()
    spec["contract_v2"]["step_requirements"][0]["step_id"] = "unknown-step"
    with pytest.raises(ValueError, match="step reference"):
        validate_spec(spec)
    spec = synthetic()
    spec["contract_v2"]["parameters"][0]["source_refs"] = ["invented-source"]
    with pytest.raises(ValueError, match="source reference"):
        validate_spec(spec)


def test_unknown_or_prohibited_capabilities_cannot_be_declared_executable():
    spec = synthetic()
    req = spec["contract_v2"]["step_requirements"][0]
    for dangerous in ("sql_execute", "packet_injection", "shell", "warp"):
        req["capability"] = dangerous
        with pytest.raises(ValueError, match="capability"):
            validate_spec(spec)
    req["capability"] = "client_action_candidate"
    for gate in ("ready", "approved", True):
        req["execution_gate"] = gate
        with pytest.raises(ValueError, match="cannot authorize"):
            validate_spec(spec)


def test_mutation_must_be_approved_isolated_and_cleaned_even_in_metadata():
    spec = synthetic()
    req = spec["contract_v2"]["step_requirements"][0]
    req["approval_required"] = False
    with pytest.raises(ValueError, match="mutating"):
        validate_spec(spec)
    req["approval_required"] = True
    req["required_permissions"] = ["operator_approval"]
    with pytest.raises(ValueError, match="mutating"):
        validate_spec(spec)
    req["required_permissions"] = [
        "operator_approval", "disposable_character", "cleanup_verification"
    ]
    assert validate_spec(spec)


def test_unverified_client_and_gm_commands_cannot_claim_read_only():
    spec = synthetic()
    req = spec["contract_v2"]["step_requirements"][0]
    for capability in ("gm_diagnostic_candidate", "gm_action_candidate",
                       "client_action_candidate"):
        req["capability"] = capability
        req["operation_class"] = "read_only"
        with pytest.raises(ValueError, match="cannot assert read-only"):
            validate_spec(spec)


def test_unchanged_v1_keys_reject_unrecognized_metadata_and_bad_outer_version():
    spec = synthetic()
    spec["contract_v2"]["magic_script"] = "unsafe"
    with pytest.raises(ValueError, match="contract fields"):
        validate_spec(spec)
    spec = synthetic()
    spec["schema_version"] = 2
    with pytest.raises(ValueError, match="unsupported test specification version"):
        validate_spec(spec)
    spec = synthetic()
    spec["contract_v2"]["contract_version"] = 3
    with pytest.raises(ValueError, match="unsupported v2"):
        validate_spec(spec)


def test_revision_compatibility_is_structural_only_and_fail_closed():
    spec = synthetic()
    fp = spec["contract_v2"]["fingerprints"]
    fp["base_spec_sha256"] = base_spec_sha256(spec)
    pins = {"dsp_commit": "a"*40, "headless_commit": "b"*40,
            "toolkit_commit": "c"*40}
    fp.update(pins)
    assert compatibility_report(spec)["state"] == "UNKNOWN"  # runtime not supplied
    assert compatibility_report(spec, pins)["state"] == "UNKNOWN"  # cited source not independently rehashed
    pinned_source(spec)  # explicitly synthetic SHA/revision, not actual DSP bytes
    source_pins = {"synthetic-source-1": {"revision": "a"*40, "sha256": "b"*64}}
    ok = compatibility_report(spec, pins, observed_sources=source_pins)
    assert ok["state"] == "MATCHED_PINNED_ONLY"
    assert not ok["execution_enabled"]
    assert ok["independent_verification"] == "NOT_ESTABLISHED"
    bad = dict(pins, headless_commit="f"*40)
    assert compatibility_report(spec, bad)["state"] == "BLOCKED"
    fp["base_spec_sha256"] = "d"*64
    assert compatibility_report(spec, pins)["state"] == "BLOCKED"
    fp["base_spec_sha256"] = None
    assert compatibility_report(spec, pins)["state"] == "UNKNOWN"


def test_optional_metadata_change_does_not_change_base_spec_fingerprint():
    spec = synthetic()
    before = base_spec_sha256(spec)
    spec["contract_v2"]["parameters"][0]["binding_state"] = "unresolved"
    spec["contract_v2"]["step_requirements"][0]["required_readbacks"].append("synthetic_extra_gap")
    assert base_spec_sha256(spec) == before


def test_json_import_does_not_silently_drop_duplicate_metadata_keys():
    spec = synthetic()
    body = serialize_spec(spec)
    with pytest.raises(ValueError, match="duplicate JSON key"):
        deserialize_spec(body.replace('"contract_version":2', '"contract_version":2,"contract_version":3'))
    with pytest.raises(ValueError, match="oversized"):
        deserialize_spec(" " * 32769)


def test_legacy_editor_and_viewer_still_reject_missing_evidence_as_unknown():
    before = copy.deepcopy(specification("inventory_observation", "INV-OBS-01"))
    assert scenario_presentation(before)["independent_verification"] == "NOT_ESTABLISHED"
    assert scenario_presentation(before)["recalculated_verdict"] is None
    assert validate_spec(before) is before
    from workbench.server_admin.feature_testing.assertion_engine import evaluate
    outcome = evaluate(before, {})
    assert outcome["verdict"] == "BLOCKED"
