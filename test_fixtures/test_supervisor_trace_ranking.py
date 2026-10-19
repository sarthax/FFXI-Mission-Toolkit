"""Bounded Feature Trace evidence presentation for supervisor investigation."""
import pytest
from workbench.server_admin.feature_testing.trace_ranking import rank_trace_evidence


def test_exact_root_and_diagnostic_relationship():
    result = rank_trace_evidence("auraMismatch",
        [{"node_id": "auraMismatch", "display_name": "auraMismatch", "node_type": "FUNCTION"}],
        [{"source_node": "auraMismatch", "target_node": "effect", "relationship": "validation_failure",
          "status": "DISCOVERED", "confidence": "REVIEW", "evidence_id": "ev1"}])
    assert result["resolution_status"] == "RESOLVED"
    assert result["root"] == "auraMismatch"
    assert result["relationships"][0]["mode"] == "diagnose"
    assert result["graph_query_executed"] is False
    assert result["causal_conclusion"] is False


def test_ambiguous_queries_do_not_choose_root():
    result = rank_trace_evidence("aura", [
        {"node_id": "aura:1", "display_name": "aura Alpha", "node_type": "FUNCTION"},
        {"node_id": "aura:2", "display_name": "aura Beta", "node_type": "FUNCTION"}], [])
    assert result["root"] is None


def test_unrelated_edges_not_returned():
    result = rank_trace_evidence("moghancement", [], [
        {"relationship": "is_near", "source_node": "a", "target_node": "b"}])
    assert result["relationships"] == []


def test_bounded_and_invalid_input_fail_closed():
    with pytest.raises(ValueError):
        rank_trace_evidence("foo", [{}] * 101, [])
    with pytest.raises(ValueError):
        rank_trace_evidence("foo", [], ["not-an-edge"])
