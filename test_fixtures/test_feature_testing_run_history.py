import re
from pathlib import Path

from workbench.server_admin.feature_testing.router import _run_summary


def test_run_summary_groups_by_run_and_verdict():
    records = [
        {"run_id": "r1", "observed_at": "2026-10-18T01:00:00Z", "feature_id": "gardening", "verdict": "PASS"},
        {"run_id": "r1", "observed_at": "2026-10-18T02:00:00Z", "feature_id": "moghancement", "verdict": "BLOCKED"},
        {"run_id": "r2", "observed_at": "2026-10-18T03:00:00Z", "feature_id": "gardening", "verdict": "FAIL"},
    ]
    runs = _run_summary(records)
    assert [r["run_id"] for r in runs] == ["r2", "r1"]
    assert runs[1]["features"] == ["gardening", "moghancement"]
    assert runs[1]["verdicts"] == {"PASS": 1, "BLOCKED": 1}
    assert runs[1]["latest"] == "2026-10-18T02:00:00Z"


def test_run_details_escape_through_jinja_and_use_existing_results():
    root = Path(__file__).resolve().parents[1]
    html = (root / "gui/templates/feature_testing_run.html").read_text(encoding="utf-8")
    assert re.search(r"result\.evidence\s*\|\s*tojson", html)
    assert "result.dsp_commit" in html
    main = (root / "gui/templates/feature_testing.html").read_text(encoding="utf-8")
    assert "/feature-testing/run/" in main
    assert "No results imported yet" in main
