"""Read-only Feature Testing & Validation dashboard."""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
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


@router.get("/catalog/{feature_id}/{case_id}")
def scenario_api(feature_id: str, case_id: str):
    return scenario_detail(feature_id, case_id)


@router.get("/scenario/{feature_id}/{case_id}", response_class=HTMLResponse)
def scenario_page(request: Request, feature_id: str, case_id: str):
    return templates.TemplateResponse(request=request, name="feature_testing_scenario.html",
                                      context={"title": "Test Scenario", "detail": scenario_detail(feature_id, case_id)})


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


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="feature_testing.html",
                                      context={"title": "Feature Testing & Validation",
                                               "features": _summaries(), "execution_enabled": False})
