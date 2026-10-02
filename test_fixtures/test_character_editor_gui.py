from __future__ import annotations

from pathlib import Path
import sys

from workbench.editors.character.gui import _safe, router

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "test_fixtures") not in sys.path:
    sys.path.insert(0, str(ROOT / "test_fixtures"))

from test_character_editor_packed_transactions import main as packed_transaction_regression


def test_character_editor_router_surface():
    paths = {route.path for route in router.routes}
    assert "/character-editor" in paths
    assert "/character-editor/status.json" in paths
    assert "/character-editor/characters.json" in paths
    assert "/character-editor/items.json" in paths
    assert "/character-editor/items/{item_id}.json" in paths
    assert "/character-editor/characters/{char_id}.json" in paths
    assert "/character-editor/characters/{char_id}/categories/{tab_key}.json" in paths
    assert "/character-editor/characters/{char_id}/fields/preview" in paths
    assert "/character-editor/characters/{char_id}/fields/apply" in paths
    assert "/character-editor/characters/{char_id}/packed/preview" in paths
    assert "/character-editor/characters/{char_id}/packed/apply" in paths
    assert "/character-editor/characters/{char_id}/inventory.json" in paths
    assert "/character-editor/characters/{char_id}/items/preview" in paths
    assert "/character-editor/characters/{char_id}/items/add" in paths


def test_character_editor_json_safety_for_blob_fields():
    assert _safe(b"\x00\x01") == {"hex": "0001", "bytes": 2}
    assert _safe({"extra": bytearray(b"\xff")}) == {"extra": {"hex": "ff", "bytes": 1}}


def test_character_editor_template_has_tabs_storage_and_guarded_scalar_flow():
    template = (ROOT / "gui" / "templates" / "character_editor.html").read_text(encoding="utf-8")
    assert 'id="characterSearch"' in template
    assert 'id="categoryTabs"' in template
    assert 'id="inventoryContainers"' in template
    assert 'id="itemDialog"' in template
    assert "/itemedit/${id}/icon.png" in template
    assert "/items/preview" in template
    assert "/fields/preview" in template
    assert "/fields/apply" in template
    assert "scalar editing locked until offline" in template
    assert "char_merit" in template and "meritid" in template
    assert "char_job_points" in template and "jobid" in template
    assert "char_vars" in template and "varname" in template
    assert "expected_before:preview.before" in template
    assert "approved:true" in template
    assert "previewScalarRow" in template
    assert "confirmItem()" in template


def test_character_editor_progression_wrapper_and_controls():
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_progression.js").read_text(encoding="utf-8")
    gui = (ROOT / "src" / "workbench" / "editors" / "character" / "gui.py").read_text(encoding="utf-8")

    assert '{% extends "character_editor.html" %}' in wrapper
    assert '/static/character_editor_progression.js' in wrapper
    assert 'name="character_editor_progression.html"' in gui

    assert "key === 'missions-quests'" in script
    assert "key === 'key-items'" in script
    assert "/packed/preview" in script
    assert "/packed/apply" in script
    assert "expected_before_sha256:preview.before_sha256" in script
    assert "editableOnline()" in script
    assert "editing locked until offline" in script

    assert "Set current" in script
    assert "status_upper" in script and "status_lower" in script
    assert "completed_id" in script and "completed" in script
    assert "Filter missions" in script

    assert "Search key item name or ID" in script
    assert "Numeric ID" in script
    assert "data-kind=\"owned\"" in script
    assert "data-kind=\"seen\"" in script
    assert "key_item_id" in script

    # Additional packed bitsets are intentionally display-only until a later guarded write slice.
    assert "renderPackedReadOnly(['abilities','weaponskills'])" in script
    assert "renderPackedReadOnly(['titles','visited_zones'])" in script
    assert "Learned Abilities" in script
    assert "Learned Weaponskill Unlocks" in script
    assert "Obtained Titles" in script
    assert "Visited Zones" in script
    assert "Labels come only from the selected server checkout." in script
    assert "Reserved legacy bits set:" in script
    assert "ce-readonly-filter" in script
    assert "ce-readonly-badge" in script


def test_character_editor_packed_mutations_preserve_unrelated_bytes():
    packed_transaction_regression()
