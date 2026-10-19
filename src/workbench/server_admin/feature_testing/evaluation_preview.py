"""Bounded, nonpersisting evaluation of explicitly supplied synthetic observations."""
from __future__ import annotations
from .assertion_engine import evaluate
from .test_specifications import specification

def preview(feature_id: str, case_id: str, observations: dict, context: dict | None = None) -> dict:
    spec = specification(feature_id, case_id)
    if spec is None:
        raise ValueError("unknown test specification")
    if not isinstance(observations, dict) or len(observations) > 20:
        raise ValueError("invalid observation object")
    if context is not None and (not isinstance(context, dict) or set(context) - {"approved_charid"}):
        raise ValueError("unsupported evaluation context")
    result = evaluate(spec, observations, context=context)
    result["preview_only"] = True
    result["persisted"] = False
    result["evidence_authenticated"] = False
    result["warning"] = "Evaluates supplied data, not independently captured game state or verified test execution."
    return result
