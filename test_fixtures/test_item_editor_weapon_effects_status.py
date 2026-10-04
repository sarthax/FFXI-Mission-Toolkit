from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_weapon_effects_status_keeps_server_changes_out_of_toolkit_slice():
    text = (ROOT / "docs" / "workbench" / "ITEM_EDITOR_WEAPON_EFFECTS_STATUS.md").read_text(encoding="utf-8")
    assert "changes to DSP/Topaz/LSB server code" in text
    assert "existing atomic save path" in text
