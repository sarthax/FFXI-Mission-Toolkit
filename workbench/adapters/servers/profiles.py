"""Audited logical schema profiles for major FFXI server lineages."""
from __future__ import annotations

from .base import FieldMapping, SchemaProfile, TableShape


def _common(equipment_file: str = "item_equipment.sql") -> dict[str, TableShape]:
    item_basic_fields=(
        FieldMapping("item_id",("itemid","itemId"),True),
        FieldMapping("sub_id",("subid","subId")),
        FieldMapping("name",("name",),True),
        FieldMapping("sort_name",("sortname","sortName")),
        FieldMapping("stack_size",("stackSize","stacksize")),
        FieldMapping("flags",("flags",)),
        FieldMapping("auction_house_category",("aH","ah")),
        FieldMapping("no_sale",("NoSale","nosale")),
        FieldMapping("base_sell",("BaseSell","basesell")),
    )
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
    battlefield_fields=(
        FieldMapping("battlefield_id",("bcnmId","bcnmid"),True),
        FieldMapping("zone_id",("zoneId","zoneid"),True),
        FieldMapping("name",("name",),True),
        FieldMapping("fastest_name",("fastestName","fastestname")),
        FieldMapping("fastest_party_size",("fastestPartySize","fastestpartysize")),
        FieldMapping("fastest_time",("fastestTime","fastesttime")),
        FieldMapping("time_limit",("timeLimit","timelimit")),
        FieldMapping("level_cap",("levelCap","levelcap")),
        FieldMapping("party_size",("partySize","partysize")),
        FieldMapping("loot_drop_id",("lootDropId","lootdropid")),
        FieldMapping("rules",("rules",)),
        FieldMapping("is_mission",("isMission","ismission")),
    )
    battlefield_member_fields=(
        FieldMapping("battlefield_id",("bcnmId","bcnmid"),True),
        FieldMapping("battlefield_number",("battlefieldNumber","battlefieldnumber"),True),
        FieldMapping("entity_id",("monsterId","monsterid"),True),
        FieldMapping("conditions",("conditions",)),
    )
    weapon_fields=(
        FieldMapping("item_id",("itemId","itemid"),True),
        FieldMapping("name",("name",),True),
        FieldMapping("skill",("skill",)),
        FieldMapping("subskill",("subskill",)),
        FieldMapping("item_level_skill",("ilvl_skill",)),
        FieldMapping("item_level_parry",("ilvl_parry",)),
        FieldMapping("item_level_magic_accuracy",("ilvl_macc",)),
        FieldMapping("damage_type",("dmgType","dmgtype")),
        FieldMapping("hit_count",("hit",)),
        FieldMapping("delay",("delay",)),
        FieldMapping("damage",("dmg",)),
        FieldMapping("unlock_points",("unlock_points",)),
    )
    usable_fields=(
        FieldMapping("item_id",("itemid","itemId"),True),
        FieldMapping("name",("name",),True),
        FieldMapping("valid_targets",("validTargets","validtargets")),
        FieldMapping("activation",("activation",)),
        FieldMapping("animation",("animation",)),
        FieldMapping("animation_time",("animationTime","animationtime")),
        FieldMapping("max_charges",("maxCharges","maxcharges")),
        FieldMapping("use_delay",("useDelay","usedelay")),
        FieldMapping("reuse_delay",("reuseDelay","reusedelay")),
        FieldMapping("aoe",("aoe","AOE")),
    )
    spell_fields=(
        FieldMapping("spell_id",("spellid","spellId"),True),
        FieldMapping("name",("name",),True),
        FieldMapping("jobs",("jobs",)),
        FieldMapping("group",("group",)),
        FieldMapping("family",("family",)),
        FieldMapping("element",("element",)),
        FieldMapping("zone_misc",("zonemisc",)),
        FieldMapping("valid_targets",("validTargets","validtargets")),
        FieldMapping("skill",("skill",)),
        FieldMapping("mp_cost",("mpCost","mpcost")),
        FieldMapping("cast_time",("castTime","casttime")),
        FieldMapping("recast_time",("recastTime","recasttime")),
        FieldMapping("message",("message",)),
        FieldMapping("magic_burst_message",("magicBurstMessage","magicburstmessage")),
        FieldMapping("animation",("animation",)),
        FieldMapping("animation_time",("animationTime","animationtime")),
        FieldMapping("aoe",("AOE","aoe")),
        FieldMapping("base",("base",)),
        FieldMapping("multiplier",("multiplier",)),
        FieldMapping("ce",("CE","ce")),
        FieldMapping("ve",("VE","ve")),
        FieldMapping("requirements",("requirements",)),
        FieldMapping("spell_range",("spell_range",)),
        FieldMapping("radius",("radius",)),
        FieldMapping("content_tag",("content_tag",)),
        FieldMapping("status_effect",("status_effect",)),
        FieldMapping("status_effect_tier",("status_effect_tier",)),
    )
    trait_fields=(
        FieldMapping("trait_id",("traitid","traitId"),True),
        FieldMapping("name",("name",),True),
        FieldMapping("job",("job",),True),
        FieldMapping("level",("level",),True),
        FieldMapping("rank",("rank",),True),
        FieldMapping("modifier",("modifier",),True),
        FieldMapping("value",("value",)),
        FieldMapping("content_tag",("content_tag",)),
        FieldMapping("merit_id",("meritid","meritId")),
    )
    topaz_item_basic_columns=("itemid","subid","name","sortname","stackSize","flags","aH","NoSale","BaseSell")
    lsb_item_basic_columns=("itemid","subid","name","sortname","name_jp","type","stackSize","flags","aH","BaseSell")
    npc_columns=("npcid","name","polutils_name","pos_rot","pos_x","pos_y","pos_z","flag","speed","speedsub","animation","animationsub","namevis","status","entityFlags","look","name_prefix","content_tag","widescan")
    topaz_group_columns=("groupid","poolid","zoneid","name","respawntime","spawntype","dropid","HP","MP","minLevel","maxLevel","allegiance")
    dsp_group_columns=("groupid","poolid","zoneid","respawntime","spawntype","dropid","HP","MP","minLevel","maxLevel","allegiance")
    lsb_group_columns=("groupid","poolid","zoneid","name","respawntime","spawntype","dropid","HP","MP","allegiance","content_tag")
    topaz_pool_columns=("poolid","name","packet_name","familyid","modelid","mJob","sJob","cmbSkill","cmbDelay","cmbDmgMult","behavior","aggro","true_detection","links","mobType","immunity","name_prefix","flag","entityFlags","animationsub","hasSpellScript","spellList","namevis","roamflag","skill_list_id")
    lsb_pool_columns=("poolid","name","packet_name","speciesid","modelid","mJob","sJob","cmbSkill","cmbDelay","cmbDmgMult","behavior","aggro","true_detection","links","mobType","immunity","name_prefix","flag","entityFlags","animationsub","hasSpellScript","spellList","namevis","roamflag","skill_list_id","resist_id","modelSize","modelHitboxSize")
    drop_columns=("dropId","dropType","groupId","groupRate","itemId","itemRate")
    weapon_columns=("itemId","name","skill","subskill","ilvl_skill","ilvl_parry","ilvl_macc","dmgType","hit","delay","dmg","unlock_points")
    usable_columns=("itemid","name","validTargets","activation","animation","animationTime","maxCharges","useDelay","reuseDelay","aoe")
    topaz_spell_columns=("spellid","name","jobs","group","family","element","zonemisc","validTargets","skill","mpCost","castTime","recastTime","message","magicBurstMessage","animation","animationTime","AOE","base","multiplier","CE","VE","requirements","spell_range","content_tag")
    dsp_spell_columns=("spellid","name","jobs","group","element","zonemisc","validTargets","skill","mpCost","castTime","recastTime","message","magicBurstMessage","animation","animationTime","AOE","base","multiplier","CE","VE","requirements","spell_range","content_tag")
    lsb_spell_columns=("spellid","name","jobs","group","family","element","zonemisc","validTargets","skill","mpCost","castTime","recastTime","message","magicBurstMessage","animation","animationTime","AOE","base","multiplier","CE","VE","requirements","spell_range","radius","content_tag","status_effect","status_effect_tier")
    topaz_trait_columns=("traitid","name","job","level","rank","modifier","value","content_tag","meritid")
    dsp_trait_columns=("traitid","name","job","level","rank","modifier","value","content_tag")
    topaz_spawn_columns=("mobid","mobname","polutils_name","groupid","pos_x","pos_y","pos_z","pos_rot")
    lsb_spawn_columns=("mobid","spawnslotid","mobname","polutils_name","groupid","minLevel","maxLevel","pos_x","pos_y","pos_z","pos_rot","spawnHour","despawnHour")
    instance_entity_columns=("instanceid","id")
    topaz_instance_columns=("instanceid","instance_name","instance_zone","entrance_zone","time_limit","start_x","start_y","start_z","start_rot","music_day","music_night","battlesolo","battlemulti")
    return {
        "item_basic": TableShape("item_basic", "item_basic.sql", "item_basic",
            parse_columns=topaz_item_basic_columns,
            field_mappings=item_basic_fields,
            identity_fields=("item_id",)),
        "item_equipment": TableShape("item_equipment", equipment_file, "item_equipment", aliases=("item_armor",),
            field_mappings=equipment_fields, identity_fields=("item_id",)),
        "item_weapon": TableShape("item_weapon", "item_weapon.sql", "item_weapon",
            parse_columns=weapon_columns, field_mappings=weapon_fields, identity_fields=("item_id",)),
        "item_usable": TableShape("item_usable", "item_usable.sql", "item_usable",
            parse_columns=usable_columns, field_mappings=usable_fields, identity_fields=("item_id",)),
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
        "battlefields": TableShape(
            "battlefields","bcnm_info.sql","bcnm_records",
            parse_columns=("bcnmId","zoneId","name","fastestName","fastestPartySize","fastestTime"),
            field_mappings=battlefield_fields, identity_fields=("battlefield_id",),
        ),
        "spells": TableShape("spells", "spell_list.sql", "spell_list",
            parse_columns=topaz_spell_columns, field_mappings=spell_fields, identity_fields=("spell_id",)),
        "traits": TableShape("traits", "traits.sql", "traits",
            parse_columns=topaz_trait_columns, field_mappings=trait_fields,
            identity_fields=("trait_id","job","level","rank","modifier")),
    }


