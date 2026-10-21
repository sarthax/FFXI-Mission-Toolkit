"""Synthetic coverage matrix regression tests — NO real client/server evidence."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from workbench.server_admin.scenario_coverage.matrix import (
    build_matrix, filter_matrix, spec_digest,
)


def fixture_case(case_id: str, kind: str = "positive") -> dict:
    return {"id": case_id, "title": "SYNTHETIC " + case_id,
            "kind": kind, "status": "planned", "run_mode": "local_read_only_observation",
            "blocking_gaps": []}


def fixture_spec(case_id: str) -> dict:
    # Synthetic projection contract, not part of the canonical scenario catalog.
    return {"schema_version": 1, "case_id": case_id, "feature_id": "synthetic-domain",
            "name": "SYNTHETIC " + case_id, "runner": "fixture_only",
            "execution_status": "verified_runner", "observations": ["synthetic"],
            "preconditions": ["fixture only"], "cleanup": ["fixture only"],
            "assertions": [{"id": "synthetic_check", "operation": "equals",
                            "observed": "synthetic", "expected": "synthetic"}]}


def fixture_record(spec: dict, verdict: str = "PASS", *,
                   digest: str | None = None, run_id: str = "synthetic-run") -> dict:
    return {"feature_id": spec["feature_id"], "case_id": spec["case_id"],
            "run_id": run_id, "observed_at": "2026-01-01T00:00:00Z",
            "stage": "behavior", "verdict": verdict, "dsp_commit": "synthetic-dsp",
            "headless_commit": "synthetic-headless", "toolkit_commit": "synthetic-toolkit",
            "evidence": {"spec_digest": digest if digest is not None else spec_digest(spec),
                         "claimed_independently_verified": True}}


def source_oracle(spec: dict, *, complete: bool = False) -> dict:
    # An external trusted assessment is injected only by tests; the web route
    # never receives or passes this object and never trusts evidence_json.
    return {"spec_digest": spec_digest(spec), "oracle": True, "readback": True,
            "independent_run": complete, "complete": complete}


def view(cases: list, specs: list, results: list | None = None, *, trusted=None,
         feature_gaps=None, history_complete: bool = True) -> dict:
    catalog = {"schema_version": 1, "features": [{
        "id": "synthetic-domain", "name": "Synthetic domain",
        "cases": cases, "gaps": feature_gaps or []
    }]}
    return build_matrix(catalog, specs, results or [], [], trusted_assessments=trusted,
                        history_complete=history_complete)


def feature(matrix: dict) -> dict:
    return matrix["features"][0]


def test_synthetic_complete_requires_all_four_verified_categories():
    kinds = ("positive", "negative", "boundary", "persistence")
    cases = [fixture_case("SYNTH-" + str(i), cat) for i, cat in enumerate(kinds)]
    specs = [fixture_spec(c["id"]) for c in cases]
    records = [fixture_record(s) for s in specs]
    trust = {(s["feature_id"], s["case_id"]): source_oracle(s, complete=True) for s in specs}
    matrix = view(cases, specs, records, trusted=trust)
    f = feature(matrix)
    assert f["state"] == "complete"
    assert sum(x["independent"] for x in f["categories"].values()) == 4
    assert all(x["state"] == "complete" for x in f["cases"])
    assert all(x["recalculated"]["verdict"] == "UNKNOWN" for x in f["cases"])
    assert all("percent" not in k for k in matrix)


def test_synthetic_partial_shows_unverified_coverage_without_inflation():
    cases = [fixture_case("SYNTH-1", "positive"), fixture_case("SYNTH-2", "negative")]
    specs = [fixture_spec(x["id"]) for x in cases]
    runs = [fixture_record(s) for s in specs]
    trust = {("synthetic-domain", "SYNTH-1"): source_oracle(specs[0], complete=True)}
    f = feature(view(cases, specs, runs, trusted=trust))
    assert f["state"] == "partial"
    assert [c["state"] for c in f["cases"]] == ["complete", "blocked"]
    assert f["categories"]["negative"]["recorded"] == 1
    assert f["categories"]["negative"]["independent"] == 0
    assert f["cases"][1]["recorded"]["verdict"] == "PASS"
    assert f["cases"][1]["independent_confidence"] == "UNVERIFIED"
    assert f["cases"][1]["oracle"] == "UNKNOWN"


def test_synthetic_untested_keeps_source_oracle_distinct_from_execution():
    case = fixture_case("SYNTH-PERSIST", "persistence")
    spec = fixture_spec(case["id"])
    f = feature(view([case], [spec], trusted={("synthetic-domain", case["id"]): source_oracle(spec)}))
    assert f["state"] == "untested"
    assert f["cases"][0]["recorded"] is None
    assert f["cases"][0]["recalculated"]["verdict"] == "UNKNOWN"
    assert f["cases"][0]["oracle"] == "SOURCE_VERIFIED"


def test_synthetic_blocked_planned_spec_and_imported_pass():
    case = fixture_case("SYNTH-BLOCK", "boundary")
    spec = fixture_spec(case["id"])
    rec = fixture_record(spec)
    result = view([case], [spec], [rec])
    row = feature(result)["cases"][0]
    assert feature(result)["state"] == "blocked"
    assert row["recorded"]["verdict"] == "PASS"
    assert row["recalculated"]["verdict"] == "UNKNOWN"
    assert row["independent_confidence"] == "UNVERIFIED"
    assert "oracle" in " ".join(row["gaps"]).lower()
    assert result["execution_enabled"] is False


def test_missing_spec_does_not_count_planned_as_specified():
    case = fixture_case("SYNTH-PLANNED")
    f = feature(view([case], []))
    assert f["state"] == "blocked"
    assert f["categories"]["positive"] == {
        "planned": 1, "specified": 0, "recorded": 0, "independent": 0}
    assert "No canonical scenario specification" in f["cases"][0]["gaps"]


def test_version_mismatch_blocks_even_trusted_looking_imported_pass():
    case = fixture_case("SYNTH-MISMATCH")
    spec = fixture_spec(case["id"])
    rec = fixture_record(spec, digest="not-current-digest")
    trust = {("synthetic-domain", case["id"]): source_oracle(spec, complete=True)}
    row = feature(view([case], [spec], [rec], trusted=trust))["cases"][0]
    assert row["version_comparison"] == "VERSION_MISMATCH"
    assert row["recorded"]["verdict"] == "PASS"
    assert row["recalculated"]["verdict"] == "UNKNOWN"
    assert row["state"] == "blocked"
    assert row["independent_confidence"] == "UNVERIFIED"


def test_missing_digest_never_claims_comparable_recalculated_result():
    case = fixture_case("SYNTH-UNPINNED")
    spec = fixture_spec(case["id"])
    rec = fixture_record(spec)
    del rec["evidence"]["spec_digest"]
    row = feature(view([case], [spec], [rec]))["cases"][0]
    assert row["version_comparison"] == "REVISION_UNPINNED"
    assert row["recalculated"]["verdict"] == "UNKNOWN"
    assert row["state"] == "blocked"


def test_misleading_positive_missing_oracle_and_readback_remains_blocked():
    case = fixture_case("SYNTH-MISLEADING")
    spec = fixture_spec(case["id"])
    rec = fixture_record(spec)
    rec["evidence"].update({
        "independently_verified": True,
        "oracle_verified": True,
        "readback_complete": True,
        "recorded_verdict": "PASS",
    })
    row = feature(view([case], [spec], [rec]))["cases"][0]
    assert row["recorded"]["verdict"] == "PASS"
    assert row["oracle"] == "UNKNOWN"
    assert row["readback"] == "UNKNOWN"
    assert row["independent_confidence"] == "UNVERIFIED"
    assert row["state"] == "blocked"


def test_incomplete_history_fails_closed():
    case = fixture_case("SYNTH-TRUNC")
    spec = fixture_spec(case["id"])
    rec = fixture_record(spec)
    trust = {("synthetic-domain", case["id"]): source_oracle(spec, complete=True)}
    row = feature(view([case], [spec], [rec], trusted=trust, history_complete=False))["cases"][0]
    assert row["state"] == "blocked"
    assert any("truncated" in x for x in row["gaps"])


def test_conflicting_stage_rows_cannot_roll_up_to_pass():
    case = fixture_case("SYNTH-STAGE")
    spec = fixture_spec(case["id"])
    pass_row = fixture_record(spec, "PASS")
    fail_row = fixture_record(spec, "FAIL")
    fail_row["stage"] = "mechanics"
    row = feature(view([case], [spec], [pass_row, fail_row]))["cases"][0]
    assert row["recorded"]["verdict"] == "FAIL"
    assert len(row["recorded"]["stage_verdicts"]) == 2


def test_orphans_are_visible_not_assumed_linked():
    source = fixture_spec("SYNTH-NO-READINESS")
    result = view([], [source], [fixture_record(source)])
    assert result["orphan_specifications"] == [
        {"feature_id": "synthetic-domain", "case_id": "SYNTH-NO-READINESS"}]
    assert result["orphan_evidence"] == result["orphan_specifications"]


def test_domain_state_filters_reject_unknown_values():
    matrix = view([fixture_case("SYNTH-FILTER")], [])
    assert len(filter_matrix(matrix, domain="synthetic-domain", readiness="blocked")["features"]) == 1
    assert filter_matrix(matrix, readiness="complete")["features"] == []
    with pytest.raises(ValueError):
        filter_matrix(matrix, domain="unknown domain")
    with pytest.raises(ValueError):
        filter_matrix(matrix, readiness="PASS")


def test_deterministic_html_preserves_separate_verdict_provenance():
    case = fixture_case("SYNTH-HTML")
    spec = fixture_spec(case["id"])
    row = view([case], [spec], [fixture_record(spec)])
    matrix = filter_matrix(row)
    root = Path(__file__).resolve().parents[1] / "gui" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html"]))
    env.globals["current_theme"] = lambda: "light"
    env.globals["shell_context"] = lambda request=None: {}
    rendered = env.get_template("feature_testing_coverage.html").render(matrix=matrix)
    assert 'data-feature="synthetic-domain"' in rendered
    assert "PASS (imported, unverified)" in rendered
    assert "Recalculated verdict" in rendered
    assert "UNKNOWN" in rendered
    assert 'action="/feature-testing/coverage"' in rendered
    assert "/feature-testing/scenario/synthetic-domain/SYNTH-HTML" in rendered
    assert "/feature-testing/run/synthetic-run" in rendered
    assert "No percentages" in rendered
    assert "independently verified case(s)" in rendered
    intro = rendered.lower().split('<section class="cov-intro">')[1].split("</section>")[0]
    assert "<script" not in intro


def test_same_run_conflicting_revision_across_stages_is_blocked():
    case = fixture_case("SYNTH-CROSS-STAGE")
    spec = fixture_spec(case["id"])
    rows = [fixture_record(spec), fixture_record(spec)]
    rows[1]["stage"] = "mechanics"
    rows[1]["headless_commit"] = "different-synthetic-build"
    trust = {("synthetic-domain", case["id"]): source_oracle(spec, complete=True)}
    row = feature(view([case], [spec], rows, trusted=trust))["cases"][0]
    assert row["version_comparison"] == "VERSION_MISMATCH"
    assert row["recorded"]["verdict"] == "PASS"
    assert row["recalculated"]["verdict"] == "UNKNOWN"
    assert row["state"] == "blocked"


def test_same_run_one_stage_missing_spec_digest_is_unpinned():
    case = fixture_case("SYNTH-MIXED-STAGE")
    spec = fixture_spec(case["id"])
    rows = [fixture_record(spec), fixture_record(spec)]
    rows[1]["stage"] = "mechanics"
    del rows[1]["evidence"]["spec_digest"]
    row = feature(view([case], [spec], rows))["cases"][0]
    assert row["version_comparison"] == "REVISION_UNPINNED"
    assert row["recalculated"]["verdict"] == "UNKNOWN"
