from pathlib import Path
from types import SimpleNamespace

import nyzul_plot as legacy
from workbench.devtools.domains import nyzul_plot as canonical
from workbench.runtime.paths import DATA_ROOT


def _make_compatible_root(root: Path) -> Path:
    for rel in (
        "scripts/globals/nyzul/floor_layouts.lua",
        "scripts/globals/nyzul.lua",
        "scripts/zones/Nyzul_Isle/IDs.lua",
        "navmeshes/Nyzul_Isle.nav",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return root


def _profile(root: Path, *, enabled: bool = True):
    return SimpleNamespace(root_path=root, enabled=enabled)


def test_root_module_is_packaged_implementation():
    assert legacy is canonical
    assert canonical.EXCL_FILE == DATA_ROOT / "nyzul_exclusions.json"


def test_nyzul_gui_prefers_active_compatible_environment(tmp_path, monkeypatch):
    active_root = _make_compatible_root(tmp_path / "active")
    other_root = _make_compatible_root(tmp_path / "other")
    resolver = canonical._configured_server_root
    monkeypatch.setitem(resolver.__globals__, "get_active_server_profile", lambda: _profile(active_root))
    monkeypatch.setitem(resolver.__globals__, "get_server_profiles", lambda include_disabled=False: [_profile(other_root)])
    monkeypatch.setitem(resolver.__globals__, "get_dsp_root", lambda: None)

    assert canonical._dsp_root() == active_root
    assert canonical._floor_layouts() == active_root / "scripts/globals/nyzul/floor_layouts.lua"
    assert canonical._nyzul_lua() == active_root / "scripts/globals/nyzul.lua"
    assert canonical._ids_lua() == active_root / "scripts/zones/Nyzul_Isle/IDs.lua"
    assert canonical._default_nav() == active_root / "navmeshes/Nyzul_Isle.nav"


def test_nyzul_gui_falls_back_from_incompatible_active_profile(tmp_path, monkeypatch):
    lsb_root = tmp_path / "lsb"
    floor_generation = lsb_root / "scripts/globals/nyzul/floor_generation.lua"
    floor_generation.parent.mkdir(parents=True, exist_ok=True)
    floor_generation.write_text("-- modern LSB layout", encoding="utf-8")
    compatible_root = _make_compatible_root(tmp_path / "dsp")

    resolver = canonical._configured_server_root
    monkeypatch.setitem(resolver.__globals__, "get_active_server_profile", lambda: _profile(lsb_root))
    monkeypatch.setitem(
        resolver.__globals__,
        "get_server_profiles",
        lambda include_disabled=False: [_profile(lsb_root), _profile(compatible_root)],
    )
    monkeypatch.setitem(resolver.__globals__, "get_dsp_root", lambda: None)

    assert canonical._dsp_root() == compatible_root


def test_missing_compatible_nyzul_environment_has_actionable_error(tmp_path, monkeypatch):
    resolver = canonical._configured_server_root
    monkeypatch.setitem(resolver.__globals__, "get_active_server_profile", lambda: _profile(tmp_path / "lsb"))
    monkeypatch.setitem(resolver.__globals__, "get_server_profiles", lambda include_disabled=False: [])
    monkeypatch.setitem(resolver.__globals__, "get_dsp_root", lambda: None)

    try:
        canonical._dsp_root()
    except ValueError as exc:
        text = str(exc)
        assert "configured server environment" in text
        assert "Nyzul layout files" in text
    else:
        raise AssertionError("missing compatible Nyzul source must remain a hard error")


def test_exclusions_round_trip_at_configured_runtime_path(tmp_path, monkeypatch):
    exclusions = tmp_path / "data" / "nyzul_exclusions.json"
    monkeypatch.setattr(canonical, "EXCL_FILE", exclusions)

    assert canonical.load_exclusions() == {"points": {}, "lamps": {}}
    payload = {"points": {"1": [2, 3]}, "lamps": {"4": [5]}}
    canonical.save_exclusions(payload)

    assert exclusions.exists()
    assert canonical.load_exclusions() == payload


def test_closest_point_triangle_geometry_is_unchanged():
    point = canonical._closest_point_triangle(
        (0.25, 2.0, 0.25),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    assert point == (0.25, 0.0, 0.25)
