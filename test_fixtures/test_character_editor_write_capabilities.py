from __future__ import annotations

from workbench.editors.character.service import CharacterEditorService


def _service(family: str) -> CharacterEditorService:
    service = object.__new__(CharacterEditorService)
    service.adapter_family = family
    return service


def test_write_capabilities_report_current_guarded_families():
    expected = [
        "inventory_offline",
        "scalar_rows_offline",
        "packed_progression_offline",
        "spells_offline",
        "blacklist_offline",
        "audit_undo_offline",
    ]
    assert _service("dsp").write_capabilities() == expected
    assert _service("topaz").write_capabilities() == expected


def test_lsb_adds_verified_admin_write_family_only_for_lsb():
    caps = _service("lsb").write_capabilities()
    assert caps[:-1] == _service("dsp").write_capabilities()
    assert caps[-1] == "lsb_admin_offline"
    assert "lsb_admin_offline" not in _service("topaz").write_capabilities()


def test_legacy_underreported_capability_names_are_retired():
    text = __import__("pathlib").Path(__file__).resolve().parents[1].joinpath(
        "src", "workbench", "editors", "character", "service.py"
    ).read_text(encoding="utf-8")
    assert "inventory_basic_offline" not in text
    assert "scalar_character_offline" not in text
    assert "packed_missions_keyitems_offline" not in text


if __name__ == "__main__":
    test_write_capabilities_report_current_guarded_families()
    test_lsb_adds_verified_admin_write_family_only_for_lsb()
    test_legacy_underreported_capability_names_are_retired()
