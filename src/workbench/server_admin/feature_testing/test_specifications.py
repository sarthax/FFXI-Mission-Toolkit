"""Versioned, allowlisted declarative test specifications; never executable code."""
from __future__ import annotations

import json
from pathlib import Path

from workbench.runtime.paths import repo_path

_SPEC_PATH = repo_path("data", "testing", "test_specifications.json")
_ALLOWED_OPERATIONS = {"equals", "nonempty", "same_rows", "all_zero"}
_ALLOWED_OBSERVATIONS = {"session", "client_bag", "client_safe", "db_bag", "db_safe",
                         "gm_active_ki", "gm_aura", "stored_furnishings",
                         "installed_layout", "client_key_items", "db_key_items"}
_ALLOWED_RUNNERS = {"xiheadless_observation_v1", "unassigned"}


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("unsupported test specification version")
    required = {"schema_version", "feature_id", "case_id", "name", "runner",
                "execution_status", "preconditions", "observations", "assertions", "cleanup"}
    optional = {"purpose", "rationale", "behavior", "steps", "authoring", "contract_v2"}
    if not required.issubset(spec) or set(spec) - required - optional:
        raise ValueError("unexpected test specification fields")
    for field in ("feature_id", "case_id", "name"):
        if not isinstance(spec[field], str) or not 1 <= len(spec[field]) <= 120:
            raise ValueError("invalid test identity")
    if spec["runner"] not in _ALLOWED_RUNNERS or spec["execution_status"] not in ("verified_runner", "design_only"):
        raise ValueError("unsupported runner or execution status")
    if spec["execution_status"] == "verified_runner" and (spec["feature_id"], spec["case_id"], spec["runner"]) != ("moghancement", "MOG-09", "xiheadless_observation_v1"):
        raise ValueError("no verified implementation for requested runner")
    for field in ("preconditions", "observations", "assertions", "cleanup"):
        if not isinstance(spec[field], list) or not 1 <= len(spec[field]) <= 20:
            raise ValueError("invalid " + field + " list")
    if any(not isinstance(x, str) or not 1 <= len(x) <= 160 for x in spec["preconditions"] + spec["cleanup"]):
        raise ValueError("invalid precondition or cleanup note")
    if len(set(spec["observations"])) != len(spec["observations"]) or any(x not in _ALLOWED_OBSERVATIONS for x in spec["observations"]):
        raise ValueError("unsupported observation type")
    names = set()
    for assertion in spec["assertions"]:
        if not isinstance(assertion, dict) or set(assertion) != {"id", "operation", "observed", "expected"}:
            raise ValueError("invalid assertion definition")
        name = assertion["id"]
        if not isinstance(name, str) or not 1 <= len(name) <= 64 or name in names:
            raise ValueError("duplicate or invalid assertion identifier")
        names.add(name)
        if assertion["operation"] not in _ALLOWED_OPERATIONS or assertion["observed"] not in spec["observations"]:
            raise ValueError("unsupported assertion operation or observation")
        if not isinstance(assertion["expected"], (str, int, list, type(None))) or isinstance(assertion["expected"], list) and len(assertion["expected"]) > 16:
            raise ValueError("invalid expected expression")
    # Narrative/step metadata is optional for legacy v1 definitions and is never
    # interpreted as an instruction to execute any action.
    for field in ("purpose", "rationale"):
        if field in spec and (not isinstance(spec[field], str) or not 1 <= len(spec[field]) <= 1000):
            raise ValueError("invalid " + field)
    if "behavior" in spec:
        behavior = spec["behavior"]
        if not isinstance(behavior, dict) or set(behavior) != {"given", "when", "then"}:
            raise ValueError("invalid BDD behavior")
        for phase in ("given", "when", "then"):
            notes = behavior[phase]
            if not isinstance(notes, list) or not 1 <= len(notes) <= 20 or any(
                not isinstance(s, str) or not 1 <= len(s) <= 500 for s in notes
            ):
                raise ValueError("invalid BDD phase: " + phase)
    if "steps" in spec:
        steps = spec["steps"]
        if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
            raise ValueError("invalid steps")
        step_ids = set()
        for step in steps:
            required_step = {"id", "title", "intent", "expected", "assertion_ids", "evidence_refs"}
            optional_step = {"confidence_note"}
            if not isinstance(step, dict) or not required_step.issubset(step) or set(step) - required_step - optional_step:
                raise ValueError("invalid step fields")
            for field in ("id", "title", "intent", "expected"):
                if not isinstance(step[field], str) or not 1 <= len(step[field]) <= 500:
                    raise ValueError("invalid step " + field)
            if step["id"] in step_ids:
                raise ValueError("duplicate step identifier")
            step_ids.add(step["id"])
            if not isinstance(step["assertion_ids"], list) or not step["assertion_ids"] or any(
                not isinstance(x, str) or x not in names for x in step["assertion_ids"]
            ):
                raise ValueError("unknown step assertion reference")
            if not isinstance(step["evidence_refs"], list) or not step["evidence_refs"] or any(
                not isinstance(x, str) or x not in spec["observations"] for x in step["evidence_refs"]
            ):
                raise ValueError("unknown step evidence reference")
            if "confidence_note" in step and (
                not isinstance(step["confidence_note"], str) or len(step["confidence_note"]) > 1000
            ):
                raise ValueError("invalid confidence note")
    if "authoring" in spec:
        a = spec["authoring"]
        if not isinstance(a, dict) or set(a) != {"state", "execution_policy", "evidence_provenance", "blocking_gaps", "review_required"}:
            raise ValueError("invalid authoring metadata")
        if any(not isinstance(a[x], str) or not 1 <= len(a[x]) <= 160 for x in ("state", "execution_policy", "evidence_provenance")):
            raise ValueError("invalid authoring metadata values")
        if not isinstance(a["review_required"], bool) or not isinstance(a["blocking_gaps"], list) or len(a["blocking_gaps"]) > 30 or any(
            not isinstance(g, str) or not 1 <= len(g) <= 500 for g in a["blocking_gaps"]
        ):
            raise ValueError("invalid authoring gaps")
    # Optional metadata remains purely descriptive: no new runner, oracle,
    # capability or permission is granted by this namespace.
    if "contract_v2" in spec:
        from .scenario_contract_v2 import validate_contract_v2
        validate_contract_v2(spec)
    return spec


def specifications() -> list[dict]:
    payload = json.loads(Path(_SPEC_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("specifications"), list):
        raise ValueError("invalid specification catalog")
    specs = [validate_spec(entry) for entry in payload["specifications"]]
    keys = [(x["feature_id"], x["case_id"]) for x in specs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate test specification")
    return specs


def specification(feature_id: str, case_id: str) -> dict | None:
    return next((s for s in specifications() if (s["feature_id"], s["case_id"]) == (feature_id, case_id)), None)
