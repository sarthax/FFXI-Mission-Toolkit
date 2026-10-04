from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_weapon_effects_followup_keeps_existing_atomic_save_path_authoritative():
    proposal = (ROOT / "docs" / "workbench" / "ITEM_EDITOR_WEAPON_EFFECTS_FOLLOWUP.md").read_text(encoding="utf-8")
    assert "stagedEffects.mods" in proposal
    assert "stagedEffects.latents" in proposal
    assert "/itemedit/validate" in proposal
    assert "/itemedit/save-atomic" in proposal
    assert "must not add a second save endpoint" in proposal
