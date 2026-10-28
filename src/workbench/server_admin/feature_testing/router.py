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
from .scenario_presentation import scenario_presentation
from .test_specifications import specification

router = APIRouter(prefix="/feature-testing", tags=["Feature Testing"])

# Apply saved Setup-tab settings (only when enabled; real env vars always win).
try:
    from . import test_execution_settings as _setup_boot
    _setup_boot.apply_to_environ()
except Exception:  # setup must never stop the Toolkit starting
    pass
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))
_REPO = Path(__file__).resolve().parents[4]


def load_test_catalog() -> dict:
    return json.loads((_REPO / "data/testing/feature_test_readiness.json").read_text(encoding="utf-8"))


def _results_db():
    # No implicit creation of a database under source control.
    return os.environ.get('MISSION_TOOLKIT_TEST_RESULTS_DB')


def _selected_run_view(feature_id: str, case_id: str, run_id: str):
    """Reevaluation context for one explicitly selected imported run; None if unusable."""
    from .results import results_for_run
    try:
        rows = results_for_run(_results_db(), run_id) if _results_db() else []
    except ValueError:
        return None
    row = next((r for r in rows if (r["feature_id"], r["case_id"]) == (feature_id, case_id)), None)
    if row is None:
        return None
    if (feature_id, case_id) == ("moghancement", "MOG-09"):
        from .normalized_evidence import evaluate_imported_mog09
        try:
            return evaluate_imported_mog09(row)
        except ValueError as exc:
            return {"error": str(exc), "recorded_verdict": row["verdict"]}
    return {"recorded_verdict": row["verdict"]}


def scenario_detail(feature_id: str, case_id: str, run_id: str = "") -> dict:
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
    observed = recent_results(_results_db(), feature_id=feature_id, case_id=case_id) if _results_db() else []
    run_ids = list(dict.fromkeys(r["run_id"] for r in observed))
    selected = None
    reevaluation = None
    if run_id and run_id in run_ids:
        reevaluation = _selected_run_view(feature_id, case_id, run_id)
        selected = run_id if reevaluation is not None else None
    return {"feature_id": feature_id, "feature_name": feature["name"],
            "scenario": case, "feature_gaps": feature.get("gaps", []),
            "gm_candidates": feature.get("existing_gm_candidates", []),
            "expected_reference": reference, "execution_enabled": False,
            "presentation": scenario_presentation(specification(feature_id, case_id), reevaluation, selected),
            "run_ids": run_ids,
            "observed_results": observed}


@router.get("/preflight/{feature_id}/{case_id}")
def scenario_preflight(feature_id: str, case_id: str):
    from .execution_preflight import preflight
    return preflight(feature_id, case_id)


@router.get("/catalog/{feature_id}/{case_id}")
def scenario_api(feature_id: str, case_id: str):
    return scenario_detail(feature_id, case_id)


