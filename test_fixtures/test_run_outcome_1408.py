"""#1408: the Run Results page says in words what a stored result does and does not establish. Offline only.

Every record here is SYNTHETIC test data, not a real run, and nothing is executed.
"""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.server_admin.feature_testing import execution_jobs, results, router as ft_router
from workbench.server_admin.feature_testing.run_outcome import describe_outcome

BASE = dict(dsp_commit="a" * 40, headless_commit="b" * 40, toolkit_commit="c" * 40)


def rec(verdict, evidence, run_id="synthetic-run", feature="gardening", case="GRD-01"):
    return dict(run_id=run_id, feature_id=feature, case_id=case, stage="behavior", verdict=verdict,
                observed_at="2026-10-28T01:00:00Z", evidence=evidence, **BASE)


def rows(*assertions):
    return {"assertions": [{"name": f"a{i}", "expected": 1, "observed": 1, "ok": ok} for i, ok in enumerate(assertions)]}


# --- the description itself --------------------------------------------------------------------------------------

def test_fail_is_described_as_a_mismatch_with_counts():
    out = describe_outcome(rec("FAIL", rows(True, False, False)))
    assert out["verdict"] == "FAIL" and out["assertion_failed"] == 2 and out["assertion_ok"] == 1
    assert "did not match" in out["meaning"] and out["warnings"] == [] and out["reason"] is None


@pytest.mark.parametrize("cls,text", [("ENVIRONMENT", "environment"), ("FIXTURE_ABSENT", "fixture"),
                                      ("ORACLE_UNKNOWN", "pass or fail"), ("OTHER", "another cause")])
def test_blocked_states_its_recorded_reason_and_note(cls, text):
    out = describe_outcome(rec("BLOCKED", {"reason_class": cls, "note": "synthetic: nothing ran"}))
    assert out["reason"]["class"] == cls and text in out["reason"]["text"]
    assert out["note"] == "synthetic: nothing ran" and "could not be carried out" in out["meaning"]


def test_a_missing_reason_is_stated_as_missing_not_guessed():
    for verdict in ("BLOCKED", "UNKNOWN"):
        out = describe_outcome(rec(verdict, {"summary": "x"}))
        assert out["reason"]["class"] == "UNCLASSIFIED" and "no reason was recorded" in out["reason"]["text"]
        assert out["note"] is None


def test_unknown_is_neither_pass_nor_fail():
    out = describe_outcome(rec("UNKNOWN", {"note": "synthetic: no readback"}))
    assert "not a pass and not a failure" in out["meaning"] and out["note"] == "synthetic: no readback"


def test_pass_without_structured_checks_is_flagged():
    for evidence in ({"summary": "unstructured"}, {"assertions": []}, {"assertions": ["not a row", 3]}):
        out = describe_outcome(rec("PASS", evidence))
        assert out["assertion_total"] == 0 and any("no structured checks" in w for w in out["warnings"])
    assert "nothing independent has confirmed it" in out["meaning"]


def test_inconsistent_pass_and_fail_are_flagged_not_corrected():
    assert any("not every recorded check" in w for w in describe_outcome(rec("PASS", rows(True, False)))["warnings"])
    assert any("no recorded check is marked as failing" in w for w in describe_outcome(rec("FAIL", rows(True)))["warnings"])
    assert describe_outcome(rec("PASS", rows(True, True)))["warnings"] == []
    assert describe_outcome(rec("PASS", rows(True, True)))["verdict"] == "PASS"


def test_note_is_bounded_and_only_read_for_blocked_or_unknown():
    assert len(describe_outcome(rec("UNKNOWN", {"note": "x" * 5000}))["note"]) == 300
    assert describe_outcome(rec("PASS", {"note": "shown nowhere", **rows(True)}))["note"] is None


