#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_campaign_edit.js").read_text(encoding="utf-8")

    assert '/static/character_editor_campaign.js' in wrapper
    assert '/static/character_editor_campaign_edit.js' in wrapper
    assert wrapper.index('/static/character_editor_campaign.js') < wrapper.index('/static/character_editor_campaign_edit.js')

    assert "key === 'missions-quests'" in script
    assert "activeCategoryData?.packed?.campaign" in script
    assert "editableOnline() && entry.editable === true" in script
    assert "capability:'campaign'" in script
    assert "/packed/preview" in script
    assert "/packed/apply" in script
    assert "expected_before_sha256:preview.before_sha256" in script
    assert "approved:true" in script
    assert 'max="65535"' in script
    assert 'max="511"' in script
    assert "editing locked until offline" in script
    assert "Campaign completion ID must be between 0 and 511." in script


if __name__ == "__main__":
    main()
