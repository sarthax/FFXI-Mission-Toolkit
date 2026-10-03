from pathlib import Path
from types import SimpleNamespace

from workbench.editors.character.gui import router
from workbench.runtime import legacy_settings
from workbench.runtime.paths import GUI_ROOT


def test_environment_api_is_mounted_below_live_character_editor_router():
    paths = {route.path for route in router.routes}
    assert "/character-editor/environments/profiles.json" in paths
    assert "/character-editor/environments/profiles" in paths
    assert "/character-editor/environments/profiles/{profile_id}/activate" in paths
    assert "/character-editor/environments/profiles/{profile_id}/test" in paths
    assert "/character-editor/environments/profiles/{profile_id}/delete" in paths


def test_named_active_profile_overrides_legacy_server_root(monkeypatch):
    selected = SimpleNamespace(root_path=Path("D:/servers/lsb-test"), family="lsb")
    monkeypatch.setattr(legacy_settings, "get_active_server_profile", lambda: selected)
    monkeypatch.setattr(
        legacy_settings,
        "_module",
        lambda: (_ for _ in ()).throw(AssertionError("legacy fallback should not be used")),
    )
    assert legacy_settings.get_active_server_root() == Path("D:/servers/lsb-test")


def test_profile_family_controls_known_legacy_sql_prefix(monkeypatch):
    monkeypatch.setattr(
        legacy_settings,
        "get_active_server_profile",
        lambda: SimpleNamespace(root_path=Path("D:/servers/dsp"), family="dsp"),
    )
    assert legacy_settings.get_active_sql_prefix() == "dsp_"


def test_character_editor_loads_server_profile_selector_asset():
    text = (GUI_ROOT / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    assert "/static/character_editor_server_profiles.js" in text
    script = (GUI_ROOT / "static" / "character_editor_server_profiles.js").read_text(encoding="utf-8")
    assert "/character-editor/environments" in script
    assert "Manage environments" in script
    assert "Test connection" in script
    assert "LIVE" in script
