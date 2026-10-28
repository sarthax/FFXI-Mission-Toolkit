"""#1408: run context derivation. Real recorded MOG-09 receipts; the comparable pair at the end is SYNTHETIC."""
import json
from pathlib import Path

import pytest

from workbench.server_admin.feature_testing import importer, run_context
from workbench.server_admin.feature_testing.stored_run_comparison import compare_stored_runs

RECORDED = Path(__file__).parent / "results_v2_recorded"
FAIL = RECORDED / "mog09_fail_obs-20261021T025326Z.report.json"
PASS = RECORDED / "mog09_pass_obs-20261021T040036Z.report.json"
CATALOG = Path(__file__).resolve().parents[1] / "data/testing/feature_test_readiness.json"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def test_real_receipts_derive_identical_context_for_same_character_and_build():
    a, notes = run_context.add_run_context(load(FAIL))
    b, _ = run_context.add_run_context(load(PASS))
    ea, eb = a["results"][0]["evidence"], b["results"][0]["evidence"]
    assert ea["environment_fingerprint"] == eb["environment_fingerprint"]
    assert ea["fixture_context"] == eb["fixture_context"] == "character_id=21833;zone_id=106;stored_furnishing_item_ids=3"
    assert ea["environment_fingerprint"].endswith("headless_tree=clean") and not notes


def test_missing_inputs_leave_fields_out_and_existing_values_are_kept():
    report = load(PASS)
    ev = report["results"][0]["evidence"]
    del ev["observations"]["provenance"]
    ev["fixture_context"] = "owner-supplied"
    new, notes = run_context.add_run_context(report)
    out = new["results"][0]["evidence"]
    assert "environment_fingerprint" not in out and out["fixture_context"] == "owner-supplied"
    assert len(notes) == 2 and "environment_fingerprint not derivable" in notes[0]
    assert "environment_fingerprint" not in report["results"][0]["evidence"]  # input untouched


def test_dirty_tree_changes_fingerprint():
    obs = load(PASS)["results"][0]["evidence"]["observations"]
    clean = run_context.environment_fingerprint(obs)
    obs["provenance"]["headless_dirty_files"] = [" M a.cs"]
    assert run_context.environment_fingerprint(obs) != clean and "dirty:" in run_context.environment_fingerprint(obs)


@pytest.mark.parametrize("bad", ["zone", "ids"])
def test_fixture_requires_ints(bad):
    obs = load(PASS)["results"][0]["evidence"]["observations"]
    if bad == "zone":
        obs["snapshot"]["zone"] = "106"
    else:
        obs["stored_furnishing_item_ids"] = [3, "4"]
    assert run_context.fixture_context(obs) is None


def test_derived_report_imports_and_pair_with_new_dsp_is_comparable(tmp_path):
    """SYNTHETIC: the second run's DSP commit is altered, because no two real receipts share env+fixture with distinct DSP."""
    db = tmp_path / "scratch.db"
    left, _ = run_context.add_run_context(load(FAIL))
    right, _ = run_context.add_run_context(load(PASS))
    right["results"][0]["dsp_commit"] = "a" * 40
    for name, rep in (("l", left), ("r", right)):
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(rep), encoding="utf-8")
        assert importer.import_report(db, CATALOG, p) == 1
    result = compare_stored_runs(str(db), left["results"][0]["run_id"], right["results"][0]["run_id"])
    row = result["comparisons"][0]
    assert row["comparable"] is True and row["transition"] == "FIXED_CANDIDATE"


def test_run_page_shows_context_or_says_it_is_missing(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from workbench.server_admin.feature_testing import router as ft_router
    db = tmp_path / "r.sqlite"
    with_ctx, _ = run_context.add_run_context(load(PASS))
    for name, rep in (("a", with_ctx), ("b", load(FAIL))):
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(rep), encoding="utf-8")
        importer.import_report(db, CATALOG, p)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
    ft_router.templates.env.globals.setdefault("current_theme", lambda *a, **k: "dark")
    ft_router.templates.env.globals.setdefault("shell_context", lambda *a, **k: {})
    app = FastAPI()
    app.include_router(ft_router.router)
    client = TestClient(app)
    ok = client.get("/feature-testing/run/" + with_ctx["results"][0]["run_id"]).text
    assert '<code class="ft-inspect">character_id=21833;zone_id=106' in ok and "headless_tree=clean</code>" in ok
    bare = client.get("/feature-testing/run/" + load(FAIL)["results"][0]["run_id"]).text
    assert bare.count("not recorded (Compare runs will list this as missing)") == 2
