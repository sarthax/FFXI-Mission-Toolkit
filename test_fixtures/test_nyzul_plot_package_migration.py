from pathlib import Path

import nyzul_plot as legacy
from workbench.devtools.domains import nyzul_plot as canonical
from workbench.runtime.paths import DATA_ROOT


def test_root_module_is_packaged_implementation():
    assert legacy is canonical
    assert canonical.EXCL_FILE == DATA_ROOT / "nyzul_exclusions.json"


def test_dsp_root_is_resolved_lazily_through_package_bridge(tmp_path, monkeypatch):
    dsp_root = tmp_path / "dsp"
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: dsp_root)

    assert canonical._dsp_root() == dsp_root
    assert canonical._floor_layouts() == dsp_root / "scripts/globals/nyzul/floor_layouts.lua"
    assert canonical._nyzul_lua() == dsp_root / "scripts/globals/nyzul.lua"
    assert canonical._ids_lua() == dsp_root / "scripts/zones/Nyzul_Isle/IDs.lua"
    assert canonical._default_nav() == dsp_root / "navmeshes/Nyzul_Isle.nav"


def test_missing_dsp_root_preserves_existing_error(monkeypatch):
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: None)

    try:
        canonical._dsp_root()
    except ValueError as exc:
        assert "DSP server path isn't configured yet" in str(exc)
    else:
        raise AssertionError("missing DSP path must remain a hard error when DSP data is requested")


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
