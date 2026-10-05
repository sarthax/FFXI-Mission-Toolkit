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


def _make_lsb_root(root: Path, *, with_nav: bool = False) -> Path:
    files = {
        "scripts/globals/nyzul/floor_generation.lua": """local lampSpawnPoints =\n{\n    [1] =\n    {\n        [1] = { 1, 2, 3 },\n    },\n}\nlocal layoutSpawnPoints =\n{\n    [1] =\n    {\n        [1] = { x = 4, y = 5, z = 6 },\n    },\n}\n""",
        "scripts/globals/nyzul.lua": """xi = xi or {}\nxi.nyzul = xi.nyzul or {}\nxi.nyzul.FloorLayout =\n{\n    [0] = { -20, -0.5, -380 },\n    [1] = { 10, 20, 30 },\n}\n""",
        "scripts/zones/Nyzul_Isle/IDs.lua": "zones = zones or {}\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if with_nav:
        nav = root / "navmeshes/Nyzul_Isle.nav"
        nav.parent.mkdir(parents=True, exist_ok=True)
        nav.write_bytes(b"TESM")
    return root


def _profile(root: Path, *, family: str = "auto", enabled: bool = True):
    return SimpleNamespace(root_path=root, family=family, enabled=enabled)


def _patch_profiles(monkeypatch, *, active, profiles=(), legacy_dsp=None):
    resolver = canonical._configured_server_source
    monkeypatch.setitem(resolver.__globals__, "get_active_server_profile", lambda: active)
    monkeypatch.setitem(resolver.__globals__, "get_server_profiles", lambda include_disabled=False: list(profiles))
    monkeypatch.setitem(resolver.__globals__, "get_dsp_root", lambda: legacy_dsp)


def test_root_module_is_packaged_implementation():
    assert legacy is canonical
    assert canonical.EXCL_FILE == DATA_ROOT / "nyzul_exclusions.json"


def test_nyzul_gui_routes_explicit_dsp_to_legacy_dsp_adapter(tmp_path, monkeypatch):
    active_root = _make_compatible_root(tmp_path / "dsp")
    _patch_profiles(monkeypatch, active=_profile(active_root, family="dsp"))

    source = canonical._configured_server_source()
    assert source.lineage == "dsp"
    assert source.adapter == "legacy-dsp"
    assert canonical._dsp_root() == active_root
    assert canonical._floor_layouts() == active_root / "scripts/globals/nyzul/floor_layouts.lua"
    assert canonical._nyzul_lua() == active_root / "scripts/globals/nyzul.lua"
    assert canonical._ids_lua() == active_root / "scripts/zones/Nyzul_Isle/IDs.lua"
    assert canonical._default_nav() == active_root / "navmeshes/Nyzul_Isle.nav"


def test_nyzul_gui_routes_explicit_topaz_to_legacy_topaz_adapter(tmp_path, monkeypatch):
    active_root = _make_compatible_root(tmp_path / "topaz")
    _patch_profiles(monkeypatch, active=_profile(active_root, family="topaz"))

    source = canonical._configured_server_source()
    assert source.lineage == "topaz"
    assert source.adapter == "legacy-topaz"


def test_nyzul_gui_uses_native_lsb_adapter_without_navmesh_submodule(tmp_path, monkeypatch):
    lsb_root = _make_lsb_root(tmp_path / "lsb", with_nav=False)
    compatible_root = _make_compatible_root(tmp_path / "dsp")
    _patch_profiles(
        monkeypatch,
        active=_profile(lsb_root, family="lsb"),
        profiles=[_profile(lsb_root, family="lsb"), _profile(compatible_root, family="dsp")],
    )

    source = canonical._configured_server_source()
    assert source.root == lsb_root
    assert source.adapter == "modern-lsb"
    data = canonical.load_data()
    assert data["adapter"]["lineage"] == "lsb"
    assert data["adapter"]["capabilities"]["navmesh_reachability"] is False
    assert data["points"][1] == [[4.0, 5.0, 6.0]]
    assert data["lamps"][1] == [[1.0, 2.0, 3.0]]
    assert data["entrances"][1] == [10.0, 20.0, 30.0]
    # The Domains -> /nyzul page calls both of these after load_data(). Missing
    # xiNavmeshes must degrade only the overlay/reachability, not break the page.
    assert canonical.reachability() == {}
    assert canonical.nav_triangles_bytes() == b""


def test_active_family_mismatch_fails_closed_instead_of_falling_back(tmp_path, monkeypatch):
    broken_lsb = tmp_path / "lsb"
    marker = broken_lsb / "scripts/globals/nyzul/floor_generation.lua"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("-- incomplete modern layout", encoding="utf-8")
    fallback_dsp = _make_compatible_root(tmp_path / "dsp")
    _patch_profiles(
        monkeypatch,
        active=_profile(broken_lsb, family="lsb"),
        profiles=[_profile(fallback_dsp, family="dsp")],
    )

    try:
        canonical._configured_server_source()
    except ValueError as exc:
        text = str(exc)
        assert "declares family 'lsb'" in text
        assert "will not fall through" in text
        assert "floor_generation.lua" in text
    else:
        raise AssertionError("active incompatible lineage must remain a hard error")


def test_unknown_auto_layout_with_nyzul_markers_fails_closed(tmp_path, monkeypatch):
    broken = tmp_path / "custom"
    marker = broken / "scripts/globals/nyzul/floor_generation.lua"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("-- incomplete custom layout", encoding="utf-8")
    _patch_profiles(monkeypatch, active=_profile(broken, family="auto"))

    try:
        canonical._configured_server_source()
    except ValueError as exc:
        text = str(exc)
        assert "does not contain the supported Nyzul source layout" in text
        assert "floor_generation.lua" in text
        assert "will not fall through" in text
    else:
        raise AssertionError("unknown Nyzul source must remain a hard error")


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
