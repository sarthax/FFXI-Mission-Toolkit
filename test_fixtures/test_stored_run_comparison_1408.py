"""#1408: the importer records what a later run comparison needs, and the comparison uses only that. Offline only.

The recorded MOG-09 reports are the real receipts from the disposable test characters; every other record here is
SYNTHETIC. Nothing is executed and no verdict is attributed to a change.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing import importer, results, test_specifications
from workbench.server_admin.feature_testing.scenario_contract_v2 import base_spec_sha256
from workbench.server_admin.feature_testing.stored_run_comparison import compare_stored_runs, comparison_context

RECORDED = Path(__file__).parent / "results_v2_recorded"
FAIL = RECORDED / "mog09_fail_obs-20261021T025326Z.report.json"
PASS = RECORDED / "mog09_pass_obs-20261021T040036Z.report.json"
CATALOG = Path(__file__).resolve().parents[1] / "data/testing/feature_test_readiness.json"


def variant(source, tmp_path, name, run_id, dsp=None, **evidence_extra):
    """A copy of a recorded report with a new run id (and optionally a new DSP commit and runner-supplied context)."""
    report = json.loads(source.read_text(encoding="utf-8"))
    for row in report["results"]:
        row["run_id"] = run_id
        if dsp:
            row["dsp_commit"] = dsp
        row["evidence"].update(evidence_extra)
    path = tmp_path / name
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def load(db, path):
    assert importer.import_report(db, CATALOG, path) == 1


def stored(db, run_id):
    return results.results_for_run(db, run_id)[0]


# --- what the importer records -------------------------------------------------------------------------------------

def test_importer_records_the_definition_fingerprint_and_a_record_hash(tmp_path):
    db = tmp_path / "r.sqlite"
    load(db, FAIL)
    ctx = stored(db, "obs-20261021T025326Z")["evidence"]["import_context"]
    spec = test_specifications.specification("moghancement", "MOG-09")
    assert ctx["version"] == 1 and ctx["report_schema_version"] == 1
    assert ctx["definition_sha256"] == base_spec_sha256(spec)
    record = json.loads(FAIL.read_text(encoding="utf-8"))["results"][0]
    expected = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                                         allow_nan=False).encode("utf-8")).hexdigest()
    assert ctx["record_sha256"] == expected  # the stored row can be checked against the report it came from


def test_the_report_cannot_supply_or_corrupt_its_own_context(tmp_path):
    db = tmp_path / "r.sqlite"
    spoof = variant(FAIL, tmp_path, "spoof.json", "x1", import_context={"definition_sha256": "0" * 64})
    with pytest.raises(ValueError, match="reserved"):
        importer.import_report(db, CATALOG, spoof)
    for bad in ("", "   ", "x" * 257, 5, ["a"]):
        with pytest.raises(ValueError, match="environment_fingerprint"):
            importer.import_report(db, CATALOG, variant(FAIL, tmp_path, "bad.json", "x2", environment_fingerprint=bad))
    with pytest.raises(ValueError, match="fixture_context"):
        importer.import_report(db, CATALOG, variant(FAIL, tmp_path, "bad2.json", "x3", fixture_context=""))
    assert results.recent_results(db) == []  # nothing was written by any refusal


def test_existing_evidence_is_kept_beside_the_context(tmp_path):
    db = tmp_path / "r.sqlite"
    load(db, PASS)
    evidence = stored(db, "obs-20261021T040036Z")["evidence"]
    original = json.loads(PASS.read_text(encoding="utf-8"))["results"][0]["evidence"]
    assert {k: v for k, v in evidence.items() if k != "import_context"} == original


# --- comparing stored runs -----------------------------------------------------------------------------------------

def test_the_two_real_receipts_are_not_a_revision_comparison(tmp_path):
    """FAIL then PASS on the same character an hour apart used the same DSP commit and supplied no environment."""
    db = tmp_path / "r.sqlite"
    load(db, FAIL)
    load(db, PASS)
    out = compare_stored_runs(db, "obs-20261021T025326Z", "obs-20261021T040036Z")
    row = out["comparisons"][0]
    assert row["comparable"] is False and row["transition"] == "NOT_COMPARABLE"
    assert row["reasons"] == ["ENVIRONMENT_FINGERPRINT_MISSING", "FIXTURE_CONTEXT_MISSING", "SAME_DSP_REVISION"]
    assert "DEFINITION_DIGEST_MISSING" not in row["reasons"] and "SCHEMA_VERSION_MISSING" not in row["reasons"]
    assert out["attribution"] == "NOT_ATTRIBUTED"


def test_with_two_dsp_revisions_and_declared_context_a_change_is_a_candidate_not_a_cause(tmp_path):
    db = tmp_path / "r.sqlite"
    ctx = dict(environment_fingerprint="synthetic-env-1", fixture_context="synthetic-fixture-1")
    load(db, variant(PASS, tmp_path, "a.json", "synthetic-run-a", dsp="a" * 40, **ctx))
    load(db, variant(FAIL, tmp_path, "b.json", "synthetic-run-b", dsp="b" * 40, **ctx))
    row = compare_stored_runs(db, "synthetic-run-a", "synthetic-run-b")["comparisons"][0]
    assert row["comparable"] is True and row["transition"] == "REGRESSION_CANDIDATE"
    assert row["left"]["dsp_commit"] == "a" * 40 and row["right"]["dsp_commit"] == "b" * 40
    back = compare_stored_runs(db, "synthetic-run-b", "synthetic-run-a")["comparisons"][0]
    assert back["transition"] == "FIXED_CANDIDATE"


def test_a_changed_definition_is_not_comparable(tmp_path, monkeypatch):
    db = tmp_path / "r.sqlite"
    ctx = dict(environment_fingerprint="synthetic-env-1", fixture_context="synthetic-fixture-1")
    load(db, variant(PASS, tmp_path, "a.json", "synthetic-run-a", dsp="a" * 40, **ctx))
    real = test_specifications.specification
    def edited(feature_id, case_id):
        spec = copy.deepcopy(real(feature_id, case_id))
        spec["purpose"] = spec["purpose"] + " (edited after the first import)"
        return spec
    monkeypatch.setattr(test_specifications, "specification", edited)
    load(db, variant(FAIL, tmp_path, "b.json", "synthetic-run-b", dsp="b" * 40, **ctx))
    row = compare_stored_runs(db, "synthetic-run-a", "synthetic-run-b")["comparisons"][0]
    assert row["comparable"] is False and "DEFINITION_CHANGED" in row["reasons"]


def test_different_environment_or_fixture_is_not_comparable(tmp_path):
    db = tmp_path / "r.sqlite"
    load(db, variant(PASS, tmp_path, "a.json", "ra", dsp="a" * 40, environment_fingerprint="env-1", fixture_context="fx-1"))
    load(db, variant(FAIL, tmp_path, "b.json", "rb", dsp="b" * 40, environment_fingerprint="env-2", fixture_context="fx-2"))
    reasons = compare_stored_runs(db, "ra", "rb")["comparisons"][0]["reasons"]
    assert reasons == ["ENVIRONMENT_MISMATCH", "FIXTURE_CONTEXT_MISMATCH"]


def test_rows_imported_before_this_change_are_reported_as_missing_not_guessed(tmp_path):
    db = tmp_path / "r.sqlite"
    for run, dsp, verdict in (("old-a", "a" * 40, "FAIL"), ("old-b", "b" * 40, "UNKNOWN")):
        results.append_result(db, dict(run_id=run, feature_id="gardening", case_id="GRD-01", stage="behavior",
                                       verdict=verdict, observed_at="2026-10-28T01:00:00Z", dsp_commit=dsp,
                                       headless_commit="c" * 40, toolkit_commit="d" * 40, evidence={"summary": "synthetic"}))
    reasons = compare_stored_runs(db, "old-a", "old-b")["comparisons"][0]["reasons"]
    assert {"DEFINITION_DIGEST_MISSING", "SCHEMA_VERSION_MISSING", "ENVIRONMENT_FINGERPRINT_MISSING",
            "FIXTURE_CONTEXT_MISSING"} <= set(reasons)


def test_context_leaves_out_anything_missing_or_inconsistent_across_a_runs_rows():
    def rec(case, env, digest="f" * 64, version=1):
        evidence = {"import_context": {"definition_sha256": digest, "report_schema_version": version}}
        if env is not None:
            evidence["environment_fingerprint"] = env
        return {"feature_id": "gardening", "case_id": case, "evidence": evidence}
    assert comparison_context([rec("A", "e1"), rec("B", "e1")]) == {
        "definition_sha256": {"gardening/A": "f" * 64, "gardening/B": "f" * 64}, "schema_version": 1,
        "environment_fingerprint": "e1"}
    assert "environment_fingerprint" not in comparison_context([rec("A", "e1"), rec("B", "e2")])  # conflict
    assert "environment_fingerprint" not in comparison_context([rec("A", "e1"), rec("B", None)])  # one row silent
    assert "schema_version" not in comparison_context([rec("A", "e1", version=1), rec("B", "e1", version=2)])
    assert comparison_context([{"feature_id": "g", "case_id": "A", "evidence": {}}]) == {}


def test_a_missing_run_is_refused(tmp_path):
    db = tmp_path / "r.sqlite"
    load(db, FAIL)
    with pytest.raises(ValueError, match="both runs"):
        compare_stored_runs(db, "obs-20261021T025326Z", "nope")
