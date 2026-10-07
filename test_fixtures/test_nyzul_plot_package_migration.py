from pathlib import Path
from types import SimpleNamespace

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


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_lsb_root(root: Path, *, with_nav: bool = False) -> Path:
    _write(
        root,
        "scripts/globals/nyzul/floor_generation.lua",
        """local lampSpawnPoints =
{
    [1] =
    {
        [1] = { 1, 2, 3 },
    },
}
local layoutSpawnPoints =
{
    [1] =
    {
        [1] = { x = 4, y = 5, z = 6 },
    },
}
local pTableEnemyLeaders =
{
    [1] = { ID.mob.LEADER_OFFSET, ID.mob.LEADER_OFFSET + 24 },
    [40] = { ID.mob.BOSS_OFFSET, ID.mob.BOSS_OFFSET + 2 },
    [100] = { ID.mob.BOSS_OFFSET + 3, ID.mob.BOSS_OFFSET + 5 },
}
local pTableSpecifiedMobs =
{
    [1] = { ID.mob.SPECIFIED_OFFSET, ID.mob.SPECIFIED_OFFSET + 4 },
}
local pTableEvenFloorRandomNMs =
{
    [1] = { ID.mob.NM_OFFSET, ID.mob.NM_OFFSET + 8 },
}
local pTableOddFloorRandomNMs =
{
    [1] = { ID.mob.NM_OFFSET + 9, ID.mob.NM_OFFSET + 17 },
}
local pTableFloorRandomEntities =
{
    [1] = { ID.mob.MOB_OFFSET, ID.mob.MOB_OFFSET + 11 }, -- Aquans
}

local function bossFloor(instance, floorBoss)
    GetMobByID(ID.mob.ARCHAIC_RAMPART_OFFSET, instance):setSpawn(-36, 0, -362, 0)
    GetMobByID(floorBoss, instance):setSpawn(-55.000, 1, -380.000, 250)
end
""",
    )
    _write(
        root,
        "scripts/globals/nyzul.lua",
        """xi = xi or {}
xi.nyzul = xi.nyzul or {}
xi.nyzul.objective =
{
    ELIMINATE_ENEMY_LEADER = 1,
    ELIMINATE_SPECIFIED_ENEMIES = 2,
    ACTIVATE_ALL_LAMPS = 3,
    ELIMINATE_SPECIFIED_ENEMY = 4,
    ELIMINATE_ALL_ENEMIES = 5,
    FREE_FLOOR = 6,
}
xi.nyzul.FloorLayout =
{
    [0] = { -20, -0.5, -380 },
    [1] = { 10, 20, 30 },
}
""",
    )
    _write(
        root,
        "scripts/zones/Nyzul_Isle/IDs.lua",
        """zones = zones or {}
zones[xi.zone.NYZUL_ISLE] =
{
    mob =
    {
        ARCHAIC_RAMPART_OFFSET = GetFirstID('Archaic_Rampart'),
        BOSS_OFFSET = GetFirstID('Adamantoise'),
        DAHAK = GetFirstID('Dahak'),
        GEAR_OFFSET = GetFirstID('Archaic_Gear'),
        LEADER_OFFSET = GetFirstID('Leader_0'),
        MOB_OFFSET = GetFirstID('Greatclaw'),
        NM_OFFSET = GetFirstID('NM_0'),
        SPECIFIED_OFFSET = GetFirstID('Heraldic_Imp'),
    },
    npc =
    {
        RUNE_OF_TRANSFER_OFFSET = GetFirstID('Rune_of_Transfer'),
    },
}
""",
    )

    mob_rows: list[tuple[int, str]] = [
        (100, "Adamantoise"), (101, "Behemoth"), (102, "Fafnir"),
        (103, "Khimaira"), (104, "Hydra"), (105, "Cerberus"),
        (106, "Archaic_Rampart"), (107, "Dahak"), (108, "Archaic_Gear"),
    ]
    mob_rows.extend((200 + i, f"Leader_{i}") for i in range(25))
    mob_rows.extend((300 + i, "Heraldic_Imp") for i in range(5))
    mob_rows.extend((400 + i, f"NM_{i}") for i in range(18))
    mob_rows.extend((500 + i, "Greatclaw") for i in range(12))
    mob_yaml = ["spawns:"]
    for entity_id, name in mob_rows:
        mob_yaml.extend([f"  {entity_id}:", f"    template: {name}", "    at: [1, 1, 1]"])
    _write(root, "data/zones/nyzul_isle/mobs.yaml", "\n".join(mob_yaml) + "\n")
    _write(
        root,
        "data/zones/nyzul_isle/npcs.yaml",
        """npcs:
  700:
    script: Rune_of_Transfer
    at: [1, 1, 1]
""",
    )

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


def test_root_module_is_retired():
    assert not (Path(__file__).resolve().parents[1] / "nyzul_plot.py").exists()
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
    assert data["adapter"]["capabilities"]["numeric_entity_ids"] is True
    assert data["adapter"]["capabilities"]["navmesh_reachability"] is False
    assert data["points"][1] == [[4.0, 5.0, 6.0]]
    assert data["lamps"][1] == [[1.0, 2.0, 3.0]]
    assert data["entrances"][1] == [10.0, 20.0, 30.0]
    assert data["leaders"][0]["id"] == 200
    assert data["bosses"]["ADAMANTOISE"] == 100
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
