"""Assault review persistence, audit history and validation evidence."""
import pytest
from workbench.domains.assault_reviews import all_reviews, mark


def test_reviews_are_independent_and_audited(tmp_path):
    db = tmp_path / "assault_reviews.db"
    mark(42, "implementation", "in_progress", "ported Lua hooks", path=db)
    mark(42, "port", "validated", "merged code", "PR #123", path=db)
    mark(42, "implementation", "ready_for_test", "compiles", "test run 10", path=db)
    current, history = all_reviews(db)
    assert len(current) == 2
    assert len(history) == 3
    assert {r["stage"]: r["state"] for r in current} == {
        "implementation": "ready_for_test", "port": "validated"
    }
    assert history[0]["state"] == "ready_for_test"
    assert history[2]["note"] == "ported Lua hooks"


def test_validation_requires_evidence(tmp_path):
    db = tmp_path / "assault_reviews.db"
    with pytest.raises(ValueError, match="evidence"):
        mark(42, "validation", "validated", "works", path=db)
    with pytest.raises(ValueError, match="Mission"):
        mark(51, "port", "pending", "pending", path=db)
    with pytest.raises(ValueError, match="stage"):
        mark(1, "unknown", "pending", "invalid", path=db)
    assert all_reviews(db) == ([], [])
