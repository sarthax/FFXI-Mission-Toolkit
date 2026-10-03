from pathlib import Path

from workbench.runtime.paths import GUI_ROOT


def test_base_shell_loads_shared_server_environment_selector():
    base = (GUI_ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert '/static/server_environment_selector.js' in base


def test_shared_selector_targets_zone_and_item_editors_with_named_profiles():
    script = (GUI_ROOT / "static" / "server_environment_selector.js").read_text(encoding="utf-8")
    assert "'/zoneplot2'" in script
    assert "'/itemedit'" in script
    assert "/character-editor/environments/profiles.json" in script
    assert "profile:${Number(profile.profile_id)}" in script
    assert "Manage environments" in script
    assert "Switch active server environment to LIVE profile" in script
    assert "window.addEventListener('load'" in script
