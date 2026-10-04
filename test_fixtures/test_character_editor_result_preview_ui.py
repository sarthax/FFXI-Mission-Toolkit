from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "gui" / "static" / "character_editor_state_surface.js"


def test_progression_result_preview_ui_contract():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "Expected result if this action completes" in source
    assert "projected_changes" in source
    assert "projectionText" in source
    assert "current unknown" in source
    assert "Read-only projection from modeled effects; no character state is changed here." in source
    assert "ce-prog-projection" in source