def test_job_progress_is_a_separate_fact_from_the_verdict():
    out = describe_outcome(rec("UNKNOWN", {"note": "n"}), {"status": "COMPLETED", "phase": "evidence_imported",
                                                          "verdict": "UNKNOWN", "error": None})
    assert out["verdict"] == "UNKNOWN" and out["job"]["status"] == "COMPLETED"
    assert out["job"]["verdict_agrees"] is True and out["job"]["error_recorded"] is False
    differs = describe_outcome(rec("FAIL", rows(False)), {"status": "COMPLETED", "phase": "p", "verdict": "PASS", "error": "boom"})
    assert differs["job"]["verdict_agrees"] is False and differs["job"]["error_recorded"] is True
    assert "boom" not in repr(differs)  # the error text itself is never passed on, only that one exists
    assert describe_outcome(rec("PASS", rows(True)))["job"] is None


def test_unknown_values_are_not_trusted():
    out = describe_outcome(rec("MAYBE", rows(True)), {"status": "WEIRD"})
    assert "Unrecognised verdict" in out["meaning"] and out["job"]["meaning"] == "an unrecognised state"


# --- the job lookup ----------------------------------------------------------------------------------------------

def test_job_lookup_is_read_only_and_exposes_no_account_or_character(tmp_path, monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_JOBS_DB", raising=False)
    assert execution_jobs.job_for_run("r1") is None
    missing = tmp_path / "jobs.sqlite"
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(missing))
    assert execution_jobs.job_for_run("r1") is None and not missing.exists()  # never creates the store
    with execution_jobs._connect() as db:
        db.execute("INSERT INTO feature_test_jobs (id, created_at, updated_at, case_id, status, account, charid, run_id, verdict, error, phase) "
                   "VALUES ('j1','2026-10-28T00:00:00Z','2026-10-28T00:00:00Z','MOG-09','COMPLETED','secret-account',12345,'r1','PASS',NULL,'evidence_imported')")
    job = execution_jobs.job_for_run("r1")
    assert job == {"status": "COMPLETED", "phase": "evidence_imported", "verdict": "PASS", "error": None,
                   "run_options": None}  # None = recorded before #1484 or not recorded
    assert "secret-account" not in repr(job) and "12345" not in repr(job)
    assert execution_jobs.job_for_run("other") is None


# --- the page ----------------------------------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "results.sqlite"
    results.append_result(db, rec("FAIL", rows(True, False), run_id="r-fail"))
    results.append_result(db, rec("BLOCKED", {"reason_class": "ENVIRONMENT", "note": "synthetic: no sandbox <b>x</b>"}, run_id="r-blocked", case="GRD-02"))
    results.append_result(db, rec("UNKNOWN", {"summary": "x"}, run_id="r-unknown", case="GRD-03"))
    results.append_result(db, rec("PASS", {"summary": "unstructured"}, run_id="r-bare-pass", case="GRD-04"))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_JOBS_DB", raising=False)
    ft_router.templates.env.globals.setdefault("current_theme", lambda *a, **k: "dark")
    ft_router.templates.env.globals.setdefault("shell_context", lambda *a, **k: {})
    app = FastAPI()
    app.include_router(ft_router.router)
    return TestClient(app)


def page(client, run_id):
    response = client.get(f"/feature-testing/run/{run_id}")
    assert response.status_code == 200
    return response.text


def test_page_says_what_happened_for_each_state(client):
    fail = page(client, "r-fail")
    assert "What happened" in fail and "1 passing, 1 failing, 0 unclear" in fail
    blocked = page(client, "r-blocked")
    assert "the test environment was not available (ENVIRONMENT)" in blocked.replace("The test", "the test")
    assert "synthetic: no sandbox &lt;b&gt;x&lt;/b&gt;" in blocked and "<b>x</b>" not in blocked  # escaped, not markup
    assert "No runner job is linked" in blocked
    unknown = page(client, "r-unknown")
    assert "no reason was recorded" in unknown.lower() and "not a pass and not a failure" in unknown
    bare = page(client, "r-bare-pass")
    assert "no structured checks" in bare and "nothing independent has confirmed it" in bare


