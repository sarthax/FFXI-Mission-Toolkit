from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_spells.js").read_text(encoding="utf-8")
    gui = (ROOT / "src" / "workbench" / "editors" / "character" / "gui.py").read_text(encoding="utf-8")

    assert '/static/character_editor_spells.js' in wrapper
    assert "spells-abilities" in script
    assert "/character-editor/spells.json" in script
    assert "/spells/preview" in script
    assert "/spells/apply" in script
    assert "expected_learned_before" in script
    assert "editableOnline()" in script
    assert "learn" in script and "unlearn" in script
    assert '@router.get("/spells.json")' in gui
    assert '@router.get("/characters/{char_id}/spells.json")' in gui
    assert '@router.post("/characters/{char_id}/spells/preview")' in gui
    assert '@router.post("/characters/{char_id}/spells/apply")' in gui


if __name__ == "__main__":
    main()
