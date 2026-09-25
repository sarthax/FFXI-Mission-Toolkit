"""Audited logical schema profiles for major FFXI server lineages."""
from __future__ import annotations

from .base import FieldMapping, SchemaProfile, TableShape


def _common(equipment_file: str = "item_equipment.sql") -> dict[str, TableShape]:
    equipment_fields=(
        FieldMapping("item_id",("itemid","itemId"),True),
        FieldMapping("name",("name",),True),
        FieldMapping("level",("level",)),
        FieldMapping("item_level",("ilevel",)),
        FieldMapping("jobs",("jobs",)),
        FieldMapping("shield_size",("shieldSize","shieldsize")),
        FieldMapping("slot",("slot",)),
        FieldMapping("rslot",("rslot",)),
    )
    instance_fields=(
        FieldMapping("instance_id",("instanceid","instanceId"),True),
        FieldMapping("name",("instance_name","name"),True),
        FieldMapping("instance_zone",("instance_zone",)),
        FieldMapping("entrance_zone",("entrance_zone",)),
        FieldMapping("start_x",("start_x",)),
        FieldMapping("start_y",("start_y",)),
        FieldMapping("start_z",("start_z",)),
    )
    return {
        "item_basic": TableShape("item_basic", "item_basic.sql", "item_basic"),
        "item_equipment": TableShape("item_equipment", equipment_file, "item_equipment", aliases=("item_armor",),
            field_mappings=equipment_fields, identity_fields=("item_id",)),
        "item_weapon": TableShape("item_weapon", "item_weapon.sql", "item_weapon"),
        "item_usable": TableShape("item_usable", "item_usable.sql", "item_usable"),
        "npc": TableShape("npc", "npc_list.sql", "npc_list"),
        "mob_groups": TableShape("mob_groups", "mob_groups.sql", "mob_groups"),
        "mob_pools": TableShape("mob_pools", "mob_pools.sql", "mob_pools"),
        "mob_drops": TableShape("mob_drops", "mob_droplist.sql", "mob_droplist"),
        "mob_spawns": TableShape("mob_spawns", "mob_spawn_points.sql", "mob_spawn_points"),
        "instance_entities": TableShape("instance_entities", "instance_entities.sql", "instance_entities"),
        "instances": TableShape("instances", "instance_list.sql", "instance_list", field_mappings=instance_fields, identity_fields=("instance_id",)),
        "spells": TableShape("spells", "spell_list.sql", "spell_list"),
        "traits": TableShape("traits", "traits.sql", "traits"),
    }


TOPAZ = SchemaProfile(
    profile_id="topaz",
    family="TOPAZ",
    tables=_common(),
    notes=("item_equipment.sql is the equipment source; mob_groups includes a name column.",),
)

DSP = SchemaProfile(
    profile_id="dsp",
    family="DSP",
    tables={
        **_common("item_armor.sql"),
        "item_equipment": TableShape(
            "item_equipment", "item_armor.sql", "item_armor", aliases=("item_equipment",),
            field_mappings=_common("item_armor.sql")["item_equipment"].field_mappings,
            identity_fields=("item_id",),
            notes=("DSP physical filename/table name differs from Topaz/LSB.",),
        ),
        "mob_groups": TableShape(
            "mob_groups", "mob_groups.sql", "mob_groups",
            notes=("DSP lacks the direct name column; logical name is derived through mob_pools.",),
        ),
        "instances": TableShape(
            "instances", "instance_list.sql", "instance_list",
            field_mappings=_common()["instances"].field_mappings,
            identity_fields=("instance_id",),
            notes=("DSP legacy shape lacks instance_zone.",),
        ),
        "spells": TableShape(
            "spells", "spell_list.sql", "spell_list",
            notes=("DSP legacy shape lacks family.",),
        ),
        "traits": TableShape(
            "traits", "traits.sql", "traits",
            notes=("DSP legacy shape lacks meritid.",),
        ),
    },
)

LSB = SchemaProfile(
    profile_id="landsandboat",
    family="LSB",
    tables=_common(),
    notes=(
        "LSB may use SQL session variables in item/drop/skill data; adapters must resolve representation before logical mapping.",
        "Modern generated data such as status effects is separate from the SQL schema profile.",
    ),
)
