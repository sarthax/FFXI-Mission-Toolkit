"""Evaluate a design-only draft against supplied observations without execution."""
from __future__ import annotations
from .assertion_engine import evaluate
from .test_specifications import validate_spec


def preview_draft(spec: dict, observations: dict, context: dict | None = None) -> dict:
    if not isinstance(spec, dict) or spec.get("runner") != "unassigned" or spec.get("execution_status") != "design_only":
        raise ValueError("Only non-executable design drafts can be previewed")
    validate_spec(spec)
    if not isinstance(observations, dict) or len(observations) > 20:
        raise ValueError("Invalid observation preview")
    if context is not None and (not isinstance(context, dict) or set(context) - {"approved_charid"}):
        raise ValueError("Unsupported context")
    result = evaluate(spec, observations, context=context)
    result.update(preview_only=True, persisted=False, evidence_authenticated=False,
                  note="Supplied observations only; no runtime capture or execution")
    return result
