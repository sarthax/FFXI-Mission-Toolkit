"""Pure, read-only scenario presentation adapter for legacy and optional BDD specs.

Never treats a stored verdict, an evaluator PASS, or a runner binding as
independent gameplay verification. No database, executor, or file writes.
"""
from __future__ import annotations


def _mapping(value):
    return value if isinstance(value, dict) else {}


def scenario_presentation(spec: dict | None, reevaluation: dict | None = None) -> dict:
    """Build display-only steps from the canonical specification and imported evidence.

    BDD fields are optional pending #1259/#1263. Legacy specifications expose
    ordered assertion rows, explicitly labeled as *not* authored BDD steps.
    """
    if not isinstance(spec, dict):
        return {"available": False, "steps": [], "behavior": {}, "blocking_gaps": [],
                "warnings": ["No canonical specification available; outcome UNKNOWN."]}
    reevaluation = _mapping(reevaluation)
    normalized = _mapping(reevaluation.get("normalization"))
    observations = _mapping(normalized.get("observations"))
    field_sources = _mapping(normalized.get("field_sources"))
    evaluation = _mapping(reevaluation.get("evaluation"))
    evaluated = {
        row["id"]: row for row in evaluation.get("assertions", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    definitions = {
        row["id"]: row for row in spec.get("assertions", [])
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    }
    authored_steps = spec.get("steps")
    has_authored_steps = isinstance(authored_steps, list) and bool(authored_steps)
    if has_authored_steps:
        step_inputs = authored_steps
    else:
        # One display-only row per original assertion. This is *not* an
        # invented BDD scenario or evidence; ids and references are canonical.
        step_inputs = [{
            "id": "assertion:" + assertion_id,
            "title": "Assertion: " + assertion_id.replace("_", " "),
            "intent": "legacy_assertion_only",
            "expected": None,
            "assertion_ids": [assertion_id],
            "evidence_refs": [definition.get("observed")] + (
                [definition["expected"]] if definition.get("expected") in
                ("db_bag", "db_safe") else []
            ),
        } for assertion_id, definition in definitions.items()]

    steps = []
    for position, entry in enumerate(step_inputs, 1):
        if not isinstance(entry, dict):
            continue
        ids = entry.get("assertion_ids", [])
        ids = ids if isinstance(ids, list) else []
        assertion_rows = []
        for assertion_id in ids:
            definition = definitions.get(assertion_id)
            outcome = evaluated.get(assertion_id)
            if definition is None:
                assertion_rows.append({"id": assertion_id, "status": "UNKNOWN",
                                       "reason": "Unknown assertion reference",
                                       "operation": None, "expected": None,
                                       "observed": None, "observed_available": False})
                continue
            observed_field = definition.get("observed")
            assertion_rows.append({
                "id": assertion_id,
                "status": outcome.get("status", "UNKNOWN") if outcome else "UNKNOWN",
                "reason": outcome.get("reason", "Not evaluated") if outcome else "Not evaluated",
                "operation": definition.get("operation"),
                "observed_field": observed_field,
                "expected_field": definition.get("expected"),
                "expected": outcome.get("expected") if outcome else definition.get("expected"),
                "observed": outcome.get("observed") if outcome else None,
                "observed_available": observed_field in observations,
            })
        states = {a["status"] for a in assertion_rows}
        verdict = ("FAIL" if "FAIL" in states else
                   "BLOCKED" if "BLOCKED" in states else
                   "UNKNOWN" if not states or "UNKNOWN" in states else "PASS")
        evidence_refs = entry.get("evidence_refs", [])
        evidence_refs = evidence_refs if isinstance(evidence_refs, list) else []
        provenance = [{
            "field": field,
            "available": field in observations,
            "source": field_sources.get(field),
            "value": observations.get(field),
        } for field in evidence_refs if isinstance(field, str)]
        steps.append({
            "number": position, "id": entry.get("id"), "title": entry.get("title"),
            "intent": entry.get("intent"), "expected": entry.get("expected"),
            "status": verdict, "assertions": assertion_rows, "provenance": provenance,
            "confidence_note": entry.get("confidence_note"),
        })

    authoring = _mapping(spec.get("authoring"))
    behavior = _mapping(spec.get("behavior"))
    warnings = normalized.get("warnings", [])
    warnings = list(warnings) if isinstance(warnings, list) else []
    # Never infer an independently verified result from a client-supplied bit
    # or the normalized report. Verification needs a separate trusted contract.
    return {
        "available": True,
        "purpose": spec.get("purpose") or spec.get("name"),
        "rationale": spec.get("rationale"),
        "behavior": {
            phase: behavior[phase] if isinstance(behavior.get(phase), list) else []
            for phase in ("given", "when", "then")
        },
        "legacy": not has_authored_steps,
        "preconditions": spec.get("preconditions", []),
        "cleanup": spec.get("cleanup", []),
        "steps": steps,
        "assertion_count": len(definitions),
        "mapped_assertion_count": len({
            a["id"] for step in steps for a in step["assertions"]
            if a["id"] in definitions
        }),
        "blocking_gaps": authoring.get("blocking_gaps", []),
        "authoring_state": authoring.get("state", "unspecified"),
        "review_required": authoring.get("review_required", True),
        "recorded_verdict": reevaluation.get("recorded_verdict"),
        "recalculated_verdict": evaluation.get("verdict"),
        "reevaluation_error": reevaluation.get("error"),
        "warnings": warnings,
        "missing_fields": normalized.get("missing_fields", []),
        "independent_verification": "NOT_ESTABLISHED",
        "source": normalized.get("source"),
    }
