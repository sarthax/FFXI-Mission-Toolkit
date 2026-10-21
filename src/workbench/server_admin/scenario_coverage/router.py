"""Standalone, GET-only coverage matrix routes.

Registered by host without modifying Feature Testing's owned viewer/editor
router. No engine, runner, draft, GM or remote client dispatch dependencies.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from workbench.runtime.paths import repo_path
from .matrix import build_matrix, filter_matrix
from .authoring import add_behavior_drilldown, draft_context


def current_matrix() -> dict:
    """Load existing declared specifications and imported history read-only."""
    from workbench.core.services.feature_catalog import load_catalog
    from workbench.server_admin.feature_testing.test_specifications import specifications
    from workbench.server_admin.feature_testing.results import recent_results
    source = repo_path("data", "testing", "feature_test_readiness.json")
    readiness = json.loads(source.read_text(encoding="utf-8"))
    configured_db = os.environ.get("MISSION_TOOLKIT_TEST_RESULTS_DB", "")
    # Never call init_db or open a new writable database for this page.
    missing_db = bool(configured_db and not Path(configured_db).is_file())
    records = recent_results(configured_db, limit=500) if configured_db and not missing_db else []
    specs = specifications()
    result = build_matrix(readiness, specs, records, load_catalog(),
                          history_complete=len(records) < 500)
    result = add_behavior_drilldown(result, readiness, specs, records)
    result["results_configured"] = bool(configured_db)
    result["history_note"] = (
        "Configured results DB is unavailable; missing history is UNKNOWN, not evidence of no runs."
        if missing_db else
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

    @router.get("/context/{feature_id}/{behavior_ref}")
    def coverage_draft_context(feature_id: str, behavior_ref: str):
        """Bounded, source-declared reference only. Never save or execute."""
        try:
            source = repo_path("data", "testing", "feature_test_readiness.json")
            catalog = json.loads(source.read_text(encoding="utf-8"))
            return draft_context(catalog, feature_id, behavior_ref)
        except LookupError as exc:
            raise HTTPException(404, "Undeclared feature or behavior reference") from exc
        except ValueError as exc:
            raise HTTPException(400, "Invalid context reference") from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise HTTPException(503, "Read-only behavior source unavailable") from exc

    return router
