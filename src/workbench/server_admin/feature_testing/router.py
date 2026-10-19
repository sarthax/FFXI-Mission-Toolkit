"""Read-only Feature Testing & Validation dashboard."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.paths import GUI_ROOT
from .results import recent_results

router = APIRouter(prefix="/feature-testing", tags=["Feature Testing"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))
_REPO = Path(__file__).resolve().parents[4]


def load_test_catalog() -> dict:
    return json.loads((_REPO / "data/testing/feature_test_readiness.json").read_text(encoding="utf-8"))


def _results_db():
    # No implicit creation of a database under source control.
    return os.environ.get('MISSION_TOOLKIT_TEST_RESULTS_DB')


def scenario_detail(feature_id: str, case_id: str) -> dict:
    catalog = load_test_catalog()
    feature = next((f for f in catalog["features"] if f["id"] == feature_id), None)
    if feature is None:
        raise HTTPException(404, "Unknown feature")
    case = next((c for c in feature.get("cases", []) if c["id"] == case_id), None)
    if case is None:
        raise HTTPException(404, "Unknown scenario")
    reference = None
    if feature_id == "gardening":
        reference = {"type": "sql_reward_oracle", "source": "sql/gardening_results.sql",
                     "detail": "Validate harvested item/quantity against seed and two crystals using the selected DSP checkout."}
    elif feature_id == "moghancement":
        reference = {"type": "furnishing_and_effect_oracle", "source": "sql/item_furnishing.sql",
                     "effect_catalog": "data/testing/moghancement_effect_validation.json",
                     "detail": "Predict dominant aura, key item, modifier delta and independent gameplay effect."}
    return {"feature_id": feature_id, "feature_name": feature["name"],
            "scenario": case, "feature_gaps": feature.get("gaps", []),
            "gm_candidates": feature.get("existing_gm_candidates", []),
            "expected_reference": reference, "execution_enabled": False,
            "observed_results": recent_results(_results_db(), feature_id=feature_id, case_id=case_id) if _results_db() else []}


@router.get("/preflight/{feature_id}/{case_id}")
def scenario_preflight(feature_id: str, case_id: str):
    from .execution_preflight import preflight
    return preflight(feature_id, case_id)


@router.get("/catalog/{feature_id}/{case_id}")
def scenario_api(feature_id: str, case_id: str):
    return scenario_detail(feature_id, case_id)


@router.get("/scenario/{feature_id}/{case_id}", response_class=HTMLResponse)
def scenario_page(request: Request, feature_id: str, case_id: str):
    return templates.TemplateResponse(request=request, name="feature_testing_scenario.html",
                                      context={"title": "Test Scenario", "detail": scenario_detail(feature_id, case_id),
                                               "preflight": scenario_preflight(feature_id, case_id)})


def _history():
    db = _results_db()
    return recent_results(db, limit=500) if db else []


def _run_summary(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows:
        key = row["run_id"]
        group = groups.setdefault(key, {"run_id": key, "latest": row["observed_at"],
                                       "verdicts": {}, "features": set(), "count": 0})
        group["count"] += 1
        group["features"].add(row["feature_id"])
        group["verdicts"][row["verdict"]] = group["verdicts"].get(row["verdict"], 0) + 1
        group["latest"] = max(group["latest"], row["observed_at"])
    return [{**v, "features": sorted(v["features"])} for v in sorted(
        groups.values(), key=lambda v: (v["latest"], v["run_id"]), reverse=True)]


@router.get("/runs")
def run_history_api():
    return {"runs": _run_summary(_history()), "execution_enabled": False}


@router.get("/run/{run_id}", response_class=HTMLResponse)
def run_page(request: Request, run_id: str):
    rows = [r for r in _history() if r["run_id"] == run_id]
    if not rows:
        raise HTTPException(404, "Run not found")
    return templates.TemplateResponse(request=request, name="feature_testing_run.html",
                                      context={"title": "Test Run", "run_id": run_id, "records": rows})


def _summaries() -> list[dict]:
    features = []
    for f in load_test_catalog()["features"]:
        counts = {}
        for case in f.get("cases", []):
            key = case.get("status", "planned")
            counts[key] = counts.get(key, 0) + 1
        features.append({"id": f["id"], "name": f["name"], "counts": counts,
                         "cases": f.get("cases", []), "gaps": f.get("gaps", []),
                         "commands": f.get("existing_gm_candidates", [])})
    return features


@router.get("/catalog")
def catalog_api():
    return {"features": _summaries(), "execution_enabled": False,
            "results": recent_results(_results_db()) if _results_db() else []}


@router.get("/results")
def results_api(feature_id: str | None = None, case_id: str | None = None):
    return {"results": recent_results(_results_db(), feature_id=feature_id, case_id=case_id)
            if _results_db() else [], "execution_enabled": False}


def _builder_preflight():
    from .execution_preflight import preflight
    return preflight("moghancement", "MOG-09")


class EvaluationPreviewRequest(BaseModel):
    feature_id: str
    case_id: str
    observations: dict
    context: dict = {}


@router.post("/builder/evaluate", include_in_schema=False)
async def evaluate_test_preview(request: Request, payload: EvaluationPreviewRequest):
    # Preview is local-only, deliberately absent from the Ornith tool schema.
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Local preview only")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin preview denied")
    if int(request.headers.get("content-length", "0") or 0) > 32768:
        raise HTTPException(413, "Preview request too large")
    from .evaluation_preview import preview
    try:
        return preview(payload.feature_id, payload.case_id, payload.observations, payload.context)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/builder/imported-evaluation/{run_id}")
def imported_evaluation_preview(run_id: str):
    from .normalized_evidence import evaluate_imported_mog09
    from .results import results_for_run
    db = _results_db()
    if not db:
        raise HTTPException(503, "Results database not configured")
    try:
        records = results_for_run(db, run_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    matches = [r for r in records if (r["feature_id"], r["case_id"]) == ("moghancement", "MOG-09")]
    if len(matches) != 1:
        raise HTTPException(404, "Exactly one MOG-09 record required for this run")
    result = evaluate_imported_mog09(matches[0])
    return {"run_id": run_id, **result, "preview_only": True, "persisted": False}


@router.get("/builder/specifications")
def test_specifications_api():
    from .test_specifications import specifications
    return {"schema_version": 1, "specifications": specifications(), "execution_enabled": False}


@router.get("/builder/specifications/{feature_id}/{case_id}")
def test_specification_api(feature_id: str, case_id: str):
    from .test_specifications import specification
    result = specification(feature_id, case_id)
    if result is None:
        raise HTTPException(404, "Unknown test specification")
    return result


@router.get("/builder/plan")
def test_builder_plan(account: str = "", charid: int = 0, supervisor_port: int = 8420):
    from .test_builder import build_plan
    return build_plan(account, charid, supervisor_port)



class LaunchRequest(BaseModel):
    account: str
    charid: int
    supervisor_port: int = 8420
    approval: bool = False


def _operator_auth(request: Request, operator_token: str | None) -> None:
    from .execution_jobs import authorize_operator
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Local operator access only")
    origin = request.headers.get("origin", "")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin execution denied")
    try:
        authorize_operator(operator_token)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/builder/launch", include_in_schema=False)
def launch_test(request: Request, payload: LaunchRequest,
                x_test_operator_token: str | None = Header(default=None)):
    _operator_auth(request, x_test_operator_token)
    if payload.approval is not True:
        raise HTTPException(400, "Explicit operator confirmation required")
    from .execution_jobs import enqueue
    try:
        job_id = enqueue(payload.account, payload.charid, payload.supervisor_port)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"job_id": job_id, "status": "QUEUED", "case_id": "MOG-09"}


class RecoveryRequest(BaseModel):
    acknowledged: bool = False


@router.post("/builder/jobs/{job_id}/reconcile", include_in_schema=False)
def reconcile_execution_job(request: Request, job_id: str, payload: RecoveryRequest,
                            x_test_operator_token: str | None = Header(default=None)):
    _operator_auth(request, x_test_operator_token)
    from .execution_jobs import recover_interrupted
    try:
        return recover_interrupted(job_id, acknowledged=payload.acknowledged)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/builder/jobs", include_in_schema=False)
def execution_jobs(request: Request, x_test_operator_token: str | None = Header(default=None)):
    _operator_auth(request, x_test_operator_token)
    from .execution_jobs import jobs
    try:
        return {"jobs": jobs()}
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


def dashboard_view(*, tab: str = "runs", feature: str = "", verdict: str = "",
                   query: str = "", page: int = 1) -> dict:
    """Build a bounded view without altering the append-only evidence store."""
    tab = tab if tab in {"runs", "catalog", "guide", "builder"} else "runs"
    verdict = verdict.upper()
    if verdict not in {"PASS", "FAIL", "BLOCKED", "SKIPPED"}:
        verdict = ""
    feature = feature[:64]
    query = query.strip()[:100]
    page = min(max(int(page), 1), 1000)
    records = _history()
    runs = _run_summary(records)
    if feature:
        runs = [run for run in runs if feature in run["features"]]
    if verdict:
        runs = [run for run in runs if run["verdicts"].get(verdict, 0)]
    if query:
        runs = [run for run in runs if query.casefold() in run["run_id"].casefold()]
    page_size = 20
    total = len(runs)
    max_page = max(1, (total + page_size - 1) // page_size)
    page = min(page, max_page)
    return {"tab": tab, "runs": runs[(page - 1) * page_size:page * page_size],
            "total_runs": total, "page": page, "max_page": max_page,
            "feature_filter": feature, "verdict_filter": verdict, "query_filter": query,
            "features": _summaries(), "evidence_count": len(records),
            "builder_preflight": _builder_preflight(),
            "results_configured": bool(_results_db()), "execution_enabled": False}


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, tab: str = "runs", feature: str = "",
              verdict: str = "", query: str = "", page: int = 1):
    view = dashboard_view(tab=tab, feature=feature, verdict=verdict, query=query, page=page)
    return templates.TemplateResponse(request=request, name="feature_testing.html",
                                      context={"title": "Feature Testing & Validation", **view})
