from __future__ import annotations

from pathlib import Path

import zone_plot as legacy
from workbench.devtools.spatial import zone_plot as canonical
from workbench.runtime.paths import DATA_ROOT


def test_root_module_is_packaged_implementation():
    assert legacy is canonical
    assert canonical.EDIT_LOG == DATA_ROOT / "zoneplot_edit_log.sql"


def test_server_root_uses_package_safe_settings_bridge(tmp_path, monkeypatch):
    topaz = tmp_path / "topaz"
    dsp = tmp_path / "dsp"
    monkeypatch.setattr(canonical, "get_topaz_root", lambda: topaz)
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: dsp)

    assert canonical._server_root("topaz") == topaz
    assert canonical._server_root("dsp") == dsp


def test_get_and_set_server_delegate_to_narrow_setting_bridge(monkeypatch):
    stored = {"value": "topaz"}
    monkeypatch.setattr(canonical, "get_zoneplot_server", lambda: stored["value"])
    monkeypatch.setattr(canonical, "set_zoneplot_server", lambda value: stored.__setitem__("value", value))
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: Path("/configured/dsp"))

    assert canonical.get_server() == "topaz"
    canonical.set_server("dsp")
    assert stored["value"] == "dsp"
    assert canonical.get_server() == "dsp"


def test_set_server_preserves_missing_dsp_guard(monkeypatch):
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