TOPAZ = SchemaProfile(
    profile_id="topaz",
    family="TOPAZ",
    tables=_common(),
    notes=("item_equipment.sql is the equipment source; mob_groups includes a name column.",),
)

TOPAZ_NEXT = SchemaProfile(
    profile_id="topaz-next",
    family="TOPAZ_NEXT",
    tables=dict(TOPAZ.tables),
    notes=(
        "Topaz-Next is retained as a distinct source lineage even where the currently audited physical SQL shapes match Topaz.",
        "Fork-specific drift must be registered explicitly rather than silently inheriting Topaz identity.",
    ),
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
        "battlefields": TableShape(
            "battlefields","bcnm_info.sql","bcnm_info",
            parse_columns=("bcnmId","zoneId","name","fastestName","fastestPartySize","fastestTime","timeLimit","levelCap","partySize","lootDropId","rules","isMission"),
            field_mappings=_common()["battlefields"].field_mappings,
            identity_fields=("battlefield_id",),
            notes=("Legacy DSP stores battlefield policy fields directly in bcnm_info; modern LSB moves much of this policy into Lua content definitions.",),
        ),
        "battlefield_members": TableShape(
            "battlefield_members","bcnm_battlefield.sql","bcnm_battlefield",
            parse_columns=("bcnmId","battlefieldNumber","monsterId","conditions"),
            field_mappings=(
                FieldMapping("battlefield_id",("bcnmId","bcnmid"),True),
                FieldMapping("battlefield_number",("battlefieldNumber","battlefieldnumber"),True),
                FieldMapping("entity_id",("monsterId","monsterid"),True),
                FieldMapping("conditions",("conditions",)),
            ),
            identity_fields=("battlefield_id","battlefield_number","entity_id"),
            notes=("Legacy DSP battlefield membership is SQL-driven; modern LSB expresses groups primarily in Lua/YAML.",),
        ),
        "spells": TableShape(
            "spells", "spell_list.sql", "spell_list",
            parse_columns=("spellid","name","jobs","group","element","zonemisc","validTargets","skill","mpCost","castTime","recastTime","message","magicBurstMessage","animation","animationTime","AOE","base","multiplier","CE","VE","requirements","spell_range","content_tag"),
            field_mappings=tuple(m for m in _common()["spells"].field_mappings if m.logical_name != "family"),
            identity_fields=("spell_id",),
            notes=("DSP legacy shape lacks family.",),
        ),
        "traits": TableShape(
            "traits", "traits.sql", "traits",
            parse_columns=("traitid","name","job","level","rank","modifier","value","content_tag"),
            field_mappings=tuple(m for m in _common()["traits"].field_mappings if m.logical_name != "merit_id"),
            identity_fields=("trait_id","job","level","rank","modifier"),
            notes=("DSP legacy shape lacks meritid.",),
        ),
    },
)

