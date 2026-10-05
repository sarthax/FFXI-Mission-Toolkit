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


def _mob_spawns() -> str:
    rows: list[tuple[int, str]] = [
        (100, "Adamantoise"),
        (101, "Behemoth"),
        (102, "Fafnir"),
        (103, "Khimaira"),
        (104, "Hydra"),
        (105, "Cerberus"),
        (106, "Archaic_Rampart"),
        (107, "Dahak"),
        (108, "Archaic_Gear"),
    ]
    rows.extend((200 + i, f"Leader_{i}") for i in range(25))
    rows.extend((300 + i, "Heraldic_Imp") for i in range(5))
    rows.extend((400 + i, f"NM_{i}") for i in range(18))
    rows.extend((500 + i, "Greatclaw" if i < 4 else "Scorpion" if i < 8 else "Pugil") for i in range(12))
    body = ["spawns:"]
    for entity_id, name in rows:
        body.extend([f"  {entity_id}:", f"    template: {name}", "    at: [1, 1, 1]"])
    return "\n".join(body) + "\n"


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
    [100] = { ID.mob.BOSS_OFFSET + 3, ID.mob.BOSS_OFFSET + 5 }, -- later bosses
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
        ALEXANDER_IMAGE = GetTableOfIDs('Alexander_Image'),
    },
}
""",
    )
    _write(root, "data/zones/nyzul_isle/mobs.yaml", _mob_spawns())
    _write(
        root,
        "data/zones/nyzul_isle/npcs.yaml",
        """npcs:
  700:
    script: Rune_of_Transfer
    at: [1, 1, 1]
  710:
    script: Alexander_Image
    at: [1, 1, 1]
  711:
    script: Alexander_Image
    at: [1, 1, 1]
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


def test_modern_lsb_spatial_objective_and_entity_data_are_normalized(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    data = load_lsb_data(root)

    assert data["lamps"][1] == [[1.5, 0.0, -2.5], [3.0, -0.5, 4.0]]
    assert data["points"][1] == [[10.5, 0.0, -11.5], [12.0, -0.5, 13.0]]
    assert data["entrances"] == {0: [-20.0, -0.5, -380.0], 1: [380.0, -0.5, -500.0]}
    assert data["objectives"] == {
        "ELIMINATE_ENEMY_LEADER": 1,
        "ELIMINATE_SPECIFIED_ENEMIES": 2,
        "ACTIVATE_ALL_LAMPS": 3,
        "ELIMINATE_SPECIFIED_ENEMY": 4,
        "ELIMINATE_ALL_ENEMIES": 5,
        "FREE_FLOOR": 6,
    }
    assert data["adapter"]["capabilities"]["numeric_entity_ids"] is True
    assert data["adapter"]["capabilities"]["native_generation_semantics"] is True
    assert data["adapter"]["capabilities"]["entity_id_source"] == "zone-yaml"

    assert data["leaders"][0] == {"id": 200, "name": "Leader_0"}
    assert data["leaders"][-1] == {"id": 224, "name": "Leader_24"}
    assert data["groups"] == [{"id": 300, "count": 5, "name": "Heraldic_Imp"}]
    assert data["nm"] == {"NM_EVEN": [400], "NM_ODD": [409]}
    assert data["bosses"]["ADAMANTOISE"] == 100
    assert data["bosses"]["CERBERUS"] == 105
    assert data["bosses"]["ARCHAIC_RAMPART"] == 106
    assert data["families"][1]["label"] == "Aquans"
    assert data["families"][1]["groups"] == [
        {"id": 500, "count": 4, "name": "Greatclaw"},
        {"id": 504, "count": 4, "name": "Scorpion"},
        {"id": 508, "count": 4, "name": "Pugil"},
    ]


def test_modern_lsb_generation_semantics_are_native_and_source_derived(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    data = load_lsb_data(root)

    assert data["generation"]["editor_objective_to_native"] == {
        1: 6,
        2: 5,
        3: 1,
        4: 2,
        5: 3,
        6: 4,
    }
    boss_floor = data["generation"]["boss_floor"]
    assert boss_floor["floor_layout"] == 0
    assert boss_floor["rampart_spawn"] == {"position": [-36.0, 0.0, -362.0], "rotation": 0}
    assert boss_floor["boss_spawn"] == {"position": [-55.0, 1.0, -380.0], "rotation": 250}


def test_modern_lsb_preserves_runtime_id_lineage_and_resolved_ids(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    data = load_lsb_data(root)

    assert data["lineage"]["runtime_ids"]["mob"]["LEADER_OFFSET"] == "GetFirstID('Leader_0')"
    assert data["lineage"]["runtime_ids"]["npc"]["RUNE_OF_TRANSFER_OFFSET"] == "GetFirstID('Rune_of_Transfer')"
    assert data["lineage"]["resolved_runtime_ids"]["mob"]["LEADER_OFFSET"] == 200
    assert data["lineage"]["resolved_runtime_ids"]["npc"]["ALEXANDER_IMAGE"] == [710, 711]
    assert data["lineage"]["enemy_leaders"][1]["first"] == "ID.mob.LEADER_OFFSET"
    assert data["lineage"]["enemy_leaders"][1]["last"] == "ID.mob.LEADER_OFFSET + 24"
    assert data["lineage"]["enemy_leaders"][1]["first_id"] == 200
    assert data["lineage"]["enemy_leaders"][1]["last_id"] == 224


def test_missing_zone_entity_mapping_fails_closed(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    mobs = root / "data/zones/nyzul_isle/mobs.yaml"
    mobs.write_text(mobs.read_text(encoding="utf-8").replace("template: Heraldic_Imp", "template: Other_Imp"), encoding="utf-8")

    with pytest.raises(ValueError, match="SPECIFIED_OFFSET"):
        load_lsb_data(root)


def test_missing_native_generation_semantics_fail_closed(tmp_path):
    root = _lsb_fixture(tmp_path / "lsb")
    floor = root / "scripts/globals/nyzul/floor_generation.lua"
    floor.write_text(
        floor.read_text(encoding="utf-8").replace(
            "GetMobByID(floorBoss, instance):setSpawn(-55.000, 1, -380.000, 250)",
            "-- missing boss spawn",
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="floor boss fixed spawn"):
        load_lsb_data(root)


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
