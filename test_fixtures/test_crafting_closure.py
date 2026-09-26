#!/usr/bin/env python3
from __future__ import annotations

from workbench.adapters.servers.base import LogicalRecord
from workbench.migrations.crafting_closure import build_crafting_closure


def rec(logical_type, recipe_id, fields):
    return LogicalRecord(
        logical_type=logical_type,
        identity=(("recipe_id", recipe_id),),
        fields={"recipe_id": recipe_id, **fields},
        source_family="LSB",
        source_table=logical_type,
    )


def main():
    heat=rec("synth_recipes",62525,{
        "key_item_id":2037,
        "alchemy":55,
        "crystal_item_id":4096,
        "ingredient_1":939,
        "ingredient_2":1645,
        "ingredient_3":1887,
        "ingredient_4":2309,
        "ingredient_5":2310,
        "result_item_id":2256,
        "result_qty":12,
        "result_name":"Heat Seeker",
    })
    glass=rec("synth_recipes",62531,{
        "alchemy":56,
        "crystal_item_id":4096,
        "ingredient_1":936,
        "ingredient_2":1883,
        "ingredient_3":1888,
        "ingredient_4":1888,
        "ingredient_5":1888,
        "ingredient_6":1888,
        "ingredient_7":1888,
        "ingredient_8":1888,
        "result_item_id":1887,
        "result_qty":1,
        "result_name":"Glass Sheet",
    })
    synergy=rec("synergy_recipes",99,{
        "primary_skill":0,
        "primary_rank":4,
        "ingredient_1":1887,
        "result_item_id":9999,
        "result_name":"Synergy Test",
    })
    records=[heat,glass,synergy]

    # Top-level recipe exists, but the path is still unresolved because its
    # prerequisite leaves have not been proven obtainable.
    unresolved=build_crafting_closure(
        records,
        2256,
        known_key_items={2037},
        known_obtainable_items={4096,939,1645,2309,2310},
    )
    assert unresolved["status"]=="UNRESOLVED",unresolved
    heat_path=unresolved["root"]["paths"][0]
    glass_node=next(x for x in heat_path["ingredients"] if x["item_id"]==1887)
    assert glass_node["status"]=="UNRESOLVED",glass_node
    assert any(x in glass_node["unresolved"] for x in (
        "ingredient 936 unresolved",
        "ingredient 1883 unresolved",
        "ingredient 1888 unresolved",
    )),glass_node

    # Once every Glass Sheet leaf is independently obtainable, the entire
    # selected crafting chain closes.
    viable=build_crafting_closure(
        records,
        2256,
        known_key_items={2037},
        known_obtainable_items={4096,939,1645,2309,2310,936,1883,1888},
    )
    assert viable["status"]=="OBTAINABLE",viable
    assert viable["root"]["satisfied_by"]=="CRAFTING",viable

    # Missing Iatrochemistry blocks the top-level path.
    no_ki=build_crafting_closure(
        records,
        2256,
        known_obtainable_items={4096,939,1645,2309,2310,936,1883,1888},
    )
    assert no_ki["status"]=="UNRESOLVED",no_ki
    assert "missing required key item 2037" in no_ki["root"]["paths"][0]["reasons"],no_ki

    # Synergy remains unavailable unless both server/runtime and client
    # capability are explicitly present.
    no_synergy=build_crafting_closure(
        records,
        9999,
        known_obtainable_items={1887},
        available_systems={"SYNTHESIS_RUNTIME"},
    )
    assert no_synergy["status"]=="UNRESOLVED",no_synergy
    assert set(no_synergy["root"]["paths"][0]["missing_systems"])=={
        "SYNERGY_RUNTIME","SYNERGY_CLIENT_CAPABILITY"
    },no_synergy

    with_synergy=build_crafting_closure(
        records,
        9999,
        known_obtainable_items={1887},
        available_systems={"SYNTHESIS_RUNTIME","SYNERGY_RUNTIME","SYNERGY_CLIENT_CAPABILITY"},
    )
    assert with_synergy["status"]=="OBTAINABLE",with_synergy

    print("crafting closure self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
