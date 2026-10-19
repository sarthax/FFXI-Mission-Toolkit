"""Deterministic, read-only evaluator for versioned observation assertions.

Input observations are untrusted measurements. Missing or ambiguous data is BLOCKED,
not PASS. This does not launch a runner, access SQL, or certify observations.
"""
from __future__ import annotations

from .test_specifications import validate_spec

_MISSING = object()


def _reference(expected, observations, context):
    if isinstance(expected, str) and expected in {"approved_charid", "db_bag", "db_safe"}:
        return (context if expected == "approved_charid" else observations).get(expected, _MISSING)
    return expected


def _rows(value):
    if not isinstance(value, list):
        return _MISSING
    rows = []
    for row in value:
        if not isinstance(row, (tuple, list)) or len(row) != 3 or any(type(v) is not int for v in row):
            return _MISSING
        rows.append(tuple(row))
    # Duplicate slot entries cannot prove equality.
    if len({row[0] for row in rows}) != len(rows):
        return _MISSING
    return sorted(rows)


def evaluate(spec: dict, observations: dict, *, context: dict | None = None) -> dict:
    validate_spec(spec)
    if not isinstance(observations, dict) or not isinstance(context, (dict, type(None))):
        raise ValueError("observations and context must be objects")
    context = context or {}
    results = []
    for assertion in spec["assertions"]:
        observed = observations.get(assertion["observed"], _MISSING)
        expected = _reference(assertion["expected"], observations, context)
        status, reason = "BLOCKED", "missing or invalid observation"
        if observed is not _MISSING and expected is not _MISSING:
            op = assertion["operation"]
            if op == "equals":
                if type(observed) is type(expected) and type(observed) in (int, str, list):
                    status = "PASS" if observed == expected else "FAIL"
                    reason = "values equal" if status == "PASS" else "values differ"
                else:
                    reason = "incompatible comparison types"
            elif op == "nonempty":
                if isinstance(observed, (list, dict, str)):
                    status = "PASS" if len(observed) > 0 else "FAIL"
                    reason = "collection populated" if status == "PASS" else "collection empty"
                else:
                    reason = "expected collection"
            elif op == "all_zero":
                if isinstance(observed, list) and len(observed) == 8 and all(type(v) is int for v in observed):
                    status = "PASS" if all(v == 0 for v in observed) else "FAIL"
                    reason = "all eight zero" if status == "PASS" else "nonzero aura present"
                else:
                    reason = "expected eight integer aura values"
            elif op == "same_rows":
                left, right = _rows(observed), _rows(expected)
                if left is not _MISSING and right is not _MISSING:
                    status = "PASS" if left == right else "FAIL"
                    reason = "inventory rows equal" if status == "PASS" else "inventory rows differ"
                else:
                    reason = "missing or invalid inventory rows"
        results.append({"id": assertion["id"], "operation": assertion["operation"],
                        "status": status, "reason": reason,
                        "expected": None if expected is _MISSING else expected,
                        "observed": None if observed is _MISSING else observed})
    statuses = {r["status"] for r in results}
    verdict = "FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS"
    return {"schema_version": 1, "feature_id": spec["feature_id"], "case_id": spec["case_id"],
            "verdict": verdict, "assertions": results,
            "source": "deterministic_evaluation_of_supplied_unverified_observations",
            "execution_enabled": False}
