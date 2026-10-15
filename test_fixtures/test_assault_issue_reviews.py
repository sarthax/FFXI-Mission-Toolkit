"""Issue-level Assault audit review regression."""
import pytest
from workbench.domains.assault_issue_reviews import mark, read


def test_per_issue_stages_and_history(tmp_path):
    db = tmp_path / "review.db"
    mark(42, 1, "topaz", "fixed", "referenced fix", "fix-log section 50", path=db, issue_count=4)
    mark(42, 1, "dsp_port", "open", "not ported", path=db, issue_count=4)
    mark(42, 1, "topaz", "in_progress", "rechecking history", path=db, issue_count=4)
    current, history = read(db)
    assert len(current) == 2
    assert len(history) == 3
    assert {(r["stage"], r["state"]) for r in current} == {
        ("topaz", "in_progress"), ("dsp_port", "open")}
    assert history[0]["state"] == "in_progress"


def test_invalid_review_is_not_persisted(tmp_path):
    db = tmp_path / "review.db"
    with pytest.raises(ValueError, match="evidence"):
        mark(1, 1, "dsp_validation", "fixed", "passed", path=db)
    with pytest.raises(ValueError, match="index"):
        mark(42, 5, "topaz", "open", issue_count=4, path=db)
    with pytest.raises(ValueError, match="stage"):
        mark(42, 1, "unknown", "open", path=db)
    assert read(db) == ([], [])


def test_issue_ui_and_route():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    page = (root / "gui/templates/domain_assault.html").read_text(encoding="utf-8")
    host = (root / "src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    assert 'action="/domains/assault/issue/review"' in page
    assert 'issue.reviews[stage]' in page
    assert 'issue.history' in page
    assert 'issue_count=len(mission["issue_crossrefs"])' in host
