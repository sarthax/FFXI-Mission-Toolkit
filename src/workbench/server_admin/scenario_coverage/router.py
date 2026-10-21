"""Standalone, GET-only coverage matrix routes.

Registered by host without modifying Feature Testing's owned viewer/editor
router. No engine, runner, draft, GM or remote client dispatch dependencies.
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException, Request

from workbench.runtime.paths import repo_path
from .matrix import build_matrix, filter_matrix


def current_matrix() -> dict:
    """Load existing declared specifications and imported history read-only."""
    from workbench.core.services.feature_catalog import load_catalog
    from workbench.server_admin.feature_testing.test_specifications import specifications
    from workbench.server_admin.feature_testing.results import recent_results
    source = repo_path("data", "testing", "feature_test_readiness.json")
    readiness = json.loads(source.read_text(encoding="utf-8"))
    configured_db = os.environ.get("MISSION_TOOLKIT_TEST_RESULTS_DB", "")
    # Never call init_db or open a new writable database for this page.
    records = recent_results(configured_db, limit=500) if configured_db else []
    result = build_matrix(readiness, specifications(), records, load_catalog(),
                          history_complete=len(records) < 500)
    result["results_configured"] = bool(configured_db)
    result["history_note"] = (
        "Only the 500 most recent imported records were loaded; do not infer missing runs."
        if len(records) >= 500 else
        "No evidence DB configured; an empty results view is not proof no runs exist."
        if not configured_db else
        "Imported records shown are not independent authentication of client/server state."
    )
    return result


def create_coverage_router(templates) -> APIRouter:
    router = APIRouter(prefix="/feature-testing/coverage", tags=["Feature Testing Coverage"])

    def view(domain: str = "", readiness: str = "") -> dict:
        try:
            return filter_matrix(current_matrix(), domain=domain, readiness=readiness)
        except ValueError as exc:
            raise HTTPException(400, "Invalid coverage filter or catalog contract") from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise HTTPException(503, "Coverage source unavailable; unknown, not empty") from exc

    @router.get("")
    def coverage_page(request: Request, domain: str = "", readiness: str = ""):
        return templates.TemplateResponse(
            request=request,
            name="feature_testing_coverage.html",
            context={"title": "Feature-to-Scenario Coverage", "matrix": view(domain, readiness)},
        )

    @router.get("/model.json")
    def coverage_json(domain: str = "", readiness: str = ""):
        return view(domain, readiness)

    return router
