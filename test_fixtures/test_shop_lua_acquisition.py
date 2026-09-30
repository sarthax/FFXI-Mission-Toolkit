#!/usr/bin/env python3
"""Regression for audited LSB Lua shop acquisition extraction."""
from __future__ import annotations

from workbench.adapters.servers.shop_lua import (
    parse_guild_shops_data,
    parse_npc_shop_script,
)
from workbench.core.services.acquisition_catalog import (
    build_acquisition_catalog,
    verified_external_item_ids,
)


NPC_SHOP = r"""
entity.onTrigger = function(player, npc)
    local stock =
    {
        { xi.item.LEATHER_BANDANA, 439 },
        { xi.item.BRONZE_CAP, 168 },
        { 936, 250 },
    }

    player:showText(npc, ID.text.SHOP_DIALOG)
    xi.shop.general(player, stock, xi.fameArea.WINDURST)
end
"""


NATION_SHOP = r"""
entity.onTrigger = function(player, npc)
    local stock =
    {
        { xi.item.POTION, 300 },
    }

    xi.shop.nation(player, stock, xi.nation.BASTOK)
end
"""


GUILD_SHOPS = r"""
xi.data.guildShops =
{
    ['Achika'] =
    {
        hours = { 9, 23 },
        stock =
        {
            { id = xi.item.HACHIMAKI, initial = 36, maxStock = 60, targetStock = 45, buyMax = 4125, restockRate = 3 },
            { id = 1888, initial = 0, maxStock = 60, targetStock = 45, buyMax = 900, restockRate = 0, noSell = true },
        },
    },

    ['Alias Vendor'] =
    {
        sharedStock = 'Achika',
    },
}
"""


DYNAMIC_UNSUPPORTED = r"""
entity.onTrigger = function(player, npc)
    local stock = buildDynamicStock(player)
    xi.shop.general(player, stock)
end
"""


def main():
    regular = parse_npc_shop_script(
        NPC_SHOP,
        source_path="scripts/zones/Mhaura/npcs/Graine.lua",
    )
    assert regular["status"] == "OK", regular
    shop = regular["shop"]
    assert shop.shop_kind == "GENERAL", shop
    assert shop.vendor_name == "Graine", shop
    assert len(shop.items) == 3, shop
    assert shop.items[0].item_literal == "xi.item.LEATHER_BANDANA", shop
    assert shop.items[0].price == 439, shop
    assert shop.items[2].item_literal == "936", shop

    nation = parse_npc_shop_script(
        NATION_SHOP,
        source_path="scripts/zones/Port_Bastok/npcs/Numa.lua",
    )
    assert nation["status"] == "OK", nation
    assert nation["shop"].shop_kind == "NATION", nation

    dynamic = parse_npc_shop_script(
        DYNAMIC_UNSUPPORTED,
        source_path="scripts/zones/Test/npcs/Dynamic.lua",
    )
    assert dynamic["status"] == "UNSUPPORTED", dynamic
    assert dynamic["warnings"], dynamic

    guild = parse_guild_shops_data(GUILD_SHOPS)
    assert guild["status"] == "OK", guild
    by_name = {row.vendor_name: row for row in guild["shops"]}
    assert set(by_name) == {"Achika", "Alias Vendor"}, by_name

    achika = by_name["Achika"]
    assert len(achika.items) == 2, achika
    hachimaki = achika.items[0]
    assert hachimaki.item_literal == "xi.item.HACHIMAKI", hachimaki
    assert hachimaki.price == 4125, hachimaki
    assert hachimaki.metadata["initial"] == 36, hachimaki
    assert hachimaki.metadata["restockRate"] == 3, hachimaki

    numeric = achika.items[1]
    assert numeric.item_literal == "1888", numeric
    assert numeric.metadata["noSell"] is True, numeric

    alias = by_name["Alias Vendor"]
    assert alias.items == (), alias
    assert alias.metadata["shared_stock"] == "Achika", alias

    catalog = build_acquisition_catalog(
        shops=(shop, nation["shop"], *guild["shops"]),
    )
    assert catalog["counts"]["SOLD_BY"] == 6, catalog
    assert "SOLD_BY" in catalog["supported_acquisition_types"], catalog
    assert catalog["unsupported_until_profiled"] == [
        "CURIO_VENDOR",
        "SPECIAL_DYNAMIC_SHOP",
    ], catalog

    by_subject = {
        (row["subject_kind"], row["subject_id"]): row
        for row in catalog["subjects"]
    }
    symbolic = by_subject[("ITEM", "xi.item.LEATHER_BANDANA")]
    assert symbolic["paths"][0]["metadata"]["vendor_name"] == "Graine", symbolic
    assert symbolic["paths"][0]["metadata"]["item_numeric_id"] is None, symbolic

    guild_numeric = by_subject[("ITEM", "1888")]
    assert guild_numeric["paths"][0]["metadata"]["shop_kind"] == "GUILD", guild_numeric
    assert guild_numeric["paths"][0]["metadata"]["item_numeric_id"] == 1888, guild_numeric

    external = verified_external_item_ids(catalog)
    assert external == {936, 1888}, external

    print("shop Lua acquisition self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
