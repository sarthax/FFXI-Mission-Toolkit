"""Fail-closed, read-only supervisor endpoints for local tool integration.

No database writes, shell commands, free-form SQL, or raw MCP controls.
Disabled entirely unless a local operator configures a bearer token.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from workbench.server_admin.feature_testing.router import _results_db, _run_summary
from workbench.server_admin.feature_testing.results import recent_results
from .log_diagnostics import read_log
from .service_health import service_health

router = APIRouter(prefix="/api/supervisor", tags=["Local Test Supervisor"])


def _authorize(authorization: str | None) -> None:
    expected = os.environ.get("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "")
    if len(expected) < 32 or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Supervisor gateway not configured or unauthorized")
    if not hmac.compare_digest(authorization[7:], expected):
        raise HTTPException(status_code=403, detail="Supervisor gateway not configured or unauthorized")


@router.get("/health", operation_id="supervisor_health")
def health(authorization: str | None = Header(default=None)):
    _authorize(authorization)
    return {"gateway": "ready", "execution_enabled": False,
            "results_configured": bool(_results_db())}


@router.get("/test-runs", operation_id="supervisor_test_runs")
def test_runs(authorization: str | None = Header(default=None)):
    _authorize(authorization)
    path = _results_db()
    rows = recent_results(path, limit=100) if path else []
    return {"runs": _run_summary(rows), "execution_enabled": False,
            "note": "Imported records are not independently authenticated"}


@router.get("/failed-assertions", operation_id="supervisor_failed_assertions")
def failed_assertions(authorization: str | None = Header(default=None)):
    _authorize(authorization)
    path = _results_db()
    rows = recent_results(path, limit=100) if path else []
    return {"results": [
        {"run_id": r["run_id"], "feature_id": r["feature_id"],
         "case_id": r["case_id"], "stage": r["stage"],
         "verdict": r["verdict"], "observed_at": r["observed_at"],
         "evaluation": r["evidence"].get("evaluation", {})}
        for r in rows if r["verdict"] in ("FAIL", "BLOCKED")
    ], "limit": 100}

@router.get("/log-errors", operation_id="supervisor_log_errors")
def log_errors(source: str = "dsp", authorization: str | None = Header(default=None)):
    _authorize(authorization)
    try:
        return read_log(source, errors_only=True, lines=80)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/service-health", operation_id="supervisor_service_health")
def supervisor_service_health(service: str = "ollama", authorization: str | None = Header(default=None)):
    _authorize(authorization)
    try:
        return service_health(service)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# A dedicated specification prevents agent clients from discovering unrelated
# and potentially state-changing Toolkit application endpoints.
@router.get("/openapi.json", include_in_schema=False)
def supervisor_openapi():
    from fastapi.openapi.utils import get_openapi
    from fastapi import FastAPI
    isolated = FastAPI(title="Mission Toolkit Read-only Test Supervisor", version="0.1.0")
    isolated.include_router(router)
    # Do not include this metadata route itself.
    spec = get_openapi(title=isolated.title, version=isolated.version, routes=[
        route for route in isolated.routes
        if getattr(route, "path", "").startswith("/api/supervisor/")
        and getattr(route, "include_in_schema", False)
    ])
    spec["servers"] = [{"url": "http://127.0.0.1:8420"}]
    return spec
