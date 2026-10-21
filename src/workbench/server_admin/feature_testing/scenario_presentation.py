"""Pure, read-only scenario presentation adapter for legacy and optional BDD specs.

Never treats a stored verdict, an evaluator PASS, or a runner binding as
independent gameplay verification. No database, executor, or file writes.
"""
from __future__ import annotations


def _mapping(value):
    return value if isinstance(value, dict) else {}


_SOURCE_LABELS = (
    ("client_", "Client-observed"),
    ("db_", "Server database"),
    ("gm_", "GM diagnostic"),
)


def source_kind(field) -> str:
    """Label an observation by its own field-name prefix, nothing more.

    This describes where the *runner says* the value came from. It is not
    authentication: every label is imported, runner-authored provenance.
    """
    if not isinstance(field, str):
        return "Source unspecified"
    for prefix, label in _SOURCE_LABELS:
        if field.startswith(prefix):
            return label
    if field == "session":
        return "Runner session report"
    return "Runner-reported (source unspecified)"


def _outcome_kind(status: str, observed_available: bool) -> str:
    """Separate a real failed assertion from a missing or unsupported observation."""
    if not observed_available:
        return "NOT_OBSERVED"
    if status == "FAIL":
        return "FAILED_ASSERTION"
    if status == "PASS":
        return "MATCHED_IMPORTED"
    if status == "BLOCKED":
        return "BLOCKED_UNSUPPORTED"
    return "NOT_EVALUATED"


def _lifecycle(authoring: dict, run_id: str | None, spec: dict) -> list[dict]:
    state = authoring.get("state", "unspecified")
    review = "review required" if authoring.get("review_required", True) else "reviewed"
    return [
        {"stage": "Definition", "state": "Published canonical specification, read-only in this view"},
        {"stage": "Draft", "state": "Not shown here; edits happen in the Scenario Developer as separate design-only drafts"},
        {"stage": "Validated version", "state": f"Authoring state {state}; {review}"},
        {"stage": "Selected run", "state": (f"Run {run_id}: imported results shown below" if run_id
                                           else "None selected: every outcome is UNKNOWN")},
        {"stage": "Historical revisions", "state": "Runs pin DSP/headless/toolkit commits; a specification revision is not pinned by the importer"},
    ]


def scenario_presentation(spec: dict | None, reevaluation: dict | None = None,
                          run_id: str | None = None) -> dict:
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
            status = outcome.get("status") if outcome else None
            status = status if status in ("PASS", "FAIL", "BLOCKED") else "UNKNOWN"
            assertion_rows.append({
                "id": assertion_id,
                "status": status,
                "reason": outcome.get("reason", "Not evaluated") if outcome else "Not evaluated",
                "operation": definition.get("operation"),
                "observed_field": observed_field,
                "expected_field": definition.get("expected"),
                "expected": outcome.get("expected") if outcome else definition.get("expected"),
                "observed": outcome.get("observed") if outcome else None,
                "observed_available": observed_field in observations,
                "outcome_kind": _outcome_kind(status, observed_field in observations),
                "source_kind": source_kind(observed_field),
            })
        states = {a["status"] for a in assertion_rows}
        verdict = ("FAIL" if "FAIL" in states else
                   "BLOCKED" if "BLOCKED" in states else
                   "PASS" if states == {"PASS"} else "UNKNOWN")
        evidence_refs = entry.get("evidence_refs", [])
        evidence_refs = evidence_refs if isinstance(evidence_refs, list) else []
        provenance = [{
            "field": field,
            "available": field in observations,
            "source": field_sources.get(field),
            "value": observations.get(field),
            "source_kind": source_kind(field),
        } for field in evidence_refs if isinstance(field, str)]
        kinds = {a.get("outcome_kind") for a in assertion_rows if "outcome_kind" in a}
        steps.append({
            "number": position, "id": entry.get("id"), "title": entry.get("title"),
            "intent": entry.get("intent"), "expected": entry.get("expected"),
            "status": verdict, "assertions": assertion_rows, "provenance": provenance,
            "source_kinds": sorted({p["source_kind"] for p in provenance}),
            "has_failed_assertion": "FAILED_ASSERTION" in kinds,
            "has_missing_observation": "NOT_OBSERVED" in kinds,
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
        "unmapped_assertions": sorted(set(definitions) - {
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
        "selected_run_id": run_id,
        "lifecycle": _lifecycle(authoring, run_id, spec),
    }
