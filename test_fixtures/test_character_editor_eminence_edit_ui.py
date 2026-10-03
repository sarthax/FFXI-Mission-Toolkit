#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_eminence_edit.js").read_text(encoding="utf-8")

    assert '/static/character_editor_eminence.js' in wrapper
    assert '/static/character_editor_eminence_edit.js' in wrapper
    assert wrapper.index('/static/character_editor_eminence.js') < wrapper.index('/static/character_editor_eminence_edit.js')
    assert "key === 'missions-quests'" in script
    assert "activeCategoryData?.packed?.eminence" in script
    assert "editableOnline() && entry.editable === true" in script
    assert "capability:'eminence'" in script
    assert "/packed/preview" in script
    assert "/packed/apply" in script
    assert "expected_before_sha256:preview.before_sha256" in script
    assert "approved:true" in script
    assert "kind:'active_slot'" in script
    assert "kind:'completion'" in script
    assert 'max="65535"' in script
    assert 'max="4294967295"' in script
    assert 'max="4095"' in script
    assert "editing locked until offline" in script
    assert "record_id:0, progress:0" in script


if __name__ == "__main__":
    main()
