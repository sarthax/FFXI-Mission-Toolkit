from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    gui = (ROOT / "src" / "workbench" / "editors" / "character" / "gui.py").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_blacklist.js").read_text(encoding="utf-8")
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")

    assert '/characters/{char_id}/blacklist.json' in gui
    assert '/characters/{char_id}/blacklist/preview' in gui
    assert '/characters/{char_id}/blacklist/apply' in gui
    assert 'expected_present_before' in gui
    assert 'approved=true' in gui
    assert 'build_blacklist_edit_plan' in gui
    assert 'apply_blacklist_edit' in gui

    assert '/static/character_editor_blacklist.js' in wrapper
    assert '/blacklist/preview' in script
    assert '/blacklist/apply' in script
    assert 'expected_present_before' in script
    assert 'editableOnline()' in script
    assert 'editing locked until offline' in script
    assert 'Find' in script
    assert 'Already blacklisted' in script
    assert '>Remove<' in script
    assert "action === 'add'" in script


if __name__ == "__main__":
    main()
