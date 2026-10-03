from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI
from workbench.editors.character.gui import _safe, router

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "test_fixtures") not in sys.path:
    sys.path.insert(0, str(ROOT / "test_fixtures"))

from test_character_editor_packed_transactions import main as packed_transaction_regression


def _router_paths() -> set[str]:
    app = FastAPI()
    app.include_router(router)
    return set(app.openapi()["paths"])


def test_character_editor_router_surface():
    paths = _router_paths()
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
    bitset = (ROOT / "gui" / "static" / "character_editor_bitset_edit.js").read_text(encoding="utf-8")
    blue = (ROOT / "gui" / "static" / "character_editor_blue_spells.js").read_text(encoding="utf-8")
    blue_edit = (ROOT / "gui" / "static" / "character_editor_blue_spell_edit.js").read_text(encoding="utf-8")
    quests = (ROOT / "gui" / "static" / "character_editor_quests.js").read_text(encoding="utf-8")
    gui = (ROOT / "src" / "workbench" / "editors" / "character" / "gui.py").read_text(encoding="utf-8")

    assert '{% extends "character_editor.html" %}' in wrapper
    assert '/static/character_editor_progression.js' in wrapper
    assert '/static/character_editor_bitset_edit.js' in wrapper
    assert '/static/character_editor_blue_spells.js' in wrapper
    assert '/static/character_editor_blue_spell_edit.js' in wrapper
    assert '/static/character_editor_quests.js' in wrapper
    assert wrapper.index('/static/character_editor_progression.js') < wrapper.index('/static/character_editor_bitset_edit.js') < wrapper.index('/static/character_editor_blue_spells.js') < wrapper.index('/static/character_editor_blue_spell_edit.js') < wrapper.index('/static/character_editor_quests.js')
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

    assert "renderPackedReadOnly(['abilities','weaponskills'])" in script
    assert "renderPackedReadOnly(['titles','visited_zones'])" in script
    assert "Labels come only from the selected server checkout." in script
    assert "Reserved legacy bits set:" in script

    assert "renderBitsetEditors(['abilities','weaponskills'])" in bitset
    assert "renderBitsetEditors(['titles','visited_zones'])" in bitset
    assert "editableOnline() && entry.editable === true" in bitset
    assert "/packed/preview" in bitset
    assert "/packed/apply" in bitset
    assert "expected_before_sha256:preview.before_sha256" in bitset
    assert "approved:true" in bitset
    assert "bit_id:id" in bitset
    assert "enabled:desired" in bitset
    assert "Reserved legacy bits are set but remain unwritable" in bitset
    assert "Numeric ID" in bitset
    assert "data-bit-id" in bitset
    assert "Single-bit edits use guarded preview + exact before-SHA confirmation." in bitset

    assert "key === 'spells-abilities'" in blue
    assert "activeCategoryData?.packed?.blue_spells" in blue
    assert "Set Blue Magic" in blue
    assert "read only" in blue
    assert "stored 0 · empty" in blue
    assert "spell ID" in blue and "stored" in blue
    assert "/packed/preview" not in blue
    assert "/packed/apply" not in blue

    assert "key === 'spells-abilities'" in blue_edit
    assert "editableOnline() && entry.editable === true" in blue_edit
    assert "capability:'blue_spells'" in blue_edit
    assert "/packed/preview" in blue_edit
    assert "/packed/apply" in blue_edit
    assert "expected_before_sha256:preview.before_sha256" in blue_edit
    assert "approved:true" in blue_edit
    assert "operation = {slot, spell_id:spellId}" in blue_edit
    assert "spell_id:null" not in blue_edit
    assert "previewAndApply(slot, null" in blue_edit
    assert "min=\"513\" max=\"767\"" in blue_edit
    assert "Blue spell ID must be between 513 (0x201) and 767 (0x2FF)." in blue_edit
    assert "editing locked until offline" in blue_edit

    # Quest editing is limited to one current/completed bit at a time through guarded packed writes.
    assert "key === 'missions-quests'" in quests
    assert "activeCategoryData?.packed?.quests" in quests
    assert "Quest State" in quests
    assert "Active" in quests and "Completed" in quests
    assert "Filter quest name or ID" in quests
    assert "checkout quest catalog unavailable" in quests
    assert "editableOnline() && entry.editable === true" in quests
    assert "capability:'quests'" in quests
    assert "/packed/preview" in quests
    assert "/packed/apply" in quests
    assert "expected_before_sha256:preview.before_sha256" in quests
    assert "approved:true" in quests
    assert "quest_id:questId" in quests
    assert "state, enabled:desired" in quests
    assert "min=\"0\" max=\"255\"" in quests
    assert "Quest ID must be between 0 and 255." in quests
    assert "editing locked until offline" in quests


def test_character_editor_packed_mutations_preserve_unrelated_bytes():
    packed_transaction_regression()
