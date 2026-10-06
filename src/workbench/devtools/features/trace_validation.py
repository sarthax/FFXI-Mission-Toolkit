"""Fail-closed real-object validation harness for Feature Trace.

This module does not add provider semantics. It drives the canonical resolver/trace pipeline against
explicit representative objects and classifies the result as PASS, CONTRACT_GAP, UNAVAILABLE, or
AMBIGUOUS. Missing data is not treated as a provider defect and ambiguous roots are never selected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from workbench.devtools.features import trace as feature_trace
from workbench.devtools.features.trace_benchmarks import SCENARIO_BY_ID, evaluate_trace


@dataclass(frozen=True)
class TraceValidationCase:
    case_id: str
    scenario_id: str
    query: str | None = None
    root: str | None = None
    depth: int = 4
    direction: str = "both"

    def __post_init__(self) -> None:
        if not self.case_id:
            raise ValueError("case_id is required")
        if self.scenario_id not in SCENARIO_BY_ID:
            raise ValueError(f"unknown Feature Trace scenario: {self.scenario_id}")
        if bool(self.query) == bool(self.root):
            raise ValueError("provide exactly one of query or root")
        if self.depth < 1:
            raise ValueError("depth must be >= 1")


@dataclass(frozen=True)
class ClosureValidationCase:
    """Exact provider-root closure contract.

    Each required link is ``(relationship, target_node)``. Use ``None`` for target_node only when
    the relationship itself is the contract; otherwise exact target identity is preferred.
    """

    case_id: str
    root: str
    required_links: tuple[tuple[str, str | None], ...]
    forbidden_relationships: tuple[str, ...] = ()
    depth: int = 1
    direction: str = "both"

    def __post_init__(self) -> None:
        if not self.case_id or not self.root:
            raise ValueError("case_id and root are required")
        if not self.required_links and not self.forbidden_relationships:
            raise ValueError("closure case requires at least one required or forbidden relationship")
        if self.depth < 1:
            raise ValueError("depth must be >= 1")


def _base_result(case: TraceValidationCase) -> dict:
    scenario = SCENARIO_BY_ID[case.scenario_id]
    return {
        "case_id": case.case_id,
        "scenario_id": case.scenario_id,
        "scenario_label": scenario.label,
        "query": case.query,
        "requested_root": case.root,
        "resolved_root": None,
        "resolution": None,
        "status": "UNAVAILABLE",
        "passed": False,
        "evaluation": None,
        "diagnostics": [],
    }


def validate_case(graph_con, case: TraceValidationCase, catalog_con=None) -> dict:
    """Run one representative object through the canonical Feature Trace path.

    Query-backed cases use the normal resolver. NOT_FOUND is UNAVAILABLE and AMBIGUOUS remains
    AMBIGUOUS; neither is converted into a contract failure. Root-backed cases intentionally skip
    fuzzy search and trace the caller-supplied exact node/provider root.
    """
    result = _base_result(case)
    scenario = SCENARIO_BY_ID[case.scenario_id]

    root = case.root
    if case.query is not None:
        resolution = feature_trace.resolve_query(graph_con, case.query, catalog_con)
        result["resolution"] = resolution
        status = str(resolution.get("status") or "")
        if status == "NOT_FOUND":
            result["diagnostics"].append("Representative object is not indexed in this data set.")
            return result
        if status != "RESOLVED" or not resolution.get("root"):
            result["status"] = "AMBIGUOUS"
            result["diagnostics"].append(
                "Representative query did not resolve uniquely; no trace root was selected."
            )
            return result
        root = str(resolution["root"])

    result["resolved_root"] = root
    trace_result = feature_trace.trace(
        graph_con,
        str(root),
        int(case.depth),
        case.direction,
        catalog_con,
        mode=scenario.mode,
    )
    evaluation = evaluate_trace(trace_result, scenario)
    result["evaluation"] = evaluation
    if evaluation.get("passed"):
        result["status"] = "PASS"
        result["passed"] = True
    else:
        result["status"] = "CONTRACT_GAP"
        failed = [name for name, passed in (evaluation.get("checks") or {}).items() if not passed]
        if failed:
            result["diagnostics"].append(
                "Feature Trace returned the object but missed required scenario checks: "
                + ", ".join(failed)
            )
    return result


def validate_closure_case(graph_con, case: ClosureValidationCase, catalog_con=None) -> dict:
    """Validate exact provider→target navigation without translating it into canonical edges."""
    info = feature_trace.node_info(graph_con, case.root, catalog_con)
    result = {
        "case_id": case.case_id,
        "requested_root": case.root,
        "status": "UNAVAILABLE",
        "passed": False,
        "required_links": [list(row) for row in case.required_links],
        "forbidden_relationships": list(case.forbidden_relationships),
        "observed_links": [],
        "missing_links": [],
        "forbidden_observed": [],
        "diagnostics": [],
    }
    if not info.get("known"):
        result["diagnostics"].append("Exact provider root is not indexed in this data set.")
        return result

    traced = feature_trace.trace(
        graph_con,
        case.root,
        int(case.depth),
        case.direction,
        catalog_con,
    )
    links = list(traced.get("provider_relationships") or ())
    observed = {
        (str(row.get("relationship") or ""), str(row.get("target_node") or ""))
        for row in links
    }
    result["observed_links"] = [
        {"relationship": relationship, "target_node": target}
        for relationship, target in sorted(observed)
    ]

    missing = []
    for relationship, target in case.required_links:
        matched = any(
            observed_relationship == relationship
            and (target is None or observed_target == target)
            for observed_relationship, observed_target in observed
        )
        if not matched:
            missing.append({"relationship": relationship, "target_node": target})
    forbidden = sorted({
        relationship
        for relationship, _target in observed
        if relationship in case.forbidden_relationships
    })
    result["missing_links"] = missing
    result["forbidden_observed"] = forbidden
    if missing or forbidden:
        result["status"] = "CONTRACT_GAP"
        if missing:
            result["diagnostics"].append("Required exact provider closure link is missing.")
        if forbidden:
            result["diagnostics"].append("A relationship required to fail closed was emitted.")
        return result

    result["status"] = "PASS"
    result["passed"] = True
    return result


def _summary(rows: list[dict]) -> dict:
    counts = {name: 0 for name in ("PASS", "CONTRACT_GAP", "UNAVAILABLE", "AMBIGUOUS")}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    attempted = counts["PASS"] + counts["CONTRACT_GAP"]
    return {
        "cases": rows,
        "counts": counts,
        "case_count": len(rows),
        "attempted_contract_count": attempted,
        "passed_contract_count": counts["PASS"],
        "all_attempted_passed": counts["CONTRACT_GAP"] == 0,
        "evidence_policy": {
            "missing_is_failure": False,
            "ambiguous_is_auto_selected": False,
            "provider_semantics_added": False,
        },
    }


def validate_cases(graph_con, cases: Iterable[TraceValidationCase], catalog_con=None) -> dict:
    return _summary([validate_case(graph_con, case, catalog_con) for case in cases])


def validate_closure_cases(graph_con, cases: Iterable[ClosureValidationCase], catalog_con=None) -> dict:
    return _summary([validate_closure_case(graph_con, case, catalog_con) for case in cases])


__all__ = [
    "TraceValidationCase",
    "ClosureValidationCase",
    "validate_case",
    "validate_cases",
    "validate_closure_case",
    "validate_closure_cases",
]
