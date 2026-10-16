"""GM command browser is visible but cannot execute commands."""
from fastapi.testclient import TestClient
from fastapi import FastAPI
from workbench.server_admin.gm_commands import gui


def test_catalog_and_page_are_copy_only(monkeypatch):
    sample = [{"name": "getmobaction", "command": "!getmobaction",
               "description": "Inspect mob action", "permission": 1,
               "parameters": "i", "classification": "diagnostic_candidate",
               "execution_enabled": False, "source_path": "scripts/commands/getmobaction.lua"}]
    monkeypatch.setattr(gui, "_catalog", lambda: sample)
    app = FastAPI()
    app.include_router(gui.router)
    client = TestClient(app)
    reply = client.get("/server/gm/commands")
    assert reply.status_code == 200
    assert reply.json()["commands"] == sample
    assert reply.json()["execution_enabled"] is False
    page = client.get("/server/gm")
    assert page.status_code == 200
    assert 'id="search"' in page.text
    assert "Copy command" in page.text
    assert "No command transmission is enabled" in page.text
    assert client.post("/server/gm/commands", json={"command": "!additem 1"}).status_code == 405
