import sqlite3

from workbench.devtools.features.trace_catalog import provider_relationships


def test_item_subtype_links_to_base_item_across_server_lineages():
    for prefix in ("sql", "lsb", "topaz", "dsp"):
        con = sqlite3.connect(":memory:")
        con.execute(f"CREATE TABLE {prefix}_item_basic (itemid INTEGER, name TEXT)")
        con.execute(f"CREATE TABLE {prefix}_item_equipment (itemid INTEGER, name TEXT)")
        con.execute(f"INSERT INTO {prefix}_item_basic VALUES (100, 'base item')")
        con.execute(f"INSERT INTO {prefix}_item_equipment VALUES (100, 'equipment item')")

        links = provider_relationships(con, f"catalog:{prefix}_item_equipment:100")

        assert links == [{
            "relationship": "EXTENDS_ITEM_BASIC",
            "source_node": f"catalog:{prefix}_item_equipment:100",
            "target_node": f"catalog:{prefix}_item_basic:100",
            "target_name": "base item",
            "target_type": "ITEM",
            "provider_native": True,
        }]


def test_mob_group_links_to_unique_pool_and_blue_spell_links_to_mob_skill():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE topaz_mob_groups (zoneid INTEGER, groupid INTEGER, name TEXT, poolid INTEGER)")
    con.execute("CREATE TABLE topaz_mob_pools (poolid INTEGER, name TEXT)")
    con.execute("INSERT INTO topaz_mob_groups VALUES (1, 7, 'group', 55)")
    con.execute("INSERT INTO topaz_mob_pools VALUES (55, 'pool')")

    group_links = provider_relationships(con, "catalog:topaz_mob_groups:zoneid=1&groupid=7")
    assert group_links[0]["relationship"] == "USES_MOB_POOL"
    assert group_links[0]["target_node"] == "catalog:topaz_mob_pools:55"

    con.execute("CREATE TABLE dsp_blue_spell_list (spellid INTEGER, mob_skill_id INTEGER)")
    con.execute("CREATE TABLE dsp_mob_skills (mob_skill_id INTEGER, name TEXT)")
    con.execute("INSERT INTO dsp_blue_spell_list VALUES (10, 400)")
    con.execute("INSERT INTO dsp_mob_skills VALUES (400, 'mob skill')")

    spell_links = provider_relationships(con, "catalog:dsp_blue_spell_list:10")
    assert spell_links[0]["relationship"] == "USES_MOB_SKILL"
    assert spell_links[0]["target_node"] == "catalog:dsp_mob_skills:400"


def test_server_provider_link_does_not_guess_ambiguous_target_identity():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE lsb_item_basic (itemid INTEGER, name TEXT)")
    con.execute("CREATE TABLE lsb_item_weapon (itemid INTEGER, name TEXT)")
    con.execute("INSERT INTO lsb_item_basic VALUES (100, 'duplicate a')")
    con.execute("INSERT INTO lsb_item_basic VALUES (100, 'duplicate b')")
    con.execute("INSERT INTO lsb_item_weapon VALUES (100, 'weapon')")

    assert provider_relationships(con, "catalog:lsb_item_weapon:100") == []
