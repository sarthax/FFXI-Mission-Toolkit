"""Fail-closed, read-only supervisor endpoints for local tool integration.

No database writes, shell commands, free-form SQL, or raw MCP controls.
Disabled entirely unless a local operator configures a bearer token.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

from workbench.server_admin.feature_testing.router import _results_db, _run_summary
from workbench.server_admin.feature_testing.results import recent_results, results_for_run
from .log_diagnostics import read_log
from .service_health import service_health
from .database_diagnostics import char_vars_snapshot, inventory_snapshot, key_items_snapshot
from .bounded_inventory import inventory_snapshot_v2
from .source_diagnostics import search_source
from .failure_diagnostics import failure_summary
from .investigation_dossier import investigation_dossier

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



@router.get("/run-evidence/{run_id}", operation_id="supervisor_run_evidence")
def run_evidence(run_id: str, authorization: str | None = Header(default=None)):
    """Retrieve all bounded imported evidence for one exact run ID; no execution."""
    _authorize(authorization)
    db_path = _results_db()
    if not db_path:
        raise HTTPException(status_code=503, detail="Results database not configured")
    try:
        records = results_for_run(db_path, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not records:
        raise HTTPException(status_code=404, detail="Run not found")
    # The importer bounds each record, but a run may have many records.
    # Reject oversized responses instead of silently dropping evidence.
    import json
    payload = json.dumps(records, ensure_ascii=False)
    if len(payload.encode("utf-8")) > 524288:
        raise HTTPException(status_code=413, detail="Run evidence exceeds supervisor response limit")
    for record in records:
        evidence = record["evidence"]
        assertions = evidence.get("assertions", [])
        record["assertions"] = assertions if isinstance(assertions, list) else []
        evaluation = evidence.get("evaluation", {})
        record["evaluation"] = evaluation if isinstance(evaluation, dict) else {}
        record.pop("evidence_json", None)
    return {"run_id": run_id, "records": records, "count": len(records),
            "result_records": len(records),
            "assertion_count": sum(len(record["assertions"]) for record in records),
            "interpretation_notes": [
                "A PASS result record may contain multiple assertions; inspect each assertion separately.",
                "A client key_items list represents held key items, not necessarily the active Moghancement effect.",
                "An oracle key_item of 0 means no selected furnishing effect; it does not imply zero held key items.",
                "Imported evidence is historical; execution_enabled false does not invalidate the recorded result.",
                "An empty layout assumed by an oracle is not independently verified installed-furniture layout.",
            ],
            "source": "imported_evidence_not_independently_authenticated",
            "execution_enabled": False}


@router.get("/failed-assertions", operation_id="supervisor_failed_assertions")
def failed_assertions(authorization: str | None = Header(default=None)):
    _authorize(authorization)
    path = _results_db()
    rows = recent_results(path, limit=100) if path else []
    summaries = [failure_summary(row) for row in rows]
    return {"results": [item for item in summaries if item is not None],
            "limit": 100, "source": "imported_evidence_not_independently_authenticated",
            "execution_enabled": False}


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


@router.get("/test-character-inventory", operation_id="supervisor_test_character_inventory")
def test_character_inventory(charid: int, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    try:
        return inventory_snapshot(charid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc





@router.get("/test-character-inventory-v2", operation_id="supervisor_test_character_inventory_v2")
def test_character_inventory_v2(charid: int, location: int, cursor: int = 0, limit: int = 100,
                                authorization: str | None = Header(default=None)):
    """Paginated persisted DB rows only; never a live inventory or complete client agreement."""
    _authorize(authorization)
    try:
        return inventory_snapshot_v2(charid, location, cursor, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/test-character-keyitems", operation_id="supervisor_test_character_keyitems")
def test_character_keyitems(charid: int, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    try:
        return key_items_snapshot(charid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/test-character-vars", operation_id="supervisor_test_character_vars")
def test_character_vars(charid: int, names: str, authorization: str | None = Header(default=None)):
    """Named char_vars for an approved test character; `names` is a comma-separated list."""
    _authorize(authorization)
    try:
        return char_vars_snapshot(charid, [n.strip() for n in names.split(",") if n.strip()])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/search-source", operation_id="supervisor_search_source")
def supervisor_search_source(term: str, repository: str = "toolkit",
                             authorization: str | None = Header(default=None)):
    """Search bounded, allowlisted local source snapshots. Never execute or modify files."""
    _authorize(authorization)
    try:
        return search_source(repository, term)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/investigation/{run_id}", operation_id="supervisor_investigation_dossier")
def supervisor_investigation_dossier(run_id: str, repository: str = "dsp",
                                     authorization: str | None = Header(default=None)):
    """Inspect imported failures and candidate source locations; never execute."""
    _authorize(authorization)
    db = _results_db()
    if not db:
        raise HTTPException(status_code=503, detail="Results database not configured")
    try:
        records = results_for_run(db, run_id)
        if not records:
            raise HTTPException(status_code=404, detail="Run not found")
        return investigation_dossier(records, repository=repository)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# A dedicated specification prevents agent clients from discovering unrelated
# and potentially state-changing Toolkit application endpoints.
@router.get("/openapi.json", include_in_schema=False)
def supervisor_openapi():
    from fastapi.openapi.utils import get_openapi
    # Read the router's own routes: FastAPI >= 0.141 wraps included routers in
    # lazy objects, so filtering an app's route list yielded an empty spec.
    spec = get_openapi(title="Mission Toolkit Read-only Test Supervisor", version="0.1.0", routes=[
        route for route in router.routes
        if getattr(route, "path", "").startswith("/api/supervisor/")
        and getattr(route, "include_in_schema", False)
    ])
    spec["servers"] = [{"url": "http://127.0.0.1:8420"}]
    # The token belongs to the client connection, not the model: hide the header
    # parameter and declare Bearer auth so tool clients never ask for a token.
    for item in spec["paths"].values():
        for op in item.values():
            op["parameters"] = [p for p in op.get("parameters", []) if p.get("name") != "authorization"]
            if not op["parameters"]:
                del op["parameters"]
            op["security"] = [{"bearerAuth": []}]
    spec.setdefault("components", {}).setdefault("securitySchemes", {})["bearerAuth"] = {"type": "http", "scheme": "bearer"}
    return spec
