"""Local-only, non-executable Guided Scenario Developer.

This router consumes the canonical #1259 validator and existing feature-testing
draft store; it does not define an alternate spec or execute any capabilities.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .context_handoff import coverage_context, inspect_evidence_review
from workbench.captures.scenario_readiness_viewer import inspect_paired_readiness
from workbench.runtime.paths import GUI_ROOT
from workbench.runtime.legacy_settings import get_dsp_root
from workbench.server_admin.scenario_authoring.catalog_adapter import (
    CatalogUnavailable, search_catalog,
)
from workbench.server_admin.feature_testing.scenario_presentation import scenario_presentation
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
        "catalog_note": "DSP source candidates only; all identities and action permissions need human reconciliation.",
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
        "reader_view": scenario_presentation(spec),
    }
    return {"valid": True, "canonical_specification": spec, "preview": preview,
            "reader_view": preview["reader_view"],
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


def catalog_candidates(kind: str, query: str, limit: int = 12) -> dict:
    """Bounded DSP-only discovery with no path supplied by a web caller.

    The configured DSP checkout is an application setting, not a client input.
    Missing sources are unavailable, never an empty 'verified' catalog.
    """
    if kind not in {"item", "keyitem", "npc", "mob", "zone", "gm"}:
        raise ValueError("Choose item, keyitem, npc, mob, zone or gm")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Catalog results must be limited to 1-20")
    root = get_dsp_root()
    if not root or not Path(root).is_dir():
        raise CatalogUnavailable(
            "No DSP source checkout configured. Configure dsp_server_path in Toolkit settings first."
        )
    return search_catalog(root, kind, query, limit=limit)


@router.get("/catalog/search", include_in_schema=False)
def search_editor_catalog(request: Request, kind: str, query: str, limit: int = 12):
    """Local browser GET only; returns unverified candidate metadata, never commands."""
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Catalog search is local-only")
    if request.headers.get("x-requested-with") != "toolkit-ui":
        raise HTTPException(403, "Catalog search requires the local editor")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin catalog search refused")
    try:
        return catalog_candidates(kind, query, limit)
    except CatalogUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc) + " Resolve: " + _validation_help(str(exc))) from exc


class CoverageReferenceRequest(BaseModel):
    context_ref: str
    source: dict


@router.post("/handoff/coverage/inspect", include_in_schema=False)
def inspect_coverage_handoff(request: Request, body: CoverageReferenceRequest):
    """Check the bounded existing coverage endpoint response; no draft writes."""
    _local_origin(request)
    try:
        return coverage_context(body.source, body.context_ref)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


class EvidenceReviewRequest(BaseModel):
    review: dict


@router.post("/handoff/evidence/inspect", include_in_schema=False)
def inspect_evidence_handoff(request: Request, body: EvidenceReviewRequest):
    """Validate *untrusted* exported review JSON; never store or approve it."""
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Evidence authoring is local-only")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin evidence import refused")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "Evidence review requires JSON")
    try:
        size = int(request.headers.get("content-length", "0") or "0")
    except ValueError:
        raise HTTPException(400, "Invalid payload size") from None
    # Offline Reviewer allows up to 4 MB of indexed projection, plus the
    # browser's bounded step/binding decision envelope. Validate the parsed
    # body as well, since Content-Length is not a security boundary.
    # Browser JSON.stringify sends compact UTF-8 rather than Python's default
    # ASCII-escaped, space-padded JSON. Count the complete request envelope;
    # otherwise valid Unicode captures can be incorrectly rejected.
    encoded = json.dumps({"review": body.review}, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    if size > 5_000_000 or len(encoded) > 5_000_000:
        raise HTTPException(413, "Evidence review too large; narrow the offline capture export")
    try:
        return inspect_evidence_review(body.review)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(422, "Unsupported, missing, modified or incompatible evidence review: " + str(exc)) from exc


class PairedReadinessRequest(BaseModel):
    review: dict
    sidecar: dict


@router.post("/handoff/readiness/inspect", include_in_schema=False)
def inspect_readiness_handoff(request: Request, body: PairedReadinessRequest):
    """Separate local-only, read-only verifier; never use canonical importer."""
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Capture readiness inspection is local-only")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin capture inspection refused")
    if request.headers.get("x-requested-with") != "toolkit-ui":
        raise HTTPException(403, "Local editor request required")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "Capture readiness requires JSON")
    try:
        size = int(request.headers.get("content-length", "0") or "0")
    except ValueError:
        raise HTTPException(400, "Invalid payload size") from None
    # Two separate files, each bounded by the verifier to 4.5 MB; bound
    # the complete wire envelope independently, including Unicode encoding.
    encoded = json.dumps({"review": body.review, "sidecar": body.sidecar},
                         ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if size > 9_100_000 or len(encoded) > 9_100_000:
        raise HTTPException(413, "Selected capture pair too large")
    try:
        return inspect_paired_readiness(body.review, body.sidecar)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise HTTPException(422, "Capture readiness pair rejected: " + str(exc)) from exc


@router.get("/seed/{feature_id}/{case_id}", include_in_schema=False)
def seed(request: Request, feature_id: str, case_id: str):
    """Read a published spec for fork/copy only; it is never editable in place."""
    spec = specification(feature_id, case_id)
    if spec is None:
        raise HTTPException(404, "No canonical specification found")
    return {"specification": spec, "copy_only": True, "execution_enabled": False}


def _validation_help(reason: str) -> str:
    """Expose next actionable edit without weakening canonical validation."""
    low = reason.casefold()
    if "duplicate step" in low:
        return "Use a different stable step ID; reorder existing steps without changing their IDs."
    if "unknown step assertion" in low:
        return "Choose an assertion ID already defined in this scenario, or add its definition."
    if "unknown step evidence" in low or "unsupported observation" in low:
        return "Select supported observations and bind each step to an existing observation name."
    if "duplicate" in low and "assertion" in low:
        return "Give each assertion a unique ID and rebind the affected steps."
    if "invalid bdd" in low or "bdd phase" in low:
        return "Enter at least one Given, When and Then statement (one per line)."
    if "unrecognized" in low or "unexpected" in low or "invalid step fields" in low:
        return "Remove unsupported JSON fields; use only the canonical schema, not a separate action format."
    if "published" in low:
        return "Clone the published scenario with a new case ID; published definitions cannot be overwritten."
    if "runner" in low or "design_only" in low or "review" in low or "mutating" in low:
        return "Keep this draft unassigned, design-only, read-only and review-required."
    return "Review required fields, lengths and source gaps; inspect the canonical specification."


@router.post("/validate", include_in_schema=False)
def validate(request: Request, body: ValidationRequest):
    _local_origin(request)
    try:
        return validate_editor_spec(body.specification)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
