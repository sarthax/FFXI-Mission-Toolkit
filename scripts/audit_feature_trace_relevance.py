"""Read-only, annotation-based Feature Trace relevance audit.

Input is an exported trace JSON and a separate human-reviewed annotation JSON:
{"relevant_edge_ids":["..."],"required_edge_ids":["..."],"verified_edge_ids":["..."],
 "locator_edge_ids":["..."],"initial_edge_ids":["..."],
 "missing_required_paths":["independently verified path absent from returned graph"]}.
IDs must be stable trace relationship_id, edge_id, or id values. Unreviewed edges are NOT automatically irrelevant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def audit_edge_ids(trace: dict) -> list[str]:
    """Stable audit-only IDs; never persisted into the canonical graph."""
    ids = []
    for edge in trace.get("edges") or []:
        native = edge.get("relationship_id") or edge.get("edge_id") or edge.get("id")
        if native is not None and str(native).strip():
            ids.append(str(native))
            continue
        source, target, relationship = (str(edge.get(k) or "").strip()
                                        for k in ("source_node", "target_node", "relationship"))
        if not all((source, target, relationship)):
            raise ValueError("Generated edge lacks source, target or relationship")
        metadata = edge.get("metadata") or {}
        generator = str(edge.get("generator") or (metadata.get("generator") if isinstance(metadata, dict) else "") or "")
        evidence = edge.get("evidence") or []
        if not isinstance(evidence, list):
            raise ValueError("Generated edge evidence must be a list")
        evidence_keys = sorted(json.dumps(v, sort_keys=True, separators=(",", ":"), default=str)
                               for v in evidence)
        signature = [source, target, relationship, generator, evidence_keys]
        digest = hashlib.sha256(json.dumps(signature, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        ids.append("audit:generated:" + digest)
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate edge audit identities; disambiguate source evidence before scoring")
    return ids


def annotation_template(trace: dict) -> dict:
    """Blank review template; never implies edges are verified or relevant."""
    audit_edge_ids(trace)
    return {
        "initial_edge_ids": [],
        "verified_edge_ids": [],
        "relevant_edge_ids": [],
        "required_edge_ids": [],
        "locator_edge_ids": [],
        "missing_required_paths": [],
    }


def score(trace: dict, annotations: dict) -> dict:
    edges = list(trace.get("edges") or [])
    ids = audit_edge_ids(trace)
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
    parser.add_argument("annotations_json", type=Path, nargs="?")
    parser.add_argument("--list-edges", action="store_true")
    parser.add_argument("--template", action="store_true", help="Print blank review annotations")
    args = parser.parse_args()
    trace = json.loads(args.trace_json.read_text(encoding="utf-8"))
    if args.template:
        print(json.dumps(annotation_template(trace), indent=2))
        return
    if args.list_edges:
        print(json.dumps([{"audit_id": edge_id, "source_node": edge.get("source_node"),
                           "relationship": edge.get("relationship"), "target_node": edge.get("target_node")}
                          for edge_id, edge in zip(audit_edge_ids(trace), trace.get("edges") or [])],
                         indent=2, sort_keys=True))
        return
    if args.annotations_json is None:
        parser.error("annotations_json is required unless --list-edges is supplied")
    annotations = json.loads(args.annotations_json.read_text(encoding="utf-8"))
    print(json.dumps(score(trace, annotations), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
