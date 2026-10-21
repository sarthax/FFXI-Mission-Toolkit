"""SYNTHETIC, offline coverage-driven authoring tests; no real FFXI IDs.

These fixtures are intentionally invented TEST IDS, not gameplay identities.
They exercise the existing matrix plus the new read-only context projection.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from workbench.server_admin.scenario_coverage.matrix import build_matrix, filter_matrix, spec_digest
from workbench.server_admin.scenario_coverage.authoring import (
    REVIEW_CATEGORIES, add_behavior_drilldown, draft_context,
)


def case(name: str, kind: str = "positive", *, run_mode: str = "local_read_only_observation") -> dict:
    return {
        "id": name, "title": "SYNTHETIC intent for " + name,
        "kind": kind, "status": "planned", "run_mode": run_mode,
        "blocking_gaps": [], "evidence_required": ["synthetic_provenance"],
    }


def spec(cid: str, *, observations: list[str] | None = None,
         status: str = "verified_runner") -> dict:
    # Not a canonical spec — projection-only synthetic fixture.
    return {
        "schema_version": 1, "feature_id": "synthetic-domain",
        "case_id": cid, "name": "SYNTHETIC " + cid,
        "runner": "synthetic_runner", "execution_status": status,
        "preconditions": ["synthetic only"], "cleanup": ["synthetic only"],
        "observations": ["session"] if observations is None else observations,
        "assertions": [{"id": "synthetic_assertion", "operation": "equals",
                        "observed": "session", "expected": "synthetic"}],
    }


def record(s: dict, *, verdict: str = "PASS", stage: str = "behavior",
           headless: str = "synthetic-h1", digest: str | None = None,
           run_id: str = "synthetic-run") -> dict:
    return {
        "feature_id": s["feature_id"], "case_id": s["case_id"],
        "run_id": run_id, "observed_at": "2026-01-01T01:00:00Z",
        "stage": stage, "verdict": verdict,
        "dsp_commit": "synthetic-dsp", "headless_commit": headless,
        "toolkit_commit": "synthetic-toolkit",
        "evidence": {"spec_digest": digest if digest is not None else spec_digest(s)},
    }


def oracle(s: dict) -> dict:
    # Only injected into the pure projection in synthetic tests.
    return {
        "spec_digest": spec_digest(s), "oracle": True, "readback": True,
        "independent_run": True, "complete": True,
    }


def project(cases: list[dict], specs: list[dict],
            records: list[dict] | None = None, *, trusted=None) -> dict:
    readiness = {
        "schema_version": 1, "features": [{
            "id": "synthetic-domain", "name": "Synthetic behavior domain",
            "headless_candidates": ["synthetic_observer"], "gaps": [],
            "cases": cases,
        }]
    }
    imported = records or []
    baseline = build_matrix(readiness, specs, imported, [], trusted_assessments=trusted)
    enhanced = add_behavior_drilldown(baseline, readiness, specs, imported)
    return enhanced


def behavior(model: dict, index: int = 0) -> dict:
    return model["features"][0]["behavior_drilldown"][index]


def test_complete_trusted_synthetic_behavior_remains_verified_not_automatically_executable():
    s = spec("SYNTH-VERIFIED")
    model = project([case(s["case_id"])], [s], [record(s)],
                    trusted={(s["feature_id"], s["case_id"]): oracle(s)})
    row = behavior(model)
    assert model["features"][0]["state"] == "complete"
    assert row["coverage_status"] == "VERIFIED"
    assert row["verified"] is True
    assert row["executable"] == "NOT_ESTABLISHED_LOCAL_PREFLIGHT_REQUIRED"
    assert row["observed"] == "IMPORTED_UNVERIFIED"
    assert model["execution_enabled"] is False


def test_planned_without_spec_is_uncovered_source_intent():
    model = project([case("SYNTH-PLANNED", "negative")], [])
    row = behavior(model)
    assert row["coverage_status"] == "DECLARED_UNSPECIFIED"
    assert row["planned"] and not row["specified"] and not row["verified"]
    assert row["executable"] == "BLOCKED_NO_SPECIFICATION"
    assert row["observed"] == "NOT_OBSERVED"
    assert row["oracle_status"] == "UNKNOWN"
    assert row["editor_url"].startswith("/scenario-developer?context_ref=")
    assert "SYNTH-PLANNED" in row["context_url"]


def test_unsupported_execution_capability_and_observation_not_assumed_available():
    c = case("SYNTH-BLOCKED", "boundary",
             run_mode="blocked_pending_verified_server_command_and_assertions")
    s = spec(c["id"], observations=["synthetic_unknown_vision"])
    row = behavior(project([c], [s]))
    assert row["executable"] == "BLOCKED_UNSUPPORTED_OBSERVATION"
    assert row["unsupported_observations"] == ["synthetic_unknown_vision"]
    assert row["capability_status"] == "UNVERIFIED_CANDIDATES"
    assert row["verified"] is False
    assert row["oracle_status"] == "UNKNOWN"


def test_imported_pass_claim_does_not_upgrade_observed_to_verified():
    s = spec("SYNTH-PASS")
    imported = record(s)
    imported["evidence"].update({"independently_verified": True, "authenticated": True})
    row = behavior(project([case(s["case_id"])], [s], [imported]))
    assert row["coverage_status"] == "IMPORTED_NOT_INDEPENDENT"
    assert row["observed"] == "IMPORTED_UNVERIFIED"
    assert row["observed_verdict"] == "PASS"
    assert row["verified"] is False
    assert row["recalculated_verdict"] == "UNKNOWN"


def test_conflicting_scenario_and_engine_revisions_are_prominent():
    s = spec("SYNTH-MIXED")
    good = record(s)
    conflict = record(s, stage="mechanics", headless="synthetic-h2", digest="synthetic-other")
    row = behavior(project([case(s["case_id"])], [s], [good, conflict]))
    assert row["version_comparison"] == "VERSION_MISMATCH"
    assert row["version_alert"] == "CONFLICTING_OR_STALE_REVISION"
    assert row["recalculated_verdict"] == "UNKNOWN"
    assert row["verified"] is False


def test_historical_engine_changes_are_labeled_not_fabricated_as_conflict():
    s = spec("SYNTH-HISTORY")
    rows = [record(s, run_id="synthetic-a"),
            record(s, run_id="synthetic-b", headless="synthetic-new")]
    row = behavior(project([case(s["case_id"])], [s], rows))
    assert row["version_alert"] == "HISTORICAL_ENGINE_REVISIONS_DIFFER"
    assert row["observed"] == "IMPORTED_UNVERIFIED"


def test_missing_category_slots_include_recovery_without_invented_behavior():
    model = project([case("SYNTH-ONLY-POSITIVE")], [])
    categories = model["features"][0]["category_gaps"]
    assert tuple(item["category"] for item in categories) == REVIEW_CATEGORIES
    assert next(x for x in categories if x["category"] == "recovery")["missing_category"] is True
    assert len(model["features"][0]["behavior_drilldown"]) == 1
    assert all(item["interpretation"] for item in categories)


def test_recovery_source_case_is_preserved_when_it_exists():
    model = project([case("SYNTH-RECOVERY", "recovery")], [])
    assert behavior(model)["category"] == "recovery"
    recovery = next(x for x in model["features"][0]["category_gaps"] if x["category"] == "recovery")
    assert recovery["declared"] == 1 and recovery["missing_category"] is False


def test_draft_context_carries_bounded_source_ref_but_no_autosave_or_assertion():
    model = project([case("SYNTH-UNSPEC", "negative")], [])
    row = behavior(model)
    url = urlsplit(row["editor_url"])
    assert url.path == "/scenario-developer"
    assert parse_qs(url.query)["context_ref"] == [row["context_url"]]
    readiness = {"schema_version": 1, "features": [{
        "id": "synthetic-domain", "cases": [case("SYNTH-UNSPEC", "negative")]}]}
    ctx = draft_context(readiness, "synthetic-domain", "SYNTH-UNSPEC")
    assert ctx["behavior_ref"] == "SYNTH-UNSPEC"
    assert ctx["reference_kind"] == "declared_test_case_intent_not_behavior_trace_identity"
    assert ctx["source"] == "data/testing/feature_test_readiness.json"
    assert ctx["proposed_case_id"] is None
    assert ctx["assertions"] == [] and ctx["observations"] == []
    assert ctx["expected_oracle"] == "UNKNOWN"
    assert ctx["context_only"] and ctx["design_only"] and ctx["review_required"]
    assert not ctx["auto_save_allowed"] and not ctx["auto_populate_allowed"]
    assert not ctx["execution_enabled"]


@pytest.mark.parametrize("feature_ref,behavior_ref", [
    ("synthetic-domain", "UNDECLARED"),
    ("../../etc", "SYNTH-EXISTS"),
    ("synthetic-domain", "../SYNTH-EXISTS"),
    ("synthetic-domain", "x" * 121),
    ("synthetic-domain", "SYNTH-EXISTS?next=/unsafe"),
])
def test_missing_or_unbounded_handoffs_fail_closed(feature_ref, behavior_ref):
    source = {"schema_version": 1, "features": [{
        "id": "synthetic-domain", "cases": [case("SYNTH-EXISTS")]}]}
    with pytest.raises((LookupError, ValueError)):
        draft_context(source, feature_ref, behavior_ref)


def test_existing_matrix_fields_and_filters_are_retained():
    s = spec("SYNTH-KEEP")
    model = project([case(s["case_id"])], [s], [record(s)])
    picked = filter_matrix(model, domain="synthetic-domain", readiness="blocked")
    feature = picked["features"][0]
    assert "cases" in feature and "categories" in feature
    assert "version_comparison" in feature["cases"][0]
    assert "behavior_drilldown" in feature
    assert picked["execution_enabled"] is False


def test_rendered_drilldown_keeps_missing_proofs_and_editor_warning_visible():
    c = case("SYNTH-UNSPEC", "negative")
    matrix = filter_matrix(project([c], []))
    root = Path(__file__).resolve().parents[1] / "gui" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html"]))
    env.globals["current_theme"] = lambda: "light"
    env.globals["shell_context"] = lambda request=None: {}
    rendered = env.get_template("feature_testing_coverage.html").render(matrix=matrix)
    assert 'data-behavior-ref="SYNTH-UNSPEC"' in rendered
    assert "Create scenario for this behavior" in rendered
    assert "unsaved, design-only draft" in rendered
    assert "Recovery — declared 0" in rendered
    assert "NO DECLARED SCENARIO" in rendered
    assert "NO_SPECIFICATION" in rendered
    assert "/scenario-developer?context_ref=" in rendered
    assert "No percentages" not in rendered or "no coverage percentages" in rendered.lower()


def test_rendered_revision_alert_is_never_hidden_by_recorded_pass():
    s = spec("SYNTH-REVISION")
    rows = [record(s), record(s, stage="mechanics", digest="synthetic-mismatch")]
    matrix = filter_matrix(project([case(s["case_id"])], [s], rows))
    root = Path(__file__).resolve().parents[1] / "gui" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html"]))
    env.globals["current_theme"] = lambda: "light"
    env.globals["shell_context"] = lambda request=None: {}
    rendered = env.get_template("feature_testing_coverage.html").render(matrix=matrix)
    assert 'class="cov-revision-alert" role="alert"' in rendered
    assert "CONFLICTING_OR_STALE_REVISION" in rendered
    assert "PASS (imported, unverified)" in rendered
    assert "UNKNOWN" in rendered
