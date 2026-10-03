from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src" / "workbench" / "editors" / "character"


def test_pet_runtime_summary_is_read_only_and_resolves_companion_names():
    text = (BASE / "pet_runtime_summary.py").read_text(encoding="utf-8")
    assert 'SHOW TABLES LIKE %s' in text
    assert 'SELECT `name` FROM `pet_name` WHERE `id` = %s' in text
    assert '"wyvern"' in text
    assert '"automaton"' in text
    assert '"unlocked_attachments_bytes"' in text
    assert '"equipped_attachments_bytes"' in text
    assert '"chocobo_user_data_bytes"' in text
    assert '"read_only_relational_and_packed_state"' in text
    assert '"read_only_persisted_runtime_state"' in text
    assert "UPDATE `char_pet`" not in text
    assert "DELETE FROM `char_effects`" not in text
    assert "UPDATE `char_recast`" not in text


def test_pet_runtime_summary_surfaces_chocobo_and_runtime_rows():
    text = (BASE / "pet_runtime_summary.py").read_text(encoding="utf-8")
    assert 'schema.table("char_chocobos")' in text
    assert 'schema.table("char_effects")' in text
    assert 'schema.table("char_recast")' in text
    assert '"effects": effects' in text
    assert '"recasts": recasts' in text
    assert '"first_name"' in text
    assert '"strength"' in text
    assert '"care_plan"' in text


def test_pet_runtime_endpoint_is_get_only():
    text = (BASE / "audit_gui.py").read_text(encoding="utf-8")
    assert 'router.get("/characters/{char_id}/pet-runtime.json")' in text
    assert 'build_pet_runtime_summary' in text
    assert 'router.post("/characters/{char_id}/pet-runtime' not in text


def test_pets_effects_ui_labels_protected_runtime_state():
    script = (ROOT / "gui" / "static" / "character_editor_pet_runtime.js").read_text(encoding="utf-8")
    template = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    assert "key === 'pets-effects'" in script
    assert "/pet-runtime.json" in script
    assert "read only" in script
    assert "Attachment/chocobo BLOBs remain codec-gated and are not editable" in script
    assert "Persisted runtime restoration state · direct row editing disabled" in script
    assert "Cooldown restoration state · direct row editing disabled" in script
    assert "character_editor_pet_runtime.js" in template


if __name__ == "__main__":
    test_pet_runtime_summary_is_read_only_and_resolves_companion_names()
    test_pet_runtime_summary_surfaces_chocobo_and_runtime_rows()
    test_pet_runtime_endpoint_is_get_only()
    test_pets_effects_ui_labels_protected_runtime_state()