@router.get("/scenario/{feature_id}/{case_id}", response_class=HTMLResponse)
def scenario_page(request: Request, feature_id: str, case_id: str, run: str = ""):
    return templates.TemplateResponse(request=request, name="feature_testing_scenario.html",
                                      context={"title": "Test Scenario", "detail": scenario_detail(feature_id, case_id, run),
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
    from .results import results_for_run
    try:
        rows = results_for_run(_results_db(), run_id) if _results_db() else []
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not rows:
        # A readable page, not bare JSON: say what was looked for and where to go next.
        return templates.TemplateResponse(request=request, name="feature_testing_run.html", status_code=404,
                                          context={"title": "Test Run not found", "run_id": run_id, "records": [],
                                                   "reevaluations": {}, "scenario_views": {}, "outcomes": {},
                                                   "missing": True, "results_configured": bool(_results_db())})
    from .normalized_evidence import evaluate_imported_mog09
    reevaluations = {}
    scenario_views = {}
    for index, row in enumerate(rows):
        if (row["feature_id"], row["case_id"]) == ("moghancement", "MOG-09"):
            try:
                reevaluations[index] = evaluate_imported_mog09(row)
            except ValueError as exc:
                reevaluations[index] = {"error": str(exc), "recorded_verdict": row["verdict"]}
        scenario_views[index] = scenario_presentation(
            specification(row["feature_id"], row["case_id"]),
            reevaluations.get(index, {"recorded_verdict": row["verdict"]}),
            run_id,
        )
    from .execution_jobs import job_for_run
    from .run_outcome import describe_outcome
    job = job_for_run(run_id)
    outcomes = {index: describe_outcome(row, job) for index, row in enumerate(rows)}
    return templates.TemplateResponse(request=request, name="feature_testing_run.html",
                                      context={"title": "Test Run", "run_id": run_id, "records": rows,
                                               "reevaluations": reevaluations, "scenario_views": scenario_views,
                                               "outcomes": outcomes})


def _compare_context(request: Request, left: str, right: str, **extra):
    from .compare_wording import reason_text, transition_text
    runs = _run_summary(_history())
    return templates.TemplateResponse(
        request=request, name="feature_testing_compare.html", status_code=extra.pop("status_code", 200),
        context={"title": "Compare runs", "left": left, "right": right, "runs": runs[:100],
                 "results_configured": bool(_results_db()), "reason_text": reason_text,
                 "transition_text": transition_text, **extra})


@router.get("/compare/data")
def compare_api(left: str, right: str):
    """The raw comparison of two stored runs (``left`` earlier, ``right`` later). Read-only."""
    from .stored_run_comparison import compare_stored_runs
    if not _results_db():
        raise HTTPException(404, "No evidence database is configured")
    try:
        return {**compare_stored_runs(_results_db(), left, right), "execution_enabled": False}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/compare", response_class=HTMLResponse)
def compare_page(request: Request, left: str = "", right: str = ""):
    """Two recorded runs side by side: what changed, and whether the pair can be compared at all."""
    from .stored_run_comparison import compare_stored_runs
    left, right = left.strip(), right.strip()
    if not left or not right:
        return _compare_context(request, left, right, comparison=None, problem=None)
    if not _results_db():
        return _compare_context(request, left, right, comparison=None, status_code=404,
                                problem="No evidence database is configured, so there is nothing to compare.")
    if left == right:
        return _compare_context(request, left, right, comparison=None, status_code=400,
                                problem="Choose two different runs.")
    try:
        comparison = compare_stored_runs(_results_db(), left, right)
    except ValueError as exc:
        return _compare_context(request, left, right, comparison=None, status_code=404,
                                problem=str(exc) if "both runs" in str(exc) else "These runs could not be compared: " + str(exc))
    return _compare_context(request, left, right, comparison=comparison, problem=None)


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


class DraftPreviewRequest(BaseModel):
    specification: dict
    observations: dict
    context: dict = {}


@router.post("/builder/drafts/preview", include_in_schema=False)
def draft_evaluation_preview(request: Request, payload: DraftPreviewRequest):
    if not request.client or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Local draft preview only")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Cross-origin preview denied")
    from .draft_preview import preview_draft
    try:
        return preview_draft(payload.specification, payload.observations, payload.context)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class DraftSaveRequest(BaseModel):
    specification: dict
    expected_revision: int = 0


@router.get("/builder/drafts", include_in_schema=False)
def draft_list(request: Request, x_test_operator_token: str | None = Header(default=None)):
    _operator_auth(request, x_test_operator_token)
    from .spec_drafts import get_drafts
    try:
        return {"drafts": get_drafts(), "execution_enabled": False}
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/builder/drafts", include_in_schema=False)
def draft_save(request: Request, payload: DraftSaveRequest,
               x_test_operator_token: str | None = Header(default=None)):
    _operator_auth(request, x_test_operator_token)
    from .spec_drafts import save_draft
    try:
        return save_draft(payload.specification, payload.expected_revision)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


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
    try:
        return build_plan(account, charid, supervisor_port)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc



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
    from . import test_execution_settings as setup
    if (not operator_token and setup.ui_mode_active()
            and request.headers.get("sec-fetch-site") == "same-origin"
            and request.headers.get("x-requested-with") == "toolkit-ui"):
        # Setup-tab opt-in: the page itself is the operator. Blocks cross-site browsers and
        # OpenAPI/model tools (hidden routes); it does not defend against local processes.
        operator_token = os.environ.get("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN")
    try:
        authorize_operator(operator_token)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


def _setup_guard(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Local operator access only")
    if (request.headers.get("sec-fetch-site") != "same-origin"
            or request.headers.get("x-requested-with") != "toolkit-ui"):
        raise HTTPException(403, "Setup changes must come from the Toolkit page")


class SetupRequest(BaseModel):
    headless_root: str | None = None
    charids: str | None = None
    account: str | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_name: str | None = None
    db_port: int | None = None


@router.get("/setup/status", include_in_schema=False)
def setup_status(request: Request):
    _setup_guard(request)
    from . import test_execution_settings as setup
    return setup.status()


@router.post("/setup/save", include_in_schema=False)
def setup_save(request: Request, payload: SetupRequest):
    _setup_guard(request)
    from . import test_execution_settings as setup
    db = {k: v for k, v in (("user", payload.db_user), ("password", payload.db_password),
                            ("name", payload.db_name), ("port", payload.db_port)) if v is not None}
    try:
        setup.update(headless_root=payload.headless_root, charids=payload.charids, db=db or None, account=payload.account)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return setup.status()


class EnableRequest(BaseModel):
    enabled: bool


@router.post("/setup/enable", include_in_schema=False)
def setup_enable(request: Request, payload: EnableRequest):
    _setup_guard(request)
    from . import test_execution_settings as setup
    setup.set_enabled(payload.enabled)
    return setup.status()


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


def _run_defaults() -> dict:
    from . import test_execution_settings as setup
    saved = setup.load()
    return {"account": saved["account"], "charid": (saved["charids"] or [""])[0]}


def _ui_mode() -> bool:
    from . import test_execution_settings as setup
    return setup.ui_mode_active()


def dashboard_view(*, tab: str = "runs", feature: str = "", verdict: str = "",
                   query: str = "", page: int = 1) -> dict:
    """Build a bounded view without altering the append-only evidence store."""
    # "setup" is the name users see for the guide tab; accept it as an alias.
    tab = {"setup": "guide"}.get(tab, tab)
    tab = tab if tab in {"runs", "catalog", "guide", "builder"} else "runs"
    verdict = verdict.upper()
    if verdict not in {"PASS", "FAIL", "BLOCKED", "SKIPPED", "UNKNOWN"}:
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
            "results_configured": bool(_results_db()), "execution_enabled": False,
            "ui_mode": _ui_mode(), "run_defaults": _run_defaults()}


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, tab: str = "runs", feature: str = "",
              verdict: str = "", query: str = "", page: int = 1):
    view = dashboard_view(tab=tab, feature=feature, verdict=verdict, query=query, page=page)
    return templates.TemplateResponse(request=request, name="feature_testing.html",
                                      context={"title": "Feature Testing & Validation", **view})
