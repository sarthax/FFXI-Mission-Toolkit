import sqlite3

import pytest

from workbench.server_admin.feature_testing.results import append_result, recent_results


def record(**kw):
    d = {"run_id": "run-1", "case_id": "MOG-01", "feature_id": "moghancement",
         "stage": "modifier", "verdict": "PASS", "observed_at": "2026-10-18T20:00:00Z",
         "dsp_commit": "a" * 40, "headless_commit": "b" * 40,
         "toolkit_commit": "c" * 40, "evidence": {"baseline": 0, "actual": 10}}
    d.update(kw)
    return d


def test_append_only_evidence_and_filter(tmp_path):
    db = tmp_path / "evidence.sqlite"
    assert recent_results(db) == []
    append_result(db, record())
    append_result(db, record(run_id="run-2", stage="behavior", verdict="BLOCKED",
                             evidence={"reason": "missing client capability"}))
    assert len(recent_results(db, feature_id="moghancement")) == 2
    assert len(recent_results(db, case_id="MOG-01")) == 2
    row = recent_results(db, limit=1)[0]
    assert row["dsp_commit"] == "a" * 40
    assert row["evidence"]
    with pytest.raises(sqlite3.IntegrityError):
        append_result(db, record())
    assert len(recent_results(db)) == 2


def test_invalid_or_empty_evidence_never_recorded(tmp_path):
    db = tmp_path / "bad.sqlite"
    with pytest.raises(ValueError):
        append_result(db, record(evidence={}))
    with pytest.raises(ValueError):
        append_result(db, record(verdict="NOT_RUN"))
    assert recent_results(db) == []


def test_filtered_queries_do_not_interpolate_sql(tmp_path):
    db = tmp_path / "evidence.sqlite"
    append_result(db, record())
    assert recent_results(db, feature_id="moghancement' OR 1=1 --") == []