LSB = SchemaProfile(
    profile_id="landsandboat",
    family="LSB",
    tables={
        **_common(),
        "item_basic": TableShape(
            "item_basic","item_basic.sql","item_basic",
            parse_columns=("itemid","subid","name","sortname","name_jp","type","stackSize","flags","aH","BaseSell"),
            field_mappings=tuple(
                m for m in _common()["item_basic"].field_mappings
                if m.logical_name != "no_sale"
            ) + (
                FieldMapping("name_jp",("name_jp",)),
                FieldMapping("item_type",("type",)),
            ),
            identity_fields=("item_id",),
            notes=(
                "LSB item_basic replaces legacy NoSale with explicit item type and adds Japanese name text.",
                "LSB flags uses a wider physical integer type; logical flags semantics remain shared.",
            ),
        ),
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
        "spells": TableShape(
            "spells","spell_list.sql","spell_list",
            parse_columns=("spellid","name","jobs","group","family","element","zonemisc","validTargets","skill","mpCost","castTime","recastTime","message","magicBurstMessage","animation","animationTime","AOE","base","multiplier","CE","VE","requirements","spell_range","radius","content_tag","status_effect","status_effect_tier"),
            field_mappings=_common()["spells"].field_mappings,
            identity_fields=("spell_id",),
            notes=("LSB adds radius/status-effect fields beyond the audited Topaz-era spell shape.",),
        ),
        "traits": TableShape(
            "traits","traits.sql","traits",
            parse_columns=("traitid","name","job","level","rank","modifier","value","content_tag","meritid"),
            field_mappings=_common()["traits"].field_mappings,
            identity_fields=("trait_id","job","level","rank","modifier"),
        ),
        "battlefields": TableShape(
            "battlefields","bcnm_info.sql","bcnm_records",
            parse_columns=("bcnmId","zoneId","name","fastestName","fastestPartySize","fastestTime"),
            field_mappings=_common()["battlefields"].field_mappings,
            identity_fields=("battlefield_id",),
            notes=("Modern LSB bcnm_records keeps registry identity/history; battlefield policy is implemented in Lua content definitions.",),
        ),
    },
    notes=(
        "LSB may use SQL session variables in item/drop/skill data; adapters must resolve representation before logical mapping.",
        "Modern generated data such as status effects is separate from the SQL schema profile.",
    ),
)
