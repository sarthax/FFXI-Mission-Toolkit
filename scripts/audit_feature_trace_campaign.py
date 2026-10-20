#!/usr/bin/env python3
"""Read-only, privacy-conscious three-case Feature Trace relevance audit campaign.

The local operator supplies actual exported trace JSON and independently reviewed
annotations. This script never queries DSP, indexes files or starts a client.
A measured scorecard is NOT a usability PASS or runtime acceptance by itself.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from audit_feature_trace_relevance import audit_edge_ids, score

CASES = {
    "absolute-virtue": ("implementation", "entity"),
    "wotg-cait-sith": ("mission", "mission"),
    "ordinary-npc": ("implementation", "entity"),
}
STATUS = frozenset({"NOT_RUN", "BLOCKED", "REVIEWED"})
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
EXPORT_SCHEMA = "feature-trace-relevance-export-v1"



def template() -> dict:
    """Unrun scaffold. No invented IDs or implied verified evidence."""
    return {
        "schema_version": 1,
        "cases": [
            {
                "case_id": case, "mode": mode, "root_kind": kind,
                "status": "NOT_RUN",
                "reason": "Local indexed source and independent operator review pending",
            }
            for case, (mode, kind) in CASES.items()
        ],
    }


def _nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())



def validate_export_binding(trace: dict, *, case_id: str, root_id: str,
                            mode: str, root_kind: str) -> dict:
    """Require the *actual exported payload* to agree with the reviewed campaign.

    The old scorer accepts generic edge lists by design. A three-case real-object
    campaign must not silently score an unrelated raw graph, renamed root,
    reversed mode or changed/duplicated edge set. No data is persisted.
    """
    if trace.get("schema") != EXPORT_SCHEMA:
        raise ValueError(f"{case_id}: not a versioned exact-root P0 trace export")
    expected = {
        "case_id": case_id, "root": root_id,
        "mode": mode, "root_kind": root_kind,
    }
    for field, value in expected.items():
        if trace.get(field) != value:
            raise ValueError(f"{case_id}: exported {field} disagrees with campaign")
    depth = trace.get("depth")
    if type(depth) is not int or depth not in (1, 2):
        raise ValueError(f"{case_id}: unrecognized export depth")
    if trace.get("direction") not in {"in", "out", "both"}:
        raise ValueError(f"{case_id}: unrecognized export direction")
    max_nodes = trace.get("max_nodes")
    if type(max_nodes) is not int or not (1 <= max_nodes <= 500):
        raise ValueError(f"{case_id}: unbounded export node budget")
    if type(trace.get("truncated")) is not bool:
        raise ValueError(f"{case_id}: missing trace truncation indicator")
    edges = trace.get("edges")
    ids = trace.get("edge_audit_ids")
    if not isinstance(edges, list) or not isinstance(ids, list):
        raise ValueError(f"{case_id}: missing edge list or audit identities")
    calculated = audit_edge_ids(trace)
    if ids != calculated:
        raise ValueError(f"{case_id}: exported edge identities no longer match graph evidence")
    return {
        "export_schema": EXPORT_SCHEMA,
        "export_depth": depth,
        "export_direction": trace["direction"],
        "export_truncated": trace["truncated"],
        "export_edge_count": len(edges),
    }


def _case_entry(raw: dict, base: Path) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Case entry must be a JSON object")
    key = raw.get("case_id")
    if key not in CASES:
        raise ValueError("Unknown case_id")
    mode, root_kind = CASES[key]
    if raw.get("mode") != mode or raw.get("root_kind") != root_kind:
        raise ValueError(f"{key}: mode or root_kind does not match the pinned scenario")
    status = raw.get("status")
    if status not in STATUS:
        raise ValueError(f"{key}: invalid status")
    summary = {"case_id": key, "mode": mode, "root_kind": root_kind}
    if status in {"NOT_RUN", "BLOCKED"}:
        if not _nonempty(raw.get("reason")):
            raise ValueError(f"{key}: unavailable cases require an explicit reason")
        if any(raw.get(field) for field in ("trace_json", "annotations_json")):
            raise ValueError(f"{key}: unfinished case may not reference scored evidence")
        summary.update({"status": status, "reason": "Local evidence unavailable or blocked",
                        "scored": False})
        return summary

    # Claiming that a local case was independently reviewed requires explicit
    # source identity, exact revisions and a reviewed edge ledger.
    for field in ("resolved_root_id", "reviewed_by", "trace_json", "annotations_json"):
        if not _nonempty(raw.get(field)):
            raise ValueError(f"{key}: {field} is required for REVIEWED")
    for field in ("toolkit_sha", "server_sha"):
        if not SHA.fullmatch(str(raw.get(field) or "")):
            raise ValueError(f"{key}: {field} must be a complete Git commit SHA")
    if raw.get("root_resolution") != "unique":
        raise ValueError(f"{key}: only a uniquely resolved root can be REVIEWED")
    families = raw.get("source_families")
    if not isinstance(families, list) or not families or any(not _nonempty(v) for v in families):
        raise ValueError(f"{key}: list real indexed source_families")
    if len(families) != len(set(families)):
        raise ValueError(f"{key}: duplicate source_families")

    def load(name):
        requested = Path(raw[name])
        path = requested if requested.is_absolute() else base / requested
        # Explicit local paths may be outside Git. Never echo them in output.
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{key}: {name} must contain a JSON object")
        return value

    trace = load("trace_json")
    export = validate_export_binding(
        trace, case_id=key, root_id=raw["resolved_root_id"],
        mode=mode, root_kind=root_kind,
    )
    scored = score(trace, load("annotations_json"))
    # The scorer itself NEVER validates source truth. Even a complete reviewer
    # ledger remains a measurement, not a verified feature implementation.
    all_reviewed = scored["initial_edges"] > 0 and scored["review_coverage"] == 1.0
    required_paths_defined = scored["required_path_recall"] is not None
    ready = all_reviewed and required_paths_defined
    summary.update({
        "status": "MEASURED_REVIEW_REQUIRED" if ready else "INCOMPLETE_ANNOTATIONS",
        "scored": True,
        "root_resolution": "unique",
        **export,
        "toolkit_sha": raw["toolkit_sha"].lower(),
        "server_sha": raw["server_sha"].lower(),
        "source_family_count": len(families),
        "initial_edges": scored["initial_edges"],
        "review_coverage": scored["review_coverage"],
        "precision_verified_only": scored["precision_verified_only"],
        "required_path_recall": scored["required_path_recall"],
        "locator_coverage_verified_initial": scored["locator_coverage_verified_initial"],
        "missing_required_path_count": scored["missing_required_path_count"],
        "unreviewed_initial_edges": scored["unreviewed_initial_edges"],
    })
    return summary


def evaluate(manifest: dict, manifest_dir: Path) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Expected Feature Trace campaign schema_version 1")
    entries = manifest.get("cases")
    if not isinstance(entries, list) or len(entries) != len(CASES):
        raise ValueError("Campaign must contain exactly the three pinned cases")
    names = [v.get("case_id") if isinstance(v, dict) else None for v in entries]
    if len(names) != len(set(names)) or set(names) != set(CASES):
        raise ValueError("Campaign has missing, duplicated or unknown cases")
    reviewed_roots = [row["resolved_root_id"] for row in entries
                      if row["status"] == "REVIEWED"]
    if len(reviewed_roots) != len(set(reviewed_roots)):
        raise ValueError("Different campaign cases cannot reuse one resolved root ID")
    items = [_case_entry(entry, manifest_dir) for entry in entries]
    ready = all(v["status"] == "MEASURED_REVIEW_REQUIRED" for v in items)
    return {
        "schema_version": 1, "audit": "feature-trace-relevance-real-object-baseline",
        "overall": "MEASURED_PENDING_OPERATOR_ACCEPTANCE" if ready else "NOT_READY",
        "cases": items, "counts": {
            key: sum(item["status"] == key for item in items)
            for key in ("NOT_RUN", "BLOCKED", "INCOMPLETE_ANNOTATIONS", "MEASURED_REVIEW_REQUIRED")
        },
        "caution": ("Metrics require independently inspected source paths and explicit first-screen "
                    "annotations. This utility does not verify source truth, runtime behavior, "
                    "source locators, browser navigation or acceptance. NOT_READY is not a FAIL."),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?",
                        help="Private, local JSON manifest; raw data is never printed")
    parser.add_argument("--template", action="store_true",
                        help="Print a blank three-case NOT_RUN manifest")
    args = parser.parse_args(argv)
    if args.template:
        if args.manifest:
            parser.error("--template does not accept a manifest")
        print(json.dumps(template(), indent=2))
        return 0
    if args.manifest is None:
        parser.error("manifest required unless --template is used")
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = evaluate(data, args.manifest.resolve().parent)
    print(json.dumps(report, indent=2, sort_keys=True))
    # No nonzero exit for legitimately NOT_RUN campaigns; structural/identity
    # errors raise rather than silently converting to missing coverage.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
