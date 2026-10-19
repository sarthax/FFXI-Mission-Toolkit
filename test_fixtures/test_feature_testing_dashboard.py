from pathlib import Path

from workbench.server_admin.feature_testing.router import test_catalog, _summaries


def test_feature_testing_catalog_loads_real_plans():
    source = test_catalog()
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
