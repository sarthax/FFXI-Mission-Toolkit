"""Offline contract tests for #1333 Validation landing operator navigation.

No host, DB, browser, client, MCP, or gameplay execution is started.
"""
from __future__ import annotations

import re

from test_gui_shell import render


def landing(**overrides):
    data = dict(runs=[], status_counts={}, result_counts={}, total_results=0, error=None)
    data.update(overrides)
    return render("validation_dashboard.html", "/validation", **data)


def test_five_entry_points_exist_and_point_to_existing_surfaces():
    html = landing()
    assert set(re.findall(r'data-validation-entry="([^"]+)"', html)) == {
        "catalog", "developer", "preflight", "evidence", "results"
    }
    for url in (
        "/feature-testing?tab=catalog",
        "/scenario-developer",
        "/feature-testing/scenario/moghancement/MOG-09",
        "/feature-testing/preflight/moghancement/MOG-09",
        "/captures",
        "/feature-testing?tab=runs",
        "/validation/runs",
    ):
        assert f'href="{url}"' in html, url


def test_error_is_scoped_to_canonical_history_and_other_navigation_survives():
    html = landing(error="Build workbench.db first <do not interpolate>")
    assert "Canonical history unavailable:" in html
    assert "Build workbench.db first &lt;do not interpolate&gt;" in html
    assert "only affects this history view" in html
    assert 'href="/scenario-developer"' in html
    assert 'href="/captures"' in html
    assert 'href="/feature-testing?tab=catalog"' in html
    assert 'href="/validation/runs"' in html
    assert "Recent canonical runs" not in html


def test_empty_database_does_not_imply_empty_feature_testing_history():
    html = landing()
    assert "No canonical validation runs are recorded for the available database" in html
    assert "separately imported history" in html
    assert "An empty or unconfigured history must not be interpreted" in html


def test_recorded_rows_keep_existing_canonical_run_details_link():
    html = landing(
        runs=[{"run_id": "synthetic-run-1", "name": "Synthetic",
               "status": "UNKNOWN", "feature_id": "demo",
               "source_snapshot_id": None, "target_snapshot_id": None,
               "started_at": "2026-01-01", "finished_at": None}],
        status_counts={"VERIFIED": 0, "FAILED": 0},
    )
    assert 'href="/validation/runs/synthetic-run-1"' in html
    assert "Synthetic" in html
    assert "Verified runs" in html


def test_preflight_and_evidence_limits_are_explicit():
    html = landing()
    for label in (
        "R8 canonical catalog API is a separate release candidate",
        "It is not the separate R8 pure advisory preview",
        "UNKNOWN, BLOCKED or UNSUPPORTED",
        "Evidence Reviewer (offline)",
        "standalone local HTML report",
        "Capture Review Queue is a different workflow",
        "INV-OBS-01 has no assigned runner",
        "execution_enabled=false",
        "independently verified gameplay",
    ):
        assert label in html, label


def test_navigation_does_not_dispatch_or_introduce_unmerged_r8_routes():
    html = landing()
    assert "<form" not in html
    assert "<script" not in html
    assert 'href="/feature-testing/r8/catalog"' not in html
    assert 'href="/feature-testing/r8/preflight/moghancement/MOG-09"' not in html
    assert "/builder/launch" not in html
    assert "No canonical validation runs" in html
