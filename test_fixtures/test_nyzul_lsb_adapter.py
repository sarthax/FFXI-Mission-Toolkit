from pathlib import Path

import pytest

from workbench.devtools.domains.nyzul_adapters import (
    classify_root,
    has_lsb_layout,
    load_lsb_data,
)


def _write(root: Path, rel: str, text: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _lsb_fixture(root: Path) -> Path:
    _write(
        root,
        "scripts/globals/nyzul/floor_generation.lua",
        """local lampSpawnPoints =
{
    [1] =
    {
        [1] = { 1.5, 0, -2.5 },
        [2] = { 3, -0.5, 4 },
    },
}

local layoutSpawnPoints =
{
    [1] =
    {
        [1] = { x = 10.5, y = 0, z = -11.5 },
        [2] = { x = 12, y = -0.5, z = 13 },
    },
}

local pTableEnemyLeaders =
{
    [1] = { ID.mob.LEADER_OFFSET, ID.mob.LEADER_OFFSET + 24 }, -- regular leaders
    [40] = { ID.mob.BOSS_OFFSET, ID.mob.BOSS_OFFSET + 2 }, -- early bosses
}

local pTableSpecifiedMobs =
{
    [1] = { ID.mob.SPECIFIED_OFFSET, ID.mob.SPECIFIED_OFFSET + 4 }, -- Heraldic Imp x5
}

local pTableEvenFloorRandomNMs =
{
    [1] = { ID.mob.NM_OFFSET, ID.mob.NM_OFFSET + 8 }, -- floors 1-20
}

local pTableOddFloorRandomNMs =
{
    [1] = { ID.mob.NM_OFFSET + 9, ID.mob.NM_OFFSET + 17 }, -- floors 1-20
}

local pTableFloorRandomEntities =
{
    [1] = { ID.mob.MOB_OFFSET, ID.mob.MOB_OFFSET + 11 }, -- Aquans
}
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
    ELIMINATE_ALL_ENEMIES = 5,
}
xi.nyzul.FloorLayout =
{
    [0] = { -20, -0.5, -380 },
    [1] = { 380, -0.5, -500 },
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
        BOSS_OFFSET = GetFirstID('Adamantoise'),
        LEADER_OFFSET = GetFirstID('Mokke'),
        NM_OFFSET = GetFirstID('Bat_Eye'),
    },
    npc =
    {
        RUNE_OF_TRANSFER_OFFSET = GetFirstID('Rune_of_Transfer'),
        ALEXANDER_IMAGE = GetTableOfIDs('Alexander_Image'),
    },
}
""",
    )
    nav = root / "navmeshes/Nyzul_Isle.nav"
    nav.parent.mkdir(parents=True, exist_ok=True)
    nav.write_bytes(b"TESM")
    return root


def test_modern_lsb_fixture_is_classified_native(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    assert has_lsb_layout(root)
    source = classify_root(root)
    assert source is not None
    assert source.lineage == "lsb"
    assert source.adapter == "modern-lsb"


def test_modern_lsb_spatial_and_objective_data_are_normalized(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    data = load_lsb_data(root)

    assert data["lamps"][1] == [[1.5, 0.0, -2.5], [3.0, -0.5, 4.0]]
    assert data["points"][1] == [[10.5, 0.0, -11.5], [12.0, -0.5, 13.0]]
    assert data["entrances"] == {0: [-20.0, -0.5, -380.0], 1: [380.0, -0.5, -500.0]}
    assert data["objectives"] == {"ELIMINATE_ENEMY_LEADER": 1, "ELIMINATE_ALL_ENEMIES": 5}
    assert data["adapter"]["capabilities"]["numeric_entity_ids"] is False


def test_modern_lsb_preserves_runtime_id_lineage_without_inventing_numbers(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    data = load_lsb_data(root)

    assert data["leaders"] == []
    assert data["bosses"] == {}
    assert data["lineage"]["runtime_ids"]["mob"]["LEADER_OFFSET"] == "GetFirstID('Mokke')"
    assert data["lineage"]["runtime_ids"]["npc"]["RUNE_OF_TRANSFER_OFFSET"] == "GetFirstID('Rune_of_Transfer')"
    assert data["lineage"]["enemy_leaders"][1]["first"] == "ID.mob.LEADER_OFFSET"
    assert data["lineage"]["enemy_leaders"][1]["last"] == "ID.mob.LEADER_OFFSET + 24"


def test_partial_modern_layout_fails_closed(tmp_path):
    root = tmp_path / "partial"
    _write(root, "scripts/globals/nyzul/floor_generation.lua", "local lampSpawnPoints = {}\n")
    _write(root, "scripts/globals/nyzul.lua", "xi.nyzul.FloorLayout = {}\n")
    _write(root, "scripts/zones/Nyzul_Isle/IDs.lua", "zones = zones or {}\n")
    nav = root / "navmeshes/Nyzul_Isle.nav"
    nav.parent.mkdir(parents=True, exist_ok=True)
    nav.write_bytes(b"TESM")

    assert not has_lsb_layout(root)
    assert classify_root(root) is None
    with pytest.raises(ValueError, match="not a recognized modern Nyzul layout"):
        load_lsb_data(root)
