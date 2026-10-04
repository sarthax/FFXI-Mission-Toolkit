from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "gui" / "static" / "character_editor_state_surface.js"


def test_transition_bundle_ui_surfaces_semantic_groups_and_blockers():
    source = ASSET.read_text(encoding="utf-8")

    assert "primary_bundle" in source
    assert "transition_bundle" in source
    assert "Persisted preconditions" in source
    assert "Runtime requirements" in source
    assert "State changes" in source
    assert "Rewards / grants" in source
    assert "Removals / consumption" in source
    assert "Completion" in source
    assert "Next activation / movement" in source
    assert "Why blocked" in source


def test_transition_bundle_ui_keeps_runtime_requirements_read_only():
    source = ASSET.read_text(encoding="utf-8")

    assert "runtime-only requirement" in source
    assert "Runtime-only requirements are shown as requirements" in source
    assert "persisted_condition" in source
    assert "editorButton(row.editor)" in source
