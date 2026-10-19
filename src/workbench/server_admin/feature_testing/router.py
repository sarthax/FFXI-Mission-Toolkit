"""Read-only Feature Testing & Validation dashboard."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from workbench.runtime.paths import GUI_ROOT

router = APIRouter(prefix="/feature-testing", tags=["Feature Testing"])
templates = Jinja2Templates(directory=str(GUI_ROOT / "templates"))
_REPO = Path(__file__).resolve().parents[4]


def test_catalog() -> dict:
    return json.loads((_REPO / "data/testing/feature_test_readiness.json").read_text(encoding="utf-8"))


def _summaries() -> list[dict]:
    features = []
    for f in test_catalog()["features"]:
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
    return {"features": _summaries(), "execution_enabled": False, "results": []}


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="feature_testing.html",
                                      context={"title": "Feature Testing & Validation",
                                               "features": _summaries(), "execution_enabled": False})
