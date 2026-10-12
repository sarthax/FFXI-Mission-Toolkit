"""Read-only, annotation-based Feature Trace relevance audit.

Input is an exported trace JSON and a separate human-reviewed annotation JSON:
{"relevant_edge_ids":["..."],"required_edge_ids":["..."],"verified_edge_ids":["..."],
 "locator_edge_ids":["..."],"initial_edge_ids":["..."],
 "missing_required_paths":["independently verified path absent from returned graph"]}.
IDs must be stable trace relationship_id, edge_id, or id values. Unreviewed edges are NOT automatically irrelevant.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def score(trace: dict, annotations: dict) -> dict:
    edges = list(trace.get("edges") or [])
    ids = [str(e.get("relationship_id") or e.get("edge_id") or e.get("id") or "") for e in edges]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Trace edges require unique, nonempty relationship_id/edge_id/id for reproducible scoring; generated evidence without IDs must be reviewed separately")
    universe = set(ids)
    fields = ("relevant_edge_ids", "required_edge_ids", "verified_edge_ids",
              "locator_edge_ids", "initial_edge_ids")
    selections = {}
    for field in fields:
        raw = annotations.get(field)
        if not isinstance(raw, list) or any(not isinstance(v, str) for v in raw):
            raise ValueError(f"{field} must be an explicit list of edge IDs")
        selection = set(raw)
        if len(selection) != len(raw) or not selection <= universe:
            raise ValueError(f"{field} contains duplicate or unknown edge IDs")
        selections[field] = selection
    initial = selections["initial_edge_ids"]
    relevant = selections["relevant_edge_ids"]
    required = selections["required_edge_ids"]
    verified = selections["verified_edge_ids"]
    locators = selections["locator_edge_ids"]
    if not relevant <= verified or not required <= verified or not locators <= verified:
        raise ValueError("Relevant, required and locator-backed edges must be independently verified")
    missing = annotations.get("missing_required_paths", [])
    if not isinstance(missing, list) or any(not isinstance(v, str) or not v.strip() for v in missing) or len(missing) != len(set(missing)):
        raise ValueError("missing_required_paths must be a list of unique, nonempty descriptions")
    reviewed_initial = initial & verified
    irrelevant_reviewed = reviewed_initial - relevant
    unreviewed_initial = initial - verified
    def ratio(numerator: int, denominator: int):
        return round(numerator / denominator, 4) if denominator else None
    return {
        "status": "REVIEWED_ANNOTATIONS",
        "total_edges": len(edges),
        "initial_edges": len(initial),
        "verified_edges": len(verified),
        "relevant_initial_edges": len(initial & relevant),
        "irrelevant_initial_edges": len(irrelevant_reviewed),
        "unreviewed_initial_edges": len(unreviewed_initial),
        "reviewed_initial_edges": len(reviewed_initial),
        "review_coverage": ratio(len(reviewed_initial), len(initial)),
        "precision_verified_only": ratio(len(initial & relevant), len(reviewed_initial)),
        "required_path_recall": ratio(len(initial & required), len(required) + len(missing)),
        "missing_required_path_count": len(missing),
        "missing_required_paths": missing,
        "locator_coverage_verified_initial": ratio(len(initial & locators), len(initial & verified)),
        "caution": "Counts describe manually annotated edge IDs, not semantic correctness or source verification performed by this script.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_json", type=Path)
    parser.add_argument("annotations_json", type=Path)
    args = parser.parse_args()
    trace = json.loads(args.trace_json.read_text(encoding="utf-8"))
    annotations = json.loads(args.annotations_json.read_text(encoding="utf-8"))
    print(json.dumps(score(trace, annotations), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
