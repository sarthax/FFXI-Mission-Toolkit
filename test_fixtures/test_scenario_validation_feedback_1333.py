"""#1333 field-specific error feedback; canonical validation remains authoritative."""
from copy import deepcopy

import pytest
from fastapi import HTTPException

from workbench.server_admin.scenario_authoring import editor_router
from workbench.server_admin.scenario_authoring.validation_feedback import field_errors


def _valid():
    return {
        "schema_version": 1, "feature_id": "moghancement",
        "case_id": "SYNTH-VALIDATION-ERR-01",
        "name": "Synthetic draft", "runner": "unassigned",
        "execution_status": "design_only",
        "preconditions": ["synthetic input"], "observations": ["client_bag"],
        "assertions": [{"id": "a1", "operation": "nonempty",
                        "observed": "client_bag", "expected": None}],
        "cleanup": ["no action"],
        "purpose": "Observe synthetic inventory", "rationale": "Synthetic test only",
        "behavior": {"given": ["synthetic precondition"],
                     "when": ["read only"], "then": ["record unknown"]},
        "steps": [{"id": "SYNTH-STEP-1", "title": "Observation",
                   "intent": "observation", "expected": "UNKNOWN",
                   "assertion_ids": ["a1"], "evidence_refs": ["client_bag"]}],
        "authoring": {"state": "draft", "execution_policy": "read_only",
                      "evidence_provenance": "synthetic_unverified",
                      "blocking_gaps": ["Needs independent oracle"],
                      "review_required": True},
    }


def test_valid_draft_still_uses_original_canonical_validator():
    s = _valid()
    out = editor_router.validate_editor_spec(deepcopy(s))
    assert out["canonical_specification"] == s
    assert out["execution_enabled"] is False


def test_three_independent_field_errors_with_no_input_normalization(monkeypatch):
    s = _valid()
    s["purpose"] = ""
    s["behavior"]["given"] = []
    del s["authoring"]["review_required"]
    original = deepcopy(s)
    with pytest.raises(ValueError, match="invalid purpose"):
        editor_router.validate_editor_spec(s)
    problems = field_errors(s, "invalid purpose")
    assert s == original
    locations = {p["field"]: p for p in problems}
    assert {"purpose", "behavior.given", "authoring"} <= set(locations)
    assert locations["purpose"]["control_id"] == "sd-purpose"
    assert locations["behavior.given"]["required"] is True
    assert locations["authoring"]["control_id"] == "sd-advanced-json"
    assert len(problems) <= 12


def test_endpoint_422_preserves_canonical_failure_and_multiple_field_locations(monkeypatch):
    monkeypatch.setattr(editor_router, "_local_origin", lambda req: None)
    s = _valid()
    s["purpose"] = ""
    s["behavior"]["given"] = []
    s["authoring"] = {"state": "draft"}
    original = deepcopy(s)
    body = editor_router.ValidationRequest(specification=s)
    with pytest.raises(HTTPException) as err:
        editor_router.validate(object(), body)
    assert err.value.status_code == 422
    detail = err.value.detail
    assert detail["canonical_error"] == "invalid purpose"
    assert detail["message"] == "Canonical scenario validation rejected"
    assert {e["field"] for e in detail["errors"]} >= {
        "purpose", "behavior.given", "authoring"
    }
    assert s == original


@pytest.mark.parametrize("value", [None, 2, "", "a" * 1001])
def test_optional_present_purpose_must_remain_canonical(value):
    s = _valid()
    s["purpose"] = value
    with pytest.raises(ValueError, match="invalid purpose"):
        editor_router.validate_editor_spec(s)
    assert any(e["field"] == "purpose" for e in field_errors(s, "invalid purpose"))


def test_valid_phase_zero_length_and_authoring_mutation_never_accepted():
    s = _valid()
    s["behavior"]["then"] = []
    s["authoring"]["execution_policy"] = "mutating"
    field_ids = {e["field"] for e in field_errors(s, "invalid BDD phase: then")}
    assert "behavior.then" in field_ids
    assert "authoring.execution_policy" in field_ids
    with pytest.raises(ValueError, match="invalid BDD phase: then"):
        editor_router.validate_editor_spec(s)


def test_canonical_contract_v2_unknown_error_not_silently_repaired():
    s = _valid()
    s["unknown_field"] = "preserve this until operator corrects it"
    problems = field_errors(s, "unexpected test specification fields")
    assert problems[0]["field"] == "specification"
    with pytest.raises(ValueError, match="unexpected test specification fields"):
        editor_router.validate_editor_spec(s)
    assert "unknown_field" in s


def test_advisory_diagnostics_have_no_execution_or_db_side_effects(monkeypatch):
    import sqlite3
    import subprocess

    def forbidden(*args, **kwargs):
        raise AssertionError("diagnostic unexpectedly attempted IO")
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    s = _valid()
    s["purpose"] = ""
    issues = field_errors(s, "invalid purpose")
    assert issues and all(set(x) == {"field", "control_id", "message", "required"} for x in issues)
    assert field_errors(s, "invalid purpose") == issues


def test_operator_token_denial_remains_uniform_and_does_not_disclose_configuration(monkeypatch):
    from workbench.server_admin.feature_testing.execution_jobs import authorize_operator

    errors = []
    for configured, presented in ((None, None), ("too-short", "too-short"),
                                  ("s" * 40, "wrong")):
        if configured is None:
            monkeypatch.delenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", raising=False)
        else:
            monkeypatch.setenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", configured)
        with pytest.raises(PermissionError) as err:
            authorize_operator(presented)
        errors.append(str(err.value))
    assert len(set(errors)) == 1
    assert "configured" not in errors[0].lower()
    assert "short" not in errors[0].lower()
    assert "wrong" not in errors[0].lower()
