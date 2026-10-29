"""#1408: the Compare runs page says, in words, what two recorded runs show and whether they can be compared at all.

The two real MOG-09 receipts are recorded data; every other record is SYNTHETIC. Nothing is executed and no change is
ever named as the cause of a difference.
"""
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_stored_run_comparison_1408 import CATALOG, FAIL, PASS, load, variant
from workbench.server_admin.feature_testing import compare_wording, results, router as ft_router

FT = Path(__file__).resolve().parents[1] / "src/workbench/server_admin/feature_testing"


@pytest.fixture()
def make_client(tmp_path, monkeypatch):
    def build(*loaders):
        db = tmp_path / "r.sqlite"
        for item in loaders:
            item(db)
        monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
        ft_router.templates.env.globals.setdefault("current_theme", lambda *a, **k: "dark")
        ft_router.templates.env.globals.setdefault("shell_context", lambda *a, **k: {})
        app = FastAPI()
        app.include_router(ft_router.router)
        return TestClient(app)
    return build


def real_pair(db):
    load(db, FAIL)
    load(db, PASS)


def two_revisions(tmp_path):
    ctx = dict(environment_fingerprint="synthetic-env-1", fixture_context="synthetic-fixture-1")
    def loader(db):
        load(db, variant(PASS, tmp_path, "a.json", "synthetic-run-a", dsp="a" * 40, **ctx))
        load(db, variant(FAIL, tmp_path, "b.json", "synthetic-run-b", dsp="b" * 40, **ctx))
    return loader


# --- wording ---------------------------------------------------------------------------------------------------------

def test_every_code_the_comparison_can_emit_has_wording():
    source = (FT / "revision_comparison.py").read_text(encoding="utf-8")
    literals = set(re.findall(r'"([A-Z][A-Z0-9_]{3,})"', source)) | set(re.findall(r'f"([A-Z][A-Z0-9_]+)_\{tag\}"', source))
    literals |= {"DSP_COMMIT_INVALID_LEFT", "DSP_COMMIT_INVALID_RIGHT", "UNCLASSIFIED_BLOCK_LEFT", "UNCLASSIFIED_BLOCK_RIGHT"}
    not_codes = {"NOT_ATTRIBUTED", "UNCLASSIFIED", "UNKNOWN", "BLOCKED", "SKIPPED", "PASS", "FAIL", "ENVIRONMENT",
                 "FIXTURE_ABSENT_KEY", "OTHER", "ORACLE_UNKNOWN_KEY", "DSP_COMMIT_INVALID", "UNCLASSIFIED_BLOCK", "LEFT", "RIGHT"}  # LEFT/RIGHT are side tags
    known = set(compare_wording.TRANSITIONS) | set(compare_wording.REASONS)
    missing = sorted(code for code in literals - not_codes if code not in known)
    assert missing == [], f"codes without wording: {missing}"
    assert "no description available" in compare_wording.reason_text("BRAND_NEW_CODE")  # never a guess


# --- the page --------------------------------------------------------------------------------------------------------

def test_chooser_lists_runs_and_runs_nothing(make_client):
    html = make_client(real_pair).get("/feature-testing/compare").text
    assert "Choose two runs" in html and "obs-20261021T025326Z" in html and "obs-20261021T040036Z" in html
    assert "Earlier run (left)" in html and 'method="get"' in html and "does not run anything" in html


def test_the_real_receipts_say_why_they_cannot_be_compared(make_client):
    html = make_client(real_pair).get("/feature-testing/compare?left=obs-20261021T025326Z&right=obs-20261021T040036Z").text
    assert "<strong>Not comparable.</strong>" in html and "<strong>Comparable.</strong>" not in html and "MOG-09" in html
    assert "Both runs used the same DSP revision, so this is a re-run" in html
    assert "did not record which test environment" in html and "did not record their test fixtures" in html
    assert "Not a cause." in html and "does not show that a DSP change caused it" in html
    assert "/feature-testing/run/obs-20261021T025326Z" in html and "Swap sides" in html
    assert re.search(r"<strong>FAIL</strong>", html) and re.search(r"<strong>PASS</strong>", html)


def test_a_comparable_pair_names_a_candidate_not_a_cause(make_client, tmp_path):
    client = make_client(two_revisions(tmp_path))
    html = client.get("/feature-testing/compare?left=synthetic-run-a&right=synthetic-run-b").text
    assert "<strong>Comparable.</strong>" in html and "<strong>Not comparable.</strong>" not in html
    assert "A candidate regression" in html and "does not show what caused it" in html
    assert "aaaaaaaaaaaa" in html and "bbbbbbbbbbbb" in html  # both DSP revisions are visible
    swapped = client.get("/feature-testing/compare?left=synthetic-run-b&right=synthetic-run-a").text
    assert "A candidate fix" in swapped


def test_problems_are_readable_pages_with_the_right_status(make_client, monkeypatch):
    client = make_client(real_pair)
    same = client.get("/feature-testing/compare?left=obs-20261021T025326Z&right=obs-20261021T025326Z")
    assert same.status_code == 400 and "Choose two different runs" in same.text
    missing = client.get("/feature-testing/compare?left=obs-20261021T025326Z&right=nope")
    assert missing.status_code == 404 and "both runs must exist" in missing.text and "text/html" in missing.headers["content-type"]
    monkeypatch.delenv("MISSION_TOOLKIT_TEST_RESULTS_DB")
    none = client.get("/feature-testing/compare?left=a&right=b")
    assert none.status_code == 404 and "No evidence database is configured" in none.text
    assert "No evidence database is configured" in client.get("/feature-testing/compare").text


def test_run_ids_are_escaped(make_client):
    def hostile(db):
        results.append_result(db, dict(run_id="<script>alert(1)</script>", feature_id="gardening", case_id="GRD-01",
                                       stage="behavior", verdict="UNKNOWN", observed_at="2026-10-28T01:00:00Z",
                                       dsp_commit="a" * 40, headless_commit="b" * 40, toolkit_commit="c" * 40,
                                       evidence={"summary": "synthetic"}))
    html = make_client(hostile).get("/feature-testing/compare").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_the_data_route_returns_the_raw_comparison_read_only(make_client):
    client = make_client(real_pair)
    data = client.get("/feature-testing/compare/data?left=obs-20261021T025326Z&right=obs-20261021T040036Z").json()
    assert data["execution_enabled"] is False and data["attribution"] == "NOT_ATTRIBUTED"
    assert data["comparisons"][0]["reasons"] == ["ENVIRONMENT_FINGERPRINT_MISSING", "FIXTURE_CONTEXT_MISSING", "SAME_DSP_REVISION"]
    assert client.get("/feature-testing/compare/data?left=obs-20261021T025326Z&right=nope").status_code == 400


def test_the_run_page_links_to_compare_but_a_missing_run_does_not(make_client):
    client = make_client(real_pair)
    assert "/feature-testing/compare?right=obs-20261021T040036Z" in client.get("/feature-testing/run/obs-20261021T040036Z").text
    assert "Compare with another run" not in client.get("/feature-testing/run/nope").text
