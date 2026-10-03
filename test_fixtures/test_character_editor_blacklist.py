from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    schema = (ROOT / "src" / "workbench" / "editors" / "character" / "schema.py").read_text(encoding="utf-8")
    tx = (ROOT / "src" / "workbench" / "editors" / "character" / "blacklist_transactions.py").read_text(encoding="utf-8")
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_blacklist.js").read_text(encoding="utf-8")

    assert '"charid_owner"' in schema
    assert '"blacklist": ("char_blacklist",)' in schema
    assert "build_blacklist_edit_plan" in tx
    assert "apply_blacklist_edit" in tx
    assert "character_online" in tx and "online_state_unknown" in tx
    assert "self_target" in tx and "target_unknown" in tx and "no_change" in tx
    assert "INSERT INTO `char_blacklist`" in tx
    assert "DELETE FROM `char_blacklist`" in tx
    assert "Blacklist state changed since preview" in tx
    assert '/static/character_editor_blacklist.js' in wrapper
    assert "key === 'advanced'" in script
    assert "offline editing enabled" in script
    assert "editing locked until offline" in script
    assert "/blacklist/preview" in script and "/blacklist/apply" in script
    assert "expected_present_before" in script and "approved:true" in script
    assert "/packed/preview" not in script and "/fields/apply" not in script


if __name__ == "__main__":
    main()
