"""Local-only, non-executable Guided Scenario Developer.

This router consumes the canonical #1259 validator and existing feature-testing
draft store; it does not define an alternate spec or execute any capabilities.
"""
from __future__ import annotations

from copy import deepcopy

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from workbench.runtime.paths import GUI_ROOT
from workbench.server_admin.feature_testing.router import load_test_catalog
from workbench.server_admin.feature_testing.spec_drafts import _validate_draft
from workbench.server_admin.feature_testing.test_specifications import (
    _ALLOWED_OBSERVATIONS, _ALLOWED_OPERATIONS, specification,
)

router = APIRouter(prefix="/scenario-developer", tags=["Scenario Developer"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))
_MAX_BYTES = 32768


def _local_origin(request: Request) -> None:
    """Validation uses only local, same-origin browser POST; no mutations."""
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Scenario authoring is local-only")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin authoring refused")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "JSON content required")
    try:
        size = int(request.headers.get("content-length", "0") or "0")
    except ValueError:
        raise HTTPException(400, "Invalid request size") from None
    if size > _MAX_BYTES:
        raise HTTPException(413, "Scenario draft exceeds 32 KiB")


class ValidationRequest(BaseModel):
    specification: dict


def editor_options() -> dict:
    """Known, source-controlled IDs only; unresolved catalog is not substituted."""
    return {
        "features": [
            {"id": item["id"], "name": item["name"]}
            for item in load_test_catalog()["features"]
        ],
        "observations": sorted(_ALLOWED_OBSERVATIONS),
        "operations": sorted(_ALLOWED_OPERATIONS),
        "catalog_status": "UNRESOLVED",
        "catalog_note": "PR #1266 catalog candidates need source/client reconciliation and security review.",
        "execution_enabled": False,
    }


def validate_editor_spec(payload: dict) -> dict:
    """Canonical validation + conservative display-only preview.

    Draft validation is not approval or an assertion evaluator. It cannot
    upgrade maturity, establish oracle completeness, or grant execution.
    """
    if not isinstance(payload, dict):
        raise ValueError("canonical scenario specification must be an object")
    spec = _validate_draft(deepcopy(payload))  # invokes canonical validate_spec
    authoring = spec.get("authoring")
    if not isinstance(authoring, dict):
        raise ValueError("BDD authoring metadata is required for guided drafts")
    if authoring.get("review_required") is not True:
        raise ValueError("operator review cannot be waived in this editor")
    if authoring.get("execution_policy") != "read_only":
        raise ValueError("only read-only design drafts are supported")
    if authoring.get("state") != "draft":
        raise ValueError("editor drafts cannot claim reviewed or executable maturity")
    safe_intents = {"observation", "read_only_comparison", "read_only_gm_diagnostic"}
    if any(step.get("intent") not in safe_intents for step in spec.get("steps", [])):
        raise ValueError("unsupported or mutating step intent")
    if not spec.get("steps") or not spec.get("behavior"):
        raise ValueError("Given/When/Then and at least one canonical step are required")
    definition_ids = {a["id"] for a in spec["assertions"]}
    linked = {a for step in spec["steps"] for a in step["assertion_ids"]}
    uncovered = sorted(definition_ids - linked)
    gaps = list(authoring.get("blocking_gaps", []))
    unknowns = [
        step["id"] for step in spec["steps"]
        if "unknown" in step.get("expected", "").casefold()
    ]
    preview = {
        "title": spec["name"],
        "purpose": spec.get("purpose", "UNKNOWN — purpose missing"),
        "rationale": spec.get("rationale", "UNKNOWN — rationale missing"),
        "feature_id": spec["feature_id"],
        "case_id": spec["case_id"],
        "behavior": spec["behavior"],
        "steps": [{
            "id": step["id"], "title": step["title"], "expected": step["expected"],
            "assertion_ids": step["assertion_ids"],
            "evidence_refs": step["evidence_refs"], "confidence_note": step.get("confidence_note"),
            "verdict": "UNKNOWN", "observed": "UNKNOWN — no independently verified observation",
        } for step in spec["steps"]],
        "blocking_gaps": gaps,
        "unmapped_assertions": uncovered,
        "unresolved_expected_steps": unknowns,
        "recorded_verdict": None,
        "recalculated_verdict": None,
        "independent_verification": "NOT_ESTABLISHED",
        "execution_enabled": False,
        "operator_review_required": True,
        "maturity": "DESIGN_ONLY — not reviewed, not executable",
        "catalog_identity": "UNRESOLVED",
    }
    return {"valid": True, "canonical_specification": spec, "preview": preview,
            "execution_enabled": False, "operator_review_required": True,
            "warnings": (["Assertions without step coverage: " + ", ".join(uncovered)] if uncovered else [])
                        + (["UNKNOWN expected oracle in " + ", ".join(unknowns)] if unknowns else [])
                        + gaps}


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def editor_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="scenario_developer.html",
        context={"title": "Guided Scenario Developer"},
    )


@router.get("/options", include_in_schema=False)
def options(request: Request):
    return editor_options()


@router.get("/seed/{feature_id}/{case_id}", include_in_schema=False)
def seed(request: Request, feature_id: str, case_id: str):
    """Read a published spec for fork/copy only; it is never editable in place."""
    spec = specification(feature_id, case_id)
    if spec is None:
        raise HTTPException(404, "No canonical specification found")
    return {"specification": spec, "copy_only": True, "execution_enabled": False}


@router.post("/validate", include_in_schema=False)
def validate(request: Request, body: ValidationRequest):
    _local_origin(request)
    try:
        return validate_editor_spec(body.specification)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
