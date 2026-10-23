"""Advisory field diagnostics for Guided validation failures (#1333).

These diagnostics NEVER normalize or accept input. The existing canonical v1/v2
validator remains the only acceptance authority; this helper is invoked only
after that validator rejects a draft.
"""
from __future__ import annotations


def field_errors(specification: dict, canonical_message: str) -> list[dict]:
    """Return bounded, deterministic and non-sensitive locations for 422 UI feedback."""
    issues: list[dict] = []

    def add(path: str, control: str, message: str, required: bool = False) -> None:
        if len(issues) < 12:
            issues.append({"field": path, "control_id": control,
                           "message": message, "required": required})

    if not isinstance(specification, dict):
        return [{"field": "specification", "control_id": "sd-advanced-json",
                 "message": "Specification must be a JSON object.", "required": True}]

    # Optional in canonical v1, but a present purpose must contain 1–1000 chars.
    # The Guided editor serializes this field, even when visually blank.
    if "purpose" in specification:
        value = specification["purpose"]
        if not isinstance(value, str) or not 1 <= len(value) <= 1000:
            add("purpose", "sd-purpose",
                "Enter a purpose (1–1000 characters), or remove this optional property in Advanced JSON.")
    if "rationale" in specification:
        value = specification["rationale"]
        if not isinstance(value, str) or not 1 <= len(value) <= 1000:
            add("rationale", "sd-rationale",
                "Rationale must be 1–1000 characters when included.")

    bdd = specification.get("behavior")
    if bdd is None:
        add("behavior", "sd-given",
            "Guided drafts require Given, When and Then statements.", True)
    elif not isinstance(bdd, dict) or set(bdd) != {"given", "when", "then"}:
        add("behavior", "sd-given",
            "Behavior must contain exactly the Given, When and Then phases.", True)
    else:
        for phase in ("given", "when", "then"):
            notes = bdd[phase]
            if (not isinstance(notes, list) or not 1 <= len(notes) <= 20 or
                    any(not isinstance(text, str) or not 1 <= len(text) <= 500 for text in notes)):
                add("behavior." + phase, "sd-" + phase,
                    phase.title() + " requires 1–20 nonempty statements of at most 500 characters each.",
                    True)

    authoring = specification.get("authoring")
    fields = {"state", "execution_policy", "evidence_provenance",
              "blocking_gaps", "review_required"}
    if not isinstance(authoring, dict) or set(authoring) != fields:
        add("authoring", "sd-advanced-json",
            "Authoring metadata must contain exactly state, execution_policy, evidence_provenance, blocking_gaps and review_required. Inspect Advanced JSON.", True)
    else:
        for key in ("state", "execution_policy", "evidence_provenance"):
            value = authoring[key]
            if not isinstance(value, str) or not 1 <= len(value) <= 160:
                add("authoring." + key, "sd-advanced-json",
                    key + " must be a nonempty string (maximum 160 characters).", True)
        if authoring["state"] != "draft":
            add("authoring.state", "sd-advanced-json",
                "Guided drafts must retain state 'draft'; validation cannot promote a draft.")
        if authoring["execution_policy"] != "read_only":
            add("authoring.execution_policy", "sd-advanced-json",
                "Only read_only design drafts are supported.")
        if authoring["review_required"] is not True:
            add("authoring.review_required", "sd-advanced-json",
                "Independent operator review cannot be waived.")
        gaps = authoring["blocking_gaps"]
        if (not isinstance(gaps, list) or len(gaps) > 30 or
                any(not isinstance(v, str) or not 1 <= len(v) <= 500 for v in gaps)):
            add("authoring.blocking_gaps", "sd-gaps",
                "Enter at most 30 nonempty blocking gaps, at most 500 characters each.")
    if not issues:
        add("specification", "sd-advanced-json",
            "Canonical validation rejected this draft: " + canonical_message[:220])
    return issues
