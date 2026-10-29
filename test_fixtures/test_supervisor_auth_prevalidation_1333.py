"""#1333: unauthenticated requests to matched supervisor routes with malformed typed input.

Test/CI only. Mounts the real supervisor router on a bare FastAPI app and records every data-lookup entry point.
Expected: 403 (authentication) is decided before 422 (framework validation), and nothing is looked up.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workbench.server_admin.feature_testing import supervisor

_LOOKUPS = ["inventory_snapshot", "inventory_snapshot_v2", "key_items_snapshot", "char_vars_snapshot",
            "progression_snapshot", "selected_jobs_snapshot", "search_source", "investigation_dossier",
            "read_log", "service_health", "recent_results", "results_for_run", "failure_summary"]

_MALFORMED = [
    "/api/supervisor/test-character-inventory?charid=abc",
    "/api/supervisor/test-character-inventory-v2?charid=abc&location=x",
    "/api/supervisor/test-character-inventory-v2?charid=1&location=0&limit=abc",
    "/api/supervisor/test-character-keyitems?charid=abc",
    "/api/supervisor/test-character-vars?charid=abc&names=x",
    "/api/supervisor/test-character-progression?charid=abc&names=x&include_keyitems=maybe",
    "/api/supervisor/test-character-selected-jobs?charid=abc",
    "/api/supervisor/test-character-inventory",          # required parameter missing
    "/api/supervisor/search-source",                      # required term missing
]


@pytest.fixture
def client_and_calls(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    calls = []
    for name in _LOOKUPS:
        monkeypatch.setattr(supervisor, name, lambda *a, _n=name, **k: calls.append(_n), raising=True)
    app = FastAPI()
    app.include_router(supervisor.router)
    return TestClient(app), calls


@pytest.mark.parametrize("url", _MALFORMED)
@pytest.mark.parametrize("headers", [{}, {"authorization": "Bearer " + "b" * 64}])
def test_unauthenticated_malformed_input_is_denied_before_validation(client_and_calls, url, headers):
    client, calls = client_and_calls
    response = client.get(url, headers=headers)
    assert response.status_code == 403, f"{url} -> {response.status_code}"
    assert calls == []
