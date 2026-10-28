"""R6 WP4a (#1199): stored UNKNOWN verdict and controlled BLOCKED reason_class. Synthetic data only."""
import json
import sqlite3

import pytest

from workbench.server_admin.feature_testing import results
from workbench.server_admin.feature_testing.importer import import_report, validate_report
from workbench.server_admin.feature_testing.observation_adapter import build_report
from workbench.server_admin.feature_testing.router import dashboard_view
from workbench.server_admin.scenario_coverage.matrix import _latest_record

CATALOG = {"features": [{"id": "feat", "cases": [{"id": f"C{i}"} for i in range(1, 9)]}]}
A, B, C = "a" * 40, "b" * 40, "c" * 40  # format examples only


def row(case, verdict, evidence=None, run="run-1", stage="behavior"):
    return {"run_id": run, "case_id": case, "feature_id": "feat", "stage": stage, "verdict": verdict,
            "observed_at": "2026-10-28T00:00:00Z", "dsp_commit": A, "headless_commit": B,
            "toolkit_commit": C, "evidence": evidence if evidence is not None else {"note": "synthetic"}}


def report(*rows):
    return {"schema_version": 1, "results": list(rows)}


@pytest.mark.parametrize("cls", sorted(results.BLOCK_REASON_CLASSES))
def test_blocked_with_each_reason_class_is_accepted(cls):
    validate_report(report(row("C1", "BLOCKED", {"reason_class": cls})), CATALOG)


def test_blocked_without_or_with_invalid_reason_class_is_rejected():
    with pytest.raises(ValueError, match="BLOCKED requires evidence.reason_class"):
        validate_report(report(row("C1", "BLOCKED")), CATALOG)
    with pytest.raises(ValueError, match="invalid reason_class"):
        validate_report(report(row("C1", "BLOCKED", {"reason_class": "TIMEOUT"})), CATALOG)
    with pytest.raises(ValueError, match="invalid reason_class"):
        validate_report(report(row("C1", "BLOCKED", {"reason_class": "environment"})), CATALOG)  # case-sensitive


def test_unknown_is_accepted_with_or_without_a_class_but_a_bad_class_is_rejected():
    validate_report(report(row("C1", "UNKNOWN"), row("C2", "UNKNOWN", {"reason_class": "ORACLE_UNKNOWN"})), CATALOG)
    with pytest.raises(ValueError, match="invalid reason_class"):
        validate_report(report(row("C1", "UNKNOWN", {"reason_class": "NOPE"})), CATALOG)


def test_reason_class_is_rejected_on_other_verdicts():
    evidence = {"assertions": [], "observations": {}, "reason_class": "OTHER"}
    for verdict in ("PASS", "FAIL", "SKIPPED"):
        with pytest.raises(ValueError, match="only applies to BLOCKED or UNKNOWN"):
            validate_report(report(row("C1", verdict, dict(evidence))), CATALOG)


def test_unknown_never_satisfies_the_pass_evidence_rule_or_becomes_pass():
    validate_report(report(row("C1", "UNKNOWN")), CATALOG)  # no assertions/observations needed...
    with pytest.raises(ValueError, match="PASS requires"):
        validate_report(report(row("C1", "PASS")), CATALOG)  # ...but PASS still needs them


def test_import_round_trip_stores_and_reads_unknown(tmp_path):
    db = tmp_path / "r.sqlite"
    catalog = tmp_path / "c.json"
    catalog.write_text(json.dumps(CATALOG))
    rep = tmp_path / "rep.json"
    rep.write_text(json.dumps(report(row("C1", "UNKNOWN", {"reason_class": "FIXTURE_ABSENT"}),
                                      row("C2", "BLOCKED", {"reason_class": "ENVIRONMENT"}))))
    assert import_report(db, catalog, rep) == 2
    stored = {r["case_id"]: r for r in results.recent_results(db)}
    assert stored["C1"]["verdict"] == "UNKNOWN" and results.reason_class(stored["C1"]) == "FIXTURE_ABSENT"
    assert results.reason_class(stored["C2"]) == "ENVIRONMENT"


def test_historical_blocked_rows_still_load_and_read_as_unclassified(tmp_path):
    db = tmp_path / "old.sqlite"
    results.init_db(db)
    with sqlite3.connect(str(db)) as conn:  # a row written before reason_class existed
        conn.execute("INSERT INTO feature_test_results VALUES (?,?,?,?,?,?,?,?,?,?)",
                     ("old-run", "C1", "feat", "behavior", "BLOCKED", "2026-10-01T00:00:00Z", A, B, C,
                      json.dumps({"reason": "legacy free text"})))
    [record] = results.recent_results(db)
    assert record["verdict"] == "BLOCKED" and results.reason_class(record) == results.UNCLASSIFIED
    assert results.reason_class({"verdict": "PASS", "evidence": {}}) is None
    assert results.reason_class({"verdict": "UNKNOWN", "evidence": {"reason_class": "bogus"}}) == results.UNCLASSIFIED


def test_append_result_validates_reason_class_but_does_not_force_it_on_direct_callers(tmp_path):
    db = tmp_path / "d.sqlite"
    base = {k: v for k, v in row("C1", "BLOCKED").items()}
    results.append_result(db, base)  # direct trusted callers keep working; the importer is the gate
    bad = dict(row("C2", "BLOCKED", {"reason_class": "NOPE"}))
    with pytest.raises(ValueError, match="invalid reason_class"):
        results.append_result(db, bad)
    assert results.reason_class(results.recent_results(db, case_id="C1")[0]) == results.UNCLASSIFIED


def test_unknown_in_a_run_never_becomes_pass_in_the_coverage_matrix():
    def rec(verdict, stage):
        return {"run_id": "r", "observed_at": "2026-10-28T00:00:00Z", "verdict": verdict, "stage": stage}
    assert _latest_record([rec("UNKNOWN", "a")])["verdict"] == "UNKNOWN"
    assert _latest_record([rec("PASS", "a"), rec("UNKNOWN", "b")])["verdict"] == "UNKNOWN"
    assert _latest_record([rec("PASS", "a"), rec("PASS", "b")])["verdict"] == "PASS"
    assert _latest_record([rec("FAIL", "a"), rec("UNKNOWN", "b")])["verdict"] == "FAIL"


def test_observation_adapter_blocked_rows_carry_other_and_pass_the_importer():
    manifest = {"run_id": "r1", "observed_at": "2026-10-28T00:00:00Z",
                "dsp_commit": A, "headless_commit": B, "toolkit_commit": C}
    catalog = {"features": [{"id": "moghancement", "cases": [{"id": "MOG-01"}]}]}
    obs = [{"kind": "mog_modifier", "case_id": "MOG-01", "baseline": {"GILFINDER": 0},
            "active": {"GILFINDER": "x"}, "removed": {"GILFINDER": 0}, "expected_delta": {"GILFINDER": 10}}]
    [out] = build_report(manifest, obs, catalog)["results"]
    assert out["verdict"] == "BLOCKED" and out["evidence"]["reason_class"] == "OTHER"


def test_dashboard_accepts_unknown_as_a_verdict_filter(monkeypatch):
    from workbench.server_admin.feature_testing import router
    monkeypatch.setattr(router, "_history", lambda: [])
    assert dashboard_view(verdict="unknown")["verdict_filter"] == "UNKNOWN"
    assert dashboard_view(verdict="bogus")["verdict_filter"] == ""
