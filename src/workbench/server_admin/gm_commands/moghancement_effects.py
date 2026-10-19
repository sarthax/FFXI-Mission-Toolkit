"""Evaluate Moghancement modifier snapshots without performing gameplay actions."""
from __future__ import annotations


def evaluate_modifiers(before: dict, during: dict, after: dict, expected: dict) -> dict:
    """Compare modifier *deltas* with baseline; detects leakage on removal.

    Inputs are mapping of numeric modifier name -> integer value as returned by
    an approved read-only server diagnostic. A missing value is not zero.
    """
    if not all(isinstance(v, dict) for v in (before, during, after, expected)):
        raise ValueError("modifier snapshots must be dictionaries")
    failures = []
    diffs = {}
    for name, delta in expected.items():
        if not isinstance(name, str) or not name or type(delta) is not int:
            raise ValueError("expected entries must be named integer deltas")
        values = [s.get(name) for s in (before, during, after)]
        if any(type(x) is not int for x in values):
            failures.append({"modifier": name, "reason": "missing_or_invalid_observation"})
            continue
        b, d, a = values
        diffs[name] = {"baseline": b, "active": d, "removed": a,
                       "observed_delta": d-b, "expected_delta": delta}
        if d-b != delta:
            failures.append({"modifier": name, "reason": "wrong_active_delta",
                             "observed": d-b, "expected": delta})
        if a != b:
            failures.append({"modifier": name, "reason": "modifier_not_restored",
                             "observed": a, "expected": b})
    return {"verdict": "BLOCKED" if any(f["reason"] == "missing_or_invalid_observation" for f in failures)
            else "FAIL" if failures else "PASS", "observations": diffs, "failures": failures}


def evaluate_replacement(baseline: dict, old_active: dict, new_active: dict,
                         old_effect: dict, new_effect: dict) -> dict:
    """Prove the old KI effect is removed and only the new effect remains."""
    names = set(old_effect) | set(new_effect)
    if not names:
        raise ValueError("no expected modifier effects")
    failures = []
    for name in sorted(names):
        values = [s.get(name) for s in (baseline, old_active, new_active)]
        if any(type(v) is not int for v in values):
            failures.append({"modifier": name, "reason": "missing_or_invalid_observation"})
            continue
        b, o, n = values
        if o-b != old_effect.get(name, 0):
            failures.append({"modifier": name, "reason": "old_effect_mismatch"})
        if n-b != new_effect.get(name, 0):
            failures.append({"modifier": name, "reason": "replacement_leak_or_wrong_effect"})
    return {"verdict": "BLOCKED" if any(f["reason"] == "missing_or_invalid_observation" for f in failures)
            else "FAIL" if failures else "PASS", "failures": failures}
