from pathlib import Path

from fastapi import FastAPI
from workbench.editors.character.gui import router


ROOT = Path(__file__).resolve().parents[1]


def test_character_editor_state_surface_route_is_registered():
    app = FastAPI()
    app.include_router(router)
    paths = set(app.openapi()["paths"])
    assert "/character-editor/characters/{char_id}/state-surface.json" in paths


def test_character_editor_state_surface_ui_contract():
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_state_surface.js").read_text(encoding="utf-8")
    assert "/static/character_editor_state_surface.js" in wrapper
    assert "Trace current" in script
    assert "openStateSurface('mission'" not in script  # trace buttons keep IDs data-driven
    assert "/state-surface.json?kind=" in script
    assert "Open Key Items" in script
    assert "Open Variables" in script
    assert "condition_matches" in script
    assert "mismatches" in script
    assert "Static source evidence; runtime ordering is not inferred." in script
    assert "/behavior?source=" in script
