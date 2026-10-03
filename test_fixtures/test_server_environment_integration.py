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
    selected = SimpleNamespace(
        profile_id=7,
        name="LSB Test",
        environment="test",
        root_path=Path("D:/servers/lsb-test"),
        family="lsb",
        enabled=True,
    )
    monkeypatch.setattr(legacy_settings, "get_active_server_profile", lambda: selected)
    monkeypatch.setattr(
        legacy_settings,
        "_module",
        lambda: (_ for _ in ()).throw(AssertionError("legacy fallback should not be used")),
    )
    assert legacy_settings.get_active_server_root() == Path("D:/servers/lsb-test")
    assert legacy_settings.get_active_server_identity() == {
        "profile_id": 7,
        "name": "LSB Test",
        "environment": "test",
        "family": "lsb",
        "server_root": "D:/servers/lsb-test",
        "enabled": True,
        "is_active": True,
        "legacy": False,
    }


def test_profile_family_controls_index_prefix(monkeypatch):
    monkeypatch.setattr(
        legacy_settings,
        "get_active_server_profile",
        lambda: SimpleNamespace(root_path=Path("D:/servers/dsp"), family="dsp"),
    )
    assert legacy_settings.get_active_sql_prefix() == "dsp_"

    monkeypatch.setattr(
        legacy_settings,
        "get_active_server_profile",
        lambda: SimpleNamespace(root_path=Path("D:/servers/lsb"), family="lsb"),
    )
    assert legacy_settings.get_active_sql_prefix() == "sql_"


def test_legacy_zoneplot_selector_reflects_named_topaz_or_dsp_profile(monkeypatch):
    monkeypatch.setattr(
        legacy_settings,
        "get_active_server_profile",
        lambda: SimpleNamespace(family="dsp"),
    )
    assert legacy_settings.get_zoneplot_server() == "dsp"


def test_character_editor_loads_server_profile_selector_asset():
    text = (GUI_ROOT / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    assert "/static/character_editor_server_profiles.js" in text
    script = (GUI_ROOT / "static" / "character_editor_server_profiles.js").read_text(encoding="utf-8")
    assert "/character-editor/environments" in script
    assert "Manage environments" in script
    assert "Test connection" in script
    assert "LIVE" in script