def test_page_shows_the_job_as_separate_from_the_verdict(client, tmp_path, monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_JOBS_DB", str(tmp_path / "jobs.sqlite"))
    with execution_jobs._connect() as db:
        db.execute("INSERT INTO feature_test_jobs (id, created_at, updated_at, case_id, status, account, charid, run_id, verdict, error, phase) "
                   "VALUES ('j1','2026-10-28T00:00:00Z','2026-10-28T00:00:00Z','GRD-03','COMPLETED','acct',1,'r-unknown','UNKNOWN',NULL,'evidence_imported')")
    html = page(client, "r-unknown")
    assert "COMPLETED — finished running" in html and "A finished job is not a pass" in html
    assert "acct" not in html


def test_unknown_run_is_a_404_and_history_without_data_has_guidance(client, tmp_path, monkeypatch):
    assert client.get("/feature-testing/run/nope").status_code == 404
    empty = tmp_path / "empty.sqlite"
    results.init_db(empty)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(empty))
    assert "No results imported yet." in client.get("/feature-testing?tab=runs").text  # configured but empty
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_RESULTS_DB")
    assert "No evidence database configured" in client.get("/feature-testing?tab=runs").text  # not configured


# --- recorded MOG-09 reports through the real importer and page ----------------------------------------------------

from pathlib import Path  # noqa: E402

RECORDED = Path(__file__).parent / "results_v2_recorded"
CATALOG = Path(__file__).resolve().parents[1] / "data/testing/feature_test_readiness.json"


@pytest.fixture()
def recorded_client(tmp_path, monkeypatch):
    from workbench.server_admin.feature_testing import importer
    db = tmp_path / "recorded.sqlite"
    for name in sorted(RECORDED.glob("*.report.json")):
        assert importer.import_report(db, CATALOG, name) == 1
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_JOBS_DB", raising=False)
    ft_router.templates.env.globals.setdefault("current_theme", lambda *a, **k: "dark")
    ft_router.templates.env.globals.setdefault("shell_context", lambda *a, **k: {})
    app = FastAPI()
    app.include_router(ft_router.router)
    return TestClient(app)


def step_card(html, number):
    """The HTML of one step card, from its summary to the next card."""
    start = html.index(f"<strong>{number}. ")
    end = html.find("<strong>%d. " % (number + 1), start)
    return html[start:end if end != -1 else len(html)]


def test_recorded_fail_shows_both_compared_sides_for_the_failed_steps(recorded_client):
    html = recorded_client.get("/feature-testing/run/obs-20261021T025326Z").text
    assert "What happened" in html and "At least one imported check did not match its expectation." in html
    bag = step_card(html, 5)
    assert "Values compared" in bag and "Server database (persisted)" in bag and "Client-observed" in bag
    assert "empty — no rows" in bag  # the persisted side the old card never showed
    assert "8 rows" in bag  # the client side, as a count rather than "(large value)"
    safe = step_card(html, 6)
    assert "Values compared" in safe and "Server database (persisted)" in safe
    assert "(large value)" not in html


def test_recorded_fail_keeps_unrelated_steps_and_the_limits(recorded_client):
    html = recorded_client.get("/feature-testing/run/obs-20261021T025326Z").text
    assert "Independent verification: NOT_ESTABLISHED" in html
    assert "Steps PASS (recalculated only): 4/6" in html
    assert "Assertion FAILED" in step_card(html, 5)


def test_recorded_pass_is_still_only_a_recorded_verdict(recorded_client):
    html = recorded_client.get("/feature-testing/run/obs-20261021T040036Z").text
    assert "nothing independent has confirmed it" in html and "Independent verification: NOT_ESTABLISHED" in html
    assert "(large value)" not in html


def test_missing_run_is_a_readable_404_page_not_bare_json(recorded_client):
    response = recorded_client.get("/feature-testing/run/does-not-exist")
    assert response.status_code == 404 and "text/html" in response.headers["content-type"]
    assert "Run not found" in response.text and "does-not-exist" in response.text
    assert "/feature-testing?tab=runs" in response.text and '{"detail"' not in response.text
