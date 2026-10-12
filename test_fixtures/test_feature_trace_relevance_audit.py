"""Smoke/regression checks for the manual Feature Trace relevance scorer."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("trace_audit", ROOT / "scripts" / "audit_feature_trace_relevance.py")
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_scoring():
    trace = {"edges": [{"id": "spawn"}, {"id": "pool"}, {"id": "wiki"}]}
    annotation = {
        "relevant_edge_ids": ["spawn", "pool"],
        "required_edge_ids": ["spawn", "pool"],
        "verified_edge_ids": ["spawn", "pool"],
        "locator_edge_ids": ["spawn"],
        "initial_edge_ids": ["spawn", "wiki"],
    }
    result = module.score(trace, annotation)
    assert result["total_edges"] == 3
    assert result["required_path_recall"] == 0.5
    assert result["precision_verified_only"] == 1.0
    assert result["unreviewed_initial_edges"] == 1
    assert result["irrelevant_initial_edges"] == 0
    assert result["reviewed_initial_edges"] == 1
    assert result["review_coverage"] == 0.5
    assert result["locator_coverage_verified_initial"] == 1.0
    annotation["missing_required_paths"] = ["AV Lua behavior entry point"]
    with_gap = module.score(trace, annotation)
    assert with_gap["missing_required_path_count"] == 1
    assert with_gap["required_path_recall"] == 0.3333


def test_native_relationship_ids():
    trace = {"edges": [{"relationship_id": "persisted-1"}]}
    annotation = {name: ["persisted-1"] for name in (
        "relevant_edge_ids", "required_edge_ids", "verified_edge_ids",
        "locator_edge_ids", "initial_edge_ids")}
    assert module.score(trace, annotation)["precision_verified_only"] == 1.0


def test_invalid_edge_reference():
    trace = {"edges": [{"id": "a"}]}
    annotation = {name: [] for name in (
        "relevant_edge_ids", "required_edge_ids", "verified_edge_ids",
        "locator_edge_ids", "initial_edge_ids")}
    annotation["initial_edge_ids"] = ["missing"]
    try:
        module.score(trace, annotation)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown edge must fail closed")


if __name__ == "__main__":
    test_scoring()
    test_invalid_edge_reference()
    test_native_relationship_ids()
    print("Feature Trace audit scorer checks passed")
