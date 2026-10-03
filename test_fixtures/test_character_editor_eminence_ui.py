#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_eminence.js").read_text(encoding="utf-8")

    assert '/static/character_editor_eminence.js' in wrapper
    assert "key === 'missions-quests'" in script
    assert "activeCategoryData?.packed?.eminence" in script
    assert "Records of Eminence" in script
    assert "time-limited slot" in script
    assert "Filter RoE record name or ID" in script
    assert "checkout RoE catalog unavailable" in script
    assert "/packed/preview" not in script
    assert "/packed/apply" not in script
    assert "read only" in script


if __name__ == "__main__":
    main()
