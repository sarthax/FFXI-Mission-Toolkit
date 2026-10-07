from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from workbench.devtools.spatial import active_zone_plot as canonical
from workbench.runtime import legacy_settings
from workbench.runtime.paths import DATA_ROOT


def test_root_module_is_retired_and_active_backend_is_packaged():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "zone_plot.py").exists()
    assert canonical.EDIT_LOG == DATA_ROOT / "zoneplot_edit_log.sql"


def test_server_root_uses_named_active_environment_by_default(tmp_path, monkeypatch):
    active_root = tmp_path / "lsb-test"
    profile = SimpleNamespace(profile_id=7, family="lsb", root_path=active_root)
    monkeypatch.setattr(legacy_settings, "get_active_server_profile", lambda: profile)
    monkeypatch.setattr(legacy_settings, "get_active_server_root", lambda: active_root)

    assert canonical._server_root() == active_root
    assert canonical.get_server() == "lsb"


def test_explicit_topaz_and_dsp_selectors_remain_legacy_compatible(tmp_path, monkeypatch):
    topaz = tmp_path / "topaz"
    dsp = tmp_path / "dsp"
    monkeypatch.setattr(canonical, "get_topaz_root", lambda: topaz)
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: dsp)

    assert canonical._server_root("topaz") == topaz
    assert canonical._server_root("dsp") == dsp


def test_unique_family_selector_activates_named_profile(monkeypatch):
    selected = []
    profile = SimpleNamespace(profile_id=11, family="dsp", root_path=Path("/configured/dsp"))
    monkeypatch.setattr(legacy_settings, "get_active_server_profile", lambda: None)
    monkeypatch.setattr(legacy_settings, "get_server_profiles", lambda include_disabled=False: [profile])
    monkeypatch.setattr(
        legacy_settings,
        "set_active_server_profile",
        lambda profile_id: selected.append(profile_id) or profile,
    )

    result = canonical.set_server("dsp")
    assert result is profile
    assert selected == [11]


def test_ambiguous_family_selector_requires_named_environment(monkeypatch):
    profiles = [
        SimpleNamespace(profile_id=1, family="lsb", root_path=Path("/live")),
        SimpleNamespace(profile_id=2, family="lsb", root_path=Path("/test")),
    ]
    monkeypatch.setattr(legacy_settings, "get_active_server_profile", lambda: None)
    monkeypatch.setattr(legacy_settings, "get_server_profiles", lambda include_disabled=False: profiles)

    try:
        canonical.set_server("lsb")
    except ValueError as exc:
        assert "Multiple LSB environments" in str(exc)
    else:
        raise AssertionError("family-only selection must not guess between Live/Test profiles")


def test_set_server_preserves_missing_dsp_guard(monkeypatch):
    monkeypatch.setattr(legacy_settings, "get_active_server_profile", lambda: None)
    monkeypatch.setattr(legacy_settings, "get_server_profiles", lambda include_disabled=False: [])
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: None)

    try:
        canonical.set_server("dsp")
    except ValueError as exc:
        assert "DSP server path isn't configured yet" in str(exc)
    else:
        raise AssertionError("DSP target without configured checkout must be rejected")


def test_conf_path_preserves_topaz_and_dsp_names(tmp_path):
    root = tmp_path / "server"
    (root / "conf").mkdir(parents=True)
    dsp_conf = root / "conf" / "map_darkstar.conf"
    dsp_conf.write_text("mysql_host: localhost\n")

    assert canonical._conf_path(root) == dsp_conf
