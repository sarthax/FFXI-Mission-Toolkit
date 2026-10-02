from __future__ import annotations

from pathlib import Path

from workbench.editors.character.gui import _safe, router

ROOT = Path(__file__).resolve().parents[1]


def test_character_editor_router_surface():
    paths = {route.path for route in router.routes}
    assert "/character-editor" in paths
    assert "/character-editor/status.json" in paths
    assert "/character-editor/characters.json" in paths
    assert "/character-editor/items.json" in paths
    assert "/character-editor/items/{item_id}.json" in paths
    assert "/character-editor/characters/{char_id}.json" in paths
    assert "/character-editor/characters/{char_id}/inventory.json" in paths
    assert "/character-editor/characters/{char_id}/items/preview" in paths
    assert "/character-editor/characters/{char_id}/items/add" in paths


def test_character_editor_json_safety_for_blob_fields():
    assert _safe(b"\x00\x01") == {"hex": "0001", "bytes": 2}
    assert _safe({"extra": bytearray(b"\xff")}) == {"extra": {"hex": "ff", "bytes": 1}}


def test_character_editor_template_has_search_inventory_and_confirm_flow():
    template = (ROOT / "gui" / "templates" / "character_editor.html").read_text(encoding="utf-8")
    assert 'id="characterSearch"' in template
    assert 'id="inventoryRows"' in template
    assert 'id="itemDialog"' in template
    assert "/itemedit/${id}/icon.png" in template
    assert "/items/preview" in template
    assert "approved:true" in template
    assert "previewItem()" in template
    assert "confirmItem()" in template
