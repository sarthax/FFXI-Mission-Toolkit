import json
import sqlite3

import pytest

from workbench.server_admin.feature_testing.importer import import_report
from workbench.server_admin.feature_testing.results import recent_results


def fixtures(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"features": [
        {"id": "moghancement", "cases": [{"id": "MOG-01"}, {"id": "MOG-02"}]}
    ]}))
    row = {
        "run_id": "test-run-001", "feature_id": "moghancement", "case_id": "MOG-01",
        "stage": "modifier", "verdict": "PASS", "observed_at": "2026-10-18T21:05:00Z",
        "dsp_commit": "a" * 40, "headless_commit": "b" * 40,
        "toolkit_commit": "c" * 40,
        "evidence": {"assertions": [{"name": "modifier_delta", "passed": True}],
                     "observations": {"before": 0, "after": 10}}
    }
    report = tmp_path / "report.json"
    db = tmp_path / "results.sqlite"
    return catalog, report, db, row


def write(report, rows):
    report.write_text(json.dumps({"schema_version": 1, "results": rows}))


def test_valid_report_import_and_duplicate_rejection(tmp_path):
    catalog, report, db, row = fixtures(tmp_path)
    write(report, [row])
    assert import_report(db, catalog, report) == 1
    assert recent_results(db)[0]["case_id"] == "MOG-01"
    with pytest.raises(sqlite3.IntegrityError):
        import_report(db, catalog, report)
    assert len(recent_results(db)) == 1


def test_invalid_result_rolls_back_entire_batch(tmp_path):
    catalog, report, db, row = fixtures(tmp_path)
    bad = dict(row, case_id="UNKNOWN", stage="behavior")
    write(report, [row, bad])
    with pytest.raises(ValueError, match="unknown"):
        import_report(db, catalog, report)
    assert recent_results(db) == []


def test_missing_pass_evidence_and_unknown_sha_rejected(tmp_path):
    catalog, report, db, row = fixtures(tmp_path)
    write(report, [dict(row, evidence={"message": "success"})])
    with pytest.raises(ValueError, match="assertions"):
        import_report(db, catalog, report)
    write(report, [dict(row, dsp_commit="unknown")])
    with pytest.raises(ValueError, match="SHA"):
        import_report(db, catalog, report)


def test_rejects_duplicate_identity_even_before_db_creation(tmp_path):
    catalog, report, db, row = fixtures(tmp_path)
    write(report, [row, row])
    with pytest.raises(ValueError, match="duplicate"):
        import_report(db, catalog, report)
    assert not db.exists()
