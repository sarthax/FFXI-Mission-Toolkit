from pathlib import Path

from workbench.server_admin.feature_testing.router import load_test_catalog, _summaries


def test_feature_testing_catalog_loads_real_plans():
    source = load_test_catalog()
    ids = {feature["id"] for feature in source["features"]}
    assert {"gardening", "moghancement", "voidwalker", "assault_nyzul"} <= ids
    rows = _summaries()
    assert all(row["cases"] for row in rows)
    assert all("counts" in row for row in rows)


def test_feature_testing_dashboard_template_uses_workbench_body():
    root = Path(__file__).resolve().parents[1]
    html = (root / "gui/templates/feature_testing.html").read_text(encoding="utf-8")
    assert '{% block page_body %}' in html
    assert "{{ case.status }}" in html
    assert "execution" in html.lower()


def test_scenario_drilldown_and_unknown_scenario():
    import pytest
    from fastapi import HTTPException
    from workbench.server_admin.feature_testing.router import scenario_detail

    detail = scenario_detail("moghancement", "MOG-01")
    assert detail["scenario"]["status"] == "planned"
    assert detail["expected_reference"]["source"] == "sql/item_furnishing.sql"
    assert detail["observed_results"] == []
    assert detail["execution_enabled"] is False
    with pytest.raises(HTTPException) as exc:
        scenario_detail("moghancement", "UNKNOWN")
    assert exc.value.status_code == 404


def test_scenario_page_template_exists():
    root = Path(__file__).resolve().parents[1]
    html = (root / "gui/templates/feature_testing_scenario.html").read_text(encoding="utf-8")
    assert "block page_body" in html
    assert "Recorded results" in html


def test_feature_testing_html_pages_render_through_host_app(monkeypatch, tmp_path):
    """Regression: router templates lacked the host's shell globals, so HTML pages returned HTTP 500."""
    import pytest
    host = pytest.importorskip("workbench.app.host", exc_type=Exception, reason="host app needs the venv dependencies")
    from fastapi.testclient import TestClient
    app = host.app
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(tmp_path / "absent.db"))
    client = TestClient(app)
    for path in ("/feature-testing", "/feature-testing?tab=catalog", "/feature-testing?tab=guide", "/feature-testing?tab=runs&verdict=FAIL", "/feature-testing/scenario/moghancement/MOG-01",
                 "/feature-testing/scenario/gardening/GARD-01"):
        assert client.get(path).status_code == 200, path


def test_dashboard_tabs_filter_runs_and_bound_pages(monkeypatch):
    from workbench.server_admin.feature_testing import router
    rows = [
        {"run_id": "run-a", "observed_at": "2026-10-19T10:00:00Z", "feature_id": "gardening", "verdict": "FAIL"},
        {"run_id": "run-b", "observed_at": "2026-10-18T10:00:00Z", "feature_id": "moghancement", "verdict": "PASS"},
    ]
    monkeypatch.setattr(router, "_history", lambda: rows)
    view = router.dashboard_view(feature="gardening", verdict="FAIL", query="RUN-A", page=100)
    assert view["tab"] == "runs"
    assert view["total_runs"] == 1 and view["page"] == 1
    assert [item["run_id"] for item in view["runs"]] == ["run-a"]
    assert router.dashboard_view(tab="unknown")["tab"] == "runs"
    assert router.dashboard_view(tab="setup")["tab"] == "guide"
    assert router.dashboard_view(tab="catalog")["tab"] == "catalog"
    assert router.dashboard_view(feature="moghancement", verdict="FAIL")["runs"] == []


def test_dashboard_navigation_and_setup_tabs_present():
    html = (Path(__file__).resolve().parents[1] / "gui/templates/feature_testing.html").read_text(encoding="utf-8")
    for expected in ('tab=runs', 'tab=catalog', 'tab=guide', 'name="verdict"', 'name="feature"',
                     'name="query"', 'Run history', 'MISSION_TOOLKIT_TEST_RESULTS_DB'):
        assert expected in html


def test_feature_testing_discoverable_in_shared_shell_and_home():
    from workbench.gui_shell import WORKSPACES
    validation = next(w for w in WORKSPACES if w["name"] == "Validation")
    testing = next(s for s in validation["sections"] if s["href"] == "/feature-testing")
    assert testing["label"] == "Feature Testing & Validation"
    assert any("feature-testing" in pattern for pattern in testing["active_patterns"])
    home = (Path(__file__).resolve().parents[1] / "gui/templates/home.html").read_text(encoding="utf-8")
    assert 'href="/feature-testing?tab=runs"' in home
    assert 'href="/feature-testing?tab=catalog"' in home


def test_inventory_observation_contract_is_read_only_and_discoverable():
    from workbench.server_admin.feature_testing.router import scenario_detail
    detail = scenario_detail("inventory_observation", "INV-OBS-01")
    assert detail["execution_enabled"] is False
    case = detail["scenario"]
    assert case["run_mode"] == "local_read_only_observation"
    assert "persisted_char_inventory_rows" in case["evidence_required"]
    assert "headless_dll_sha256" in case["required_artifacts"]
    assert "truncated DB snapshot" in case["negative_invariant"]


def test_run_inspector_exposes_assertions_and_provenance():
    html = (Path(__file__).resolve().parents[1] / "gui/templates/feature_testing_run.html").read_text(encoding="utf-8")
    for fragment in ("assertion.ok", "assertion.expected", "assertion.observed",
                     "headless_dll_sha256", "headless_dirty_files",
                     "capability_gaps", "Full original evidence"):
        assert fragment in html
