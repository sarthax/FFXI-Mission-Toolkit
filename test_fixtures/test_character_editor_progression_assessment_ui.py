from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "gui" / "static" / "character_editor_state_surface.js"


def test_progression_assessment_ui_contract():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "assessmentHtml" in source
    assert "WAITING_RUNTIME" in source
    assert "BLOCKED_PERSISTED" in source
    assert "No modeled next action" in source
    assert "progression.assessment" in source
    assert "ce-prog-assessment" in source
    assert "correction_targets" in source
