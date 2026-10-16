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
    from workbench.gui_shell import build_shell_context
    gui.templates.env.globals.update(
        current_theme=lambda: "dark", backport_enabled=lambda: False,
        shell_context=lambda request: build_shell_context(
            path=request.url.path, method=request.method, settings={}, default_topaz_root="C:/topaz",
            default_backport_root="", detected_client_path=None, workspace_slug=None, shell_override=None))
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
    assert "wb-page-frame" in page.text  # shared shell page template, not standalone HTML
    assert "Copy command" in page.text
    assert "allow_chat_commands=1" in page.text
    assert client.post("/server/gm/commands", json={"command": "!additem 1"}).status_code == 405
