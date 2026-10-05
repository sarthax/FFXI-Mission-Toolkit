from workbench.devtools.domains.nyzul_adapters import _block, _indexed_subtables, _parse_range_table


def test_padded_lsb_layout_indexes_match_upstream_style():
    text = """local layoutSpawnPoints =
{
    [ 1] =
    {
        [ 1] = { x = 1, y = 2, z = 3 },
    },
    [16] =
    {
        [91] = { x = 4, y = 5, z = 6 },
    },
}
"""
    block = _block(text, r"(?m)^local\s+layoutSpawnPoints\s*=")
    tables = _indexed_subtables(block)
    assert sorted(tables) == [1, 16]
    assert "[ 1] = { x = 1" in tables[1]
    assert "[91] = { x = 4" in tables[16]


def test_padded_lsb_range_indexes_match_upstream_style():
    text = """local pTableFloorRandomEntities =
{
    [ 1] = { ID.mob.MOB_OFFSET,       ID.mob.MOB_OFFSET +  11 }, -- Aquans
    [17] = { ID.mob.GEAR_OFFSET,      ID.mob.GEAR_OFFSET +   4 }, -- Archaic Gears
}
"""
    rows = _parse_range_table(text, "pTableFloorRandomEntities")
    assert rows[1] == {
        "first": "ID.mob.MOB_OFFSET",
        "last": "ID.mob.MOB_OFFSET +  11",
        "note": "Aquans",
    }
    assert rows[17]["first"] == "ID.mob.GEAR_OFFSET"
    assert rows[17]["last"] == "ID.mob.GEAR_OFFSET +   4"
