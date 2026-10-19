"""Presentation-only adaptation of existing Feature Trace resolution to test investigations.

The adapter does not open a graph database, execute searches, or invent edges.
A future, authorized read-only graph service may pass already retrieved candidates
and relationships through this bounded adapter.
"""
from __future__ import annotations

from workbench.devtools.features.trace_resolver import resolve_candidates
from workbench.devtools.features.trace_modes import edge_allowed, relationship_relevance

_MAX_CANDIDATES = 8
_MAX_EDGES = 12
_MAX_INPUT = 100


def rank_trace_evidence(term: str, candidates: list[dict], edges: list[dict]) -> dict:
    if not isinstance(term, str) or not 3 <= len(term) <= 64:
        raise ValueError("invalid trace term")
    if not isinstance(candidates, list) or not isinstance(edges, list):
        raise ValueError("trace inputs must be lists")
    if len(candidates) > _MAX_INPUT or len(edges) > _MAX_INPUT:
        raise ValueError("trace inputs exceed bounded adapter limit")
    if any(not isinstance(row, dict) for row in candidates + edges):
        raise ValueError("trace rows must be objects")
    resolution = resolve_candidates(term, candidates)
    relevant = []
    for edge in edges:
        if not edge_allowed(edge, "diagnose") and not edge_allowed(edge, "implementation"):
            continue
        mode = "diagnose" if edge_allowed(edge, "diagnose") else "implementation"
        relevant.append({
            "source_node": str(edge.get("source_node") or "")[:160],
            "target_node": str(edge.get("target_node") or "")[:160],
            "relationship": str(edge.get("relationship") or "")[:120],
            "status": str(edge.get("status") or "UNKNOWN")[:40],
            "confidence": str(edge.get("confidence") or "UNKNOWN")[:40],
            "mode": mode,
            "relevance_score": relationship_relevance(edge.get("relationship"), mode),
            "evidence_id": str(edge.get("evidence_id") or "")[:160],
        })
    relevant.sort(key=lambda row: (-row["relevance_score"], row["source_node"], row["target_node"]))
    return {
        "query": term, "resolution_status": resolution.status,
        "root": resolution.root if resolution.status == "RESOLVED" else None,
        "resolution_confidence": resolution.confidence,
        "candidates": [
            {"node_id": str(row.get("node_id") or "")[:160],
             "display_name": str(row.get("display_name") or "")[:160],
             "node_type": str(row.get("node_type") or "")[:64],
             "resolver_score": row["resolver_score"]}
            for row in list(resolution.candidates)[:_MAX_CANDIDATES]
        ],
        "relationships": relevant[:_MAX_EDGES],
        "candidates_truncated": len(resolution.candidates) > _MAX_CANDIDATES,
        "relationships_truncated": len(relevant) > _MAX_EDGES,
        "provenance": "supplied_graph_rows_not_independently_verified",
        "graph_query_executed": False,
        "causal_conclusion": False,
    }
