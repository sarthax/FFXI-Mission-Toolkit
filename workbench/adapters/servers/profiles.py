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
    npc_fields=(
        FieldMapping("npc_id",("npcid",),True),
        FieldMapping("name",("name",),True),
        FieldMapping("pos_x",("pos_x",)),
        FieldMapping("pos_y",("pos_y",)),
        FieldMapping("pos_z",("pos_z",)),
        FieldMapping("pos_rot",("pos_rot",)),
        FieldMapping("entity_flags",("entityFlags","entityflags")),
        FieldMapping("widescan",("widescan",)),
    )
    mob_group_fields=(
        FieldMapping("group_id",("groupid","groupId"),True),
        FieldMapping("pool_id",("poolid","poolId"),True),
        FieldMapping("zone_id",("zoneid","zoneId"),True),
        FieldMapping("name",("name",)),
        FieldMapping("respawn_time",("respawntime","respawnTime")),
        FieldMapping("spawn_type",("spawntype","spawnType")),
        FieldMapping("drop_id",("dropid","dropId")),
        FieldMapping("min_level",("minLevel","minlevel")),
        FieldMapping("max_level",("maxLevel","maxlevel")),
    )
    mob_pool_fields=(
        FieldMapping("pool_id",("poolid","poolId"),True),
        FieldMapping("name",("name",),True),
        FieldMapping("model_id",("modelid","modelId")),
        FieldMapping("main_job",("mJob","mjob")),
        FieldMapping("sub_job",("sJob","sjob")),
        FieldMapping("entity_flags",("entityFlags","entityflags")),
        FieldMapping("name_visibility",("namevis",)),
        FieldMapping("roam_flags",("roamflag",)),
    )
    drop_fields=(
        FieldMapping("drop_id",("dropId","dropid"),True),
        FieldMapping("drop_type",("dropType","droptype"),True),
        FieldMapping("group_id",("groupId","groupid"),True),
        FieldMapping("group_rate",("groupRate","grouprate")),
        FieldMapping("item_id",("itemId","itemid"),True),
        FieldMapping("item_rate",("itemRate","itemrate")),
    )
    spawn_fields=(
        FieldMapping("mob_id",("mobid",),True),
        FieldMapping("spawn_slot_id",("spawnslotid","spawnSlotId")),
        FieldMapping("name",("mobname","name"),True),
        FieldMapping("group_id",("groupid","groupId"),True),
        FieldMapping("min_level",("minLevel","minlevel")),
        FieldMapping("max_level",("maxLevel","maxlevel")),
        FieldMapping("pos_x",("pos_x",)),
        FieldMapping("pos_y",("pos_y",)),
        FieldMapping("pos_z",("pos_z",)),
        FieldMapping("pos_rot",("pos_rot",)),
    )
    instance_entity_fields=(
        FieldMapping("instance_id",("instanceid","instanceId"),True),
        FieldMapping("entity_id",("id","entity_id"),True),
    )
    npc_columns=("npcid","name","polutils_name","pos_rot","pos_x","pos_y","pos_z","flag","speed","speedsub","animation","animationsub","namevis","status","entityFlags","look","name_prefix","content_tag","widescan")
    topaz_group_columns=("groupid","poolid","zoneid","name","respawntime","spawntype","dropid","HP","MP","minLevel","maxLevel","allegiance")
    dsp_group_columns=("groupid","poolid","zoneid","respawntime","spawntype","dropid","HP","MP","minLevel","maxLevel","allegiance")
    lsb_group_columns=("groupid","poolid","zoneid","name","respawntime","spawntype","dropid","HP","MP","allegiance","content_tag")
    topaz_pool_columns=("poolid","name","packet_name","familyid","modelid","mJob","sJob","cmbSkill","cmbDelay","cmbDmgMult","behavior","aggro","true_detection","links","mobType","immunity","name_prefix","flag","entityFlags","animationsub","hasSpellScript","spellList","namevis","roamflag","skill_list_id")
    lsb_pool_columns=("poolid","name","packet_name","speciesid","modelid","mJob","sJob","cmbSkill","cmbDelay","cmbDmgMult","behavior","aggro","true_detection","links","mobType","immunity","name_prefix","flag","entityFlags","animationsub","hasSpellScript","spellList","namevis","roamflag","skill_list_id","resist_id","modelSize","modelHitboxSize")
    drop_columns=("dropId","dropType","groupId","groupRate","itemId","itemRate")
    topaz_spawn_columns=("mobid","mobname","polutils_name","groupid","pos_x","pos_y","pos_z","pos_rot")
    lsb_spawn_columns=("mobid","spawnslotid","mobname","polutils_name","groupid","minLevel","maxLevel","pos_x","pos_y","pos_z","pos_rot","spawnHour","despawnHour")
    instance_entity_columns=("instanceid","id")
    topaz_instance_columns=("instanceid","instance_name","instance_zone","entrance_zone","time_limit","start_x","start_y","start_z","start_rot","music_day","music_night","battlesolo","battlemulti")
    return {
        "item_basic": TableShape("item_basic", "item_basic.sql", "item_basic"),
        "item_equipment": TableShape("item_equipment", equipment_file, "item_equipment", aliases=("item_armor",),
            field_mappings=equipment_fields, identity_fields=("item_id",)),
        "item_weapon": TableShape("item_weapon", "item_weapon.sql", "item_weapon"),
        "item_usable": TableShape("item_usable", "item_usable.sql", "item_usable"),
        "npc": TableShape("npc", "npc_list.sql", "npc_list",
            parse_columns=npc_columns, field_mappings=npc_fields, identity_fields=("npc_id",)),
        "mob_groups": TableShape("mob_groups", "mob_groups.sql", "mob_groups",
            parse_columns=topaz_group_columns, field_mappings=mob_group_fields, identity_fields=("zone_id","group_id")),
        "mob_pools": TableShape("mob_pools", "mob_pools.sql", "mob_pools",
            parse_columns=topaz_pool_columns,
            field_mappings=mob_pool_fields + (FieldMapping("family_id",("familyid","familyId")),),
            identity_fields=("pool_id",)),
        "mob_drops": TableShape("mob_drops", "mob_droplist.sql", "mob_droplist",
            parse_columns=drop_columns, field_mappings=drop_fields, identity_fields=("drop_id","drop_type","group_id","item_id")),
        "mob_spawns": TableShape("mob_spawns", "mob_spawn_points.sql", "mob_spawn_points",
            parse_columns=topaz_spawn_columns, field_mappings=spawn_fields, identity_fields=("mob_id",)),
        "instance_entities": TableShape("instance_entities", "instance_entities.sql", "instance_entities",
            parse_columns=instance_entity_columns, field_mappings=instance_entity_fields, identity_fields=("instance_id","entity_id")),
        "instances": TableShape("instances", "instance_list.sql", "instance_list",
            parse_columns=topaz_instance_columns, field_mappings=instance_fields, identity_fields=("instance_id",)),
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
            parse_columns=("groupid","poolid","zoneid","respawntime","spawntype","dropid","HP","MP","minLevel","maxLevel","allegiance"),
            field_mappings=_common()["mob_groups"].field_mappings,
            identity_fields=("zone_id","group_id"),
            notes=("DSP lacks the direct name column; logical name requires a mob_pools join rather than direct row normalization.",),
        ),
        "instances": TableShape(
            "instances", "instance_list.sql", "instance_list",
            parse_columns=("instanceid","instance_name","entrance_zone","time_limit","start_x","start_y","start_z","start_rot","music_day","music_night","battlesolo","battlemulti"),
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
    tables={
        **_common(),
        "mob_pools": TableShape(
            "mob_pools", "mob_pools.sql", "mob_pools",
            parse_columns=("poolid","name","packet_name","speciesid","modelid","mJob","sJob","cmbSkill","cmbDelay","cmbDmgMult","behavior","aggro","true_detection","links","mobType","immunity","name_prefix","flag","entityFlags","animationsub","hasSpellScript","spellList","namevis","roamflag","skill_list_id","resist_id","modelSize","modelHitboxSize"),
            field_mappings=tuple(m for m in _common()["mob_pools"].field_mappings if m.logical_name != "family_id")
                + (FieldMapping("species_id",("speciesid","speciesId")),),
            identity_fields=("pool_id",),
            notes=("LSB uses speciesid where older Topaz/DSP schemas expose familyid; these are retained as distinct logical fields.",),
        ),
        "mob_groups": TableShape(
            "mob_groups","mob_groups.sql","mob_groups",
            parse_columns=("groupid","poolid","zoneid","name","respawntime","spawntype","dropid","HP","MP","allegiance","content_tag"),
            field_mappings=_common()["mob_groups"].field_mappings,
            identity_fields=("zone_id","group_id"),
        ),
        "mob_spawns": TableShape(
            "mob_spawns","mob_spawn_points.sql","mob_spawn_points",
            parse_columns=("mobid","spawnslotid","mobname","polutils_name","groupid","minLevel","maxLevel","pos_x","pos_y","pos_z","pos_rot","spawnHour","despawnHour"),
            field_mappings=_common()["mob_spawns"].field_mappings,
            identity_fields=("mob_id",),
        ),
        "instances": TableShape(
            "instances","instance_list.sql","instance_list",
            parse_columns=("instanceid","instance_name","instance_zone","entrance_zone","overlay_id","time_limit","start_x","start_y","start_z","start_rot","music_day","music_night","battlesolo","battlemulti"),
            field_mappings=_common()["instances"].field_mappings,
            identity_fields=("instance_id",),
        ),
    },
    notes=(
        "LSB may use SQL session variables in item/drop/skill data; adapters must resolve representation before logical mapping.",
        "Modern generated data such as status effects is separate from the SQL schema profile.",
    ),
)
