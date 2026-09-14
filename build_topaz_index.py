#!/usr/bin/env python3
"""
build_topaz_index.py -- indexes Topaz's own sql/ checkout as its OWN data layer inside the
backport module, structurally parallel to build_dsp_index.py (old-DSP) and build_lsb_index.py
(LandSandBoat).

Why this exists: CORE_AGNOSTIC_DESIGN.md phase 1 repointed build_sql_index.py's sql_* tables at
the bundled LandSandBoat/ checkout instead of Topaz -- LSB is now the core module's primary data
source (what gui_server.py's pages query by default). That means Topaz's own SQL data -- which
used to be build_sql_index.py's whole reason for existing -- no longer has a loader of its own.
This file is that loader, moved into the backport module alongside build_dsp_index.py, gated the
same optional way: if topaz_server_path isn't a real checkout, every load_*() here degrades to
"0 rows" instead of erroring.

Schema, confirmed directly against a real checkout (C:/topaz/sql/*.sql CREATE TABLE + first
INSERT row of each file, read this session -- NOT ported blindly from build_sql_index.py's
current load_*() functions, which as of phase 1 parse LSB's schema, not Topaz's real one):

  - item_basic.sql: 9 raw columns (itemid, subid, name, sortname, stackSize, flags, aH, NoSale,
    BaseSell), plain integers -- no name_jp/type columns and no `SET @VAR` indirection (that's an
    LSB-only quirk; Topaz's own dump never uses it, confirmed against every table read this
    session).
  - item_equipment.sql: real table name (not item_armor.sql, that's DSP's rename), 10 columns
    (itemId, name, level, ilevel, jobs, MId, shieldSize, scriptType, slot, rslot).
  - mob_groups.sql: 12 columns, HAS a `name` column directly (confirmed via CREATE TABLE) -- no
    need to derive a display name via mob_pools join the way build_dsp_index.py's load_mob_groups()
    has to (DSP's mob_groups.sql genuinely lacks `name`; Topaz's doesn't).
  - instance_list.sql: 13 columns, HAS `instance_zone` (DSP's dump lacks it, LSB's has it too).
  - spell_list.sql: 24 columns, HAS `family` (DSP's dump lacks it) -- not carried into the stored
    table here either way, same as build_dsp_index.py/build_lsb_index.py (their own comparison
    columns never use it), so this only affects column-list alignment during parsing, not stored
    data.
  - traits.sql: 9 columns, HAS `meritid` (DSP's dump lacks it) -- also not stored, same reasoning
    as `family` above.
  - mob_droplist.sql / item_basic.sql: real INSERT rows here are plain integers throughout (e.g.
    `(1,0,0,1000,18856,240)` for mob_droplist) -- no `@VAR`-style SQL anywhere, so (unlike LSB) no
    resolve_sql_vars()/_resolve_field() call is needed for any table.
  - Every other table read this session (item_weapon, item_usable, npc_list, mob_pools,
    mob_spawn_points, instance_entities, mob_skills, abilities, weapon_skills, blue_spell_list,
    pet_list) matches the column shape build_dsp_index.py already uses for DSP's equivalent
    (DSP's dumps are themselves close derivatives of Topaz's own, per that file's own docstring),
    so those load_*() functions here are structurally identical to build_dsp_index.py's.

Effects (topaz_effects) and npc_event_refs (source='topaz') are already populated by
build_lsb_index.py's load_effects()/load_npc_event_refs() (it reads TOPAZ_STATUS_EFFECT_H /
TOPAZ_SCRIPTS_DIR directly as the "other side" of its own LSB-vs-Topaz diff) -- deliberately NOT
duplicated here; that's phase 3's concern (flipping the diff direction / moving it into this
module), not this file's.

Topaz's checkout root comes from Settings' topaz_server_path (settings.get_topaz_root()), same
"user tells us where it is" model DSP/LSB use -- except Topaz's setting already existed pre-phase-1
and has a real default (C:/topaz) rather than defaulting to None. If that path (or its sql/
subdirectory) doesn't exist, every function here degrades to "0 rows" rather than erroring, same
as build_dsp_index.py does when dsp_server_path is unset.

Usage:
    py -3 build_topaz_index.py               # parse and (re)load every topaz_* table
"""
import re
import sqlite3
from pathlib import Path

import build_database
import build_sql_index as sqlidx
import settings

TOOLS_ROOT = Path(__file__).parent
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
TOPAZ_ROOT = settings.get_topaz_root()
TOPAZ_SQL_DIR = (TOPAZ_ROOT / "sql") if (TOPAZ_ROOT and (TOPAZ_ROOT / "sql").is_dir()) else None

normalize = build_database.normalize
parse_table_file = sqlidx.parse_table_file
unquote = sqlidx.unquote
cleaned_path = sqlidx.cleaned_path


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS topaz_item_basic (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT,
            stackSize INTEGER, flags INTEGER, aH INTEGER, BaseSell INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_item_equipment (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, level INTEGER, ilevel INTEGER,
            jobs INTEGER, shieldSize INTEGER, slot INTEGER, rslot INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_item_weapon (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, skill INTEGER, subskill INTEGER,
            dmgType INTEGER, delay INTEGER, dmg INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_item_usable (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, validTargets INTEGER,
            activation REAL, animation INTEGER, maxCharges INTEGER, useDelay INTEGER,
            reuseDelay INTEGER, aoe INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_npc_list (
            npcid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, zoneid INTEGER,
            pos_x REAL, pos_y REAL, pos_z REAL, pos_rot REAL, entityFlags INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_mob_groups (
            zoneid INTEGER, groupid INTEGER, poolid INTEGER, name TEXT, norm_name TEXT,
            respawntime INTEGER, minLevel INTEGER, maxLevel INTEGER, dropid INTEGER,
            PRIMARY KEY (zoneid, groupid)
        );
        CREATE TABLE IF NOT EXISTS topaz_mob_pools (
            poolid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, familyid INTEGER, modelid TEXT
        );
        CREATE TABLE IF NOT EXISTS topaz_mob_droplist (
            dropid INTEGER, dropType INTEGER, groupId INTEGER, groupRate INTEGER,
            itemId INTEGER, itemRate INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_mob_spawn_points (
            mobid INTEGER PRIMARY KEY, mobname TEXT, norm_name TEXT, groupid INTEGER,
            pos_x REAL, pos_y REAL, pos_z REAL, pos_rot REAL
        );
        CREATE TABLE IF NOT EXISTS topaz_instance_entities (
            instanceid INTEGER, id INTEGER, PRIMARY KEY (instanceid, id)
        );
        CREATE TABLE IF NOT EXISTS topaz_instance_list (
            instanceid INTEGER PRIMARY KEY, instance_name TEXT, instance_zone INTEGER,
            entrance_zone INTEGER, start_x REAL, start_y REAL, start_z REAL
        );
        CREATE TABLE IF NOT EXISTS topaz_mob_skills (
            mob_skill_id INTEGER PRIMARY KEY, mob_anim_id INTEGER, name TEXT, norm_name TEXT,
            aoe INTEGER, distance REAL, anim_time INTEGER, prepare_time INTEGER,
            valid_targets INTEGER, skill_flag INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_spell_list (
            spellid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, element INTEGER, skill INTEGER,
            mpCost INTEGER, castTime INTEGER, recastTime INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_abilities (
            abilityId INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, job INTEGER, level INTEGER,
            recastTime INTEGER, recastId INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_weapon_skills (
            weaponskillid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, skilllevel INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_traits (
            traitid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT
        );
        CREATE TABLE IF NOT EXISTS topaz_blue_spell_list (
            spellid INTEGER PRIMARY KEY, mob_skill_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_pet_list (
            petid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, poolid INTEGER
        );
        CREATE TABLE IF NOT EXISTS topaz_keyitems (
            id INTEGER PRIMARY KEY, const_name TEXT, norm_name TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_topaz_mob_groups_poolid ON topaz_mob_groups(poolid);
        CREATE INDEX IF NOT EXISTS idx_topaz_mob_spawn_groupid ON topaz_mob_spawn_points(groupid);
    """)
    con.commit()


def _zoneid_from_npcid(npcid: int) -> int:
    return (npcid >> 12) & 0xFFF


def _empty(reason: str) -> int:
    print(f"  skipped -- {reason}")
    return 0


def load_item_basic(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["itemid", "subid", "name", "sortname", "stackSize", "flags", "aH", "NoSale", "BaseSell"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "item_basic.sql"), "item_basic", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemid"])), name, normalize(name),
                      int(unquote(r["stackSize"])), int(unquote(r["flags"])), int(unquote(r["aH"])), int(unquote(r["BaseSell"]))))
    con.execute("DELETE FROM topaz_item_basic")
    con.executemany("INSERT OR REPLACE INTO topaz_item_basic VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_equipment(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["itemId", "name", "level", "ilevel", "jobs", "MId", "shieldSize", "scriptType", "slot", "rslot"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "item_equipment.sql"), "item_equipment", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemId"])), name, normalize(name), int(unquote(r["level"])), int(unquote(r["ilevel"])),
                      int(unquote(r["jobs"])), int(unquote(r["shieldSize"])), int(unquote(r["slot"])), int(unquote(r["rslot"]))))
    con.execute("DELETE FROM topaz_item_equipment")
    con.executemany("INSERT OR REPLACE INTO topaz_item_equipment VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_weapon(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["itemId", "name", "skill", "subskill", "ilvl_skill", "ilvl_parry", "ilvl_macc",
            "dmgType", "hit", "delay", "dmg", "unlock_points"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "item_weapon.sql"), "item_weapon", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemId"])), name, normalize(name), int(unquote(r["skill"])), int(unquote(r["subskill"])),
                      int(unquote(r["dmgType"])), int(unquote(r["delay"])), int(unquote(r["dmg"]))))
    con.execute("DELETE FROM topaz_item_weapon")
    con.executemany("INSERT OR REPLACE INTO topaz_item_weapon VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_usable(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["itemid", "name", "validTargets", "activation", "animation", "animationTime",
            "maxCharges", "useDelay", "reuseDelay", "aoe"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "item_usable.sql"), "item_usable", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemid"])), name, normalize(name), int(unquote(r["validTargets"])), float(unquote(r["activation"])),
                      int(unquote(r["animation"])), int(unquote(r["maxCharges"])), int(unquote(r["useDelay"])), int(unquote(r["reuseDelay"])),
                      int(unquote(r["aoe"]))))
    con.execute("DELETE FROM topaz_item_usable")
    con.executemany("INSERT OR REPLACE INTO topaz_item_usable VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_npc_list(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["npcid", "name", "polutils_name", "pos_rot", "pos_x", "pos_y", "pos_z", "flag",
            "speed", "speedsub", "animation", "animationsub", "namevis", "status",
            "entityFlags", "look", "name_prefix", "content_tag", "widescan"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "npc_list.sql"), "npc_list", cols):
        npcid = int(unquote(r["npcid"]))
        name = unquote(r["name"])
        rows.append((npcid, name, normalize(name), _zoneid_from_npcid(npcid),
                      float(unquote(r["pos_x"])), float(unquote(r["pos_y"])), float(unquote(r["pos_z"])), float(unquote(r["pos_rot"])),
                      int(unquote(r["entityFlags"]))))
    con.execute("DELETE FROM topaz_npc_list")
    con.executemany("INSERT OR REPLACE INTO topaz_npc_list VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_pools(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["poolid", "name", "packet_name", "familyid", "modelid", "mJob", "sJob", "cmbSkill",
            "cmbDelay", "cmbDmgMult", "behavior", "aggro", "true_detection", "links", "mobType",
            "immunity", "name_prefix", "flag", "entityFlags", "animationsub", "hasSpellScript",
            "spellList", "namevis", "roamflag", "skill_list_id"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "mob_pools.sql"), "mob_pools", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["poolid"])), name, normalize(name), int(unquote(r["familyid"])), r["modelid"]))
    con.execute("DELETE FROM topaz_mob_pools")
    con.executemany("INSERT OR REPLACE INTO topaz_mob_pools VALUES (?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_groups(con: sqlite3.Connection) -> int:
    # Real finding: Topaz's mob_groups.sql (unlike DSP's) HAS a `name` column directly (12 cols,
    # confirmed via CREATE TABLE), so no mob_pools join/derivation is needed here the way
    # build_dsp_index.py's load_mob_groups() has to do for DSP's 11-col dump.
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["groupid", "poolid", "zoneid", "name", "respawntime", "spawntype", "dropid",
            "HP", "MP", "minLevel", "maxLevel", "allegiance"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "mob_groups.sql"), "mob_groups", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["zoneid"])), int(unquote(r["groupid"])), int(unquote(r["poolid"])), name, normalize(name),
                      int(unquote(r["respawntime"])), int(unquote(r["minLevel"])), int(unquote(r["maxLevel"])), int(unquote(r["dropid"]))))
    con.execute("DELETE FROM topaz_mob_groups")
    con.executemany("INSERT OR REPLACE INTO topaz_mob_groups VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_droplist(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["dropId", "dropType", "groupId", "groupRate", "itemId", "itemRate"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "mob_droplist.sql"), "mob_droplist", cols):
        rows.append((int(unquote(r["dropId"])), int(unquote(r["dropType"])), int(unquote(r["groupId"])), int(unquote(r["groupRate"])),
                      int(unquote(r["itemId"])), int(unquote(r["itemRate"]))))
    con.execute("DELETE FROM topaz_mob_droplist")
    con.executemany("INSERT INTO topaz_mob_droplist VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_spawn_points(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["mobid", "mobname", "polutils_name", "groupid", "pos_x", "pos_y", "pos_z", "pos_rot"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "mob_spawn_points.sql"), "mob_spawn_points", cols):
        name = unquote(r["mobname"])
        rows.append((int(unquote(r["mobid"])), name, normalize(name), int(unquote(r["groupid"])),
                      float(unquote(r["pos_x"])), float(unquote(r["pos_y"])), float(unquote(r["pos_z"])), float(unquote(r["pos_rot"]))))
    con.execute("DELETE FROM topaz_mob_spawn_points")
    con.executemany("INSERT OR REPLACE INTO topaz_mob_spawn_points VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_entities(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["instanceid", "id"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "instance_entities.sql"), "instance_entities", cols):
        rows.append((int(unquote(r["instanceid"])), int(unquote(r["id"]))))
    con.execute("DELETE FROM topaz_instance_entities")
    con.executemany("INSERT OR REPLACE INTO topaz_instance_entities VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_list(con: sqlite3.Connection) -> int:
    # Real finding: Topaz's instance_list.sql (unlike DSP's) HAS `instance_zone` (13 cols,
    # confirmed via CREATE TABLE) -- kept in the stored table here (matching lsb_instance_list's
    # shape) since Topaz genuinely carries it, unlike DSP.
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["instanceid", "instance_name", "instance_zone", "entrance_zone", "time_limit",
            "start_x", "start_y", "start_z", "start_rot", "music_day", "music_night",
            "battlesolo", "battlemulti"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "instance_list.sql"), "instance_list", cols):
        rows.append((int(unquote(r["instanceid"])), unquote(r["instance_name"]), int(unquote(r["instance_zone"])),
                      int(unquote(r["entrance_zone"])), float(unquote(r["start_x"])), float(unquote(r["start_y"])),
                      float(unquote(r["start_z"]))))
    con.execute("DELETE FROM topaz_instance_list")
    con.executemany("INSERT OR REPLACE INTO topaz_instance_list VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_skills(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["mob_skill_id", "mob_anim_id", "mob_skill_name", "mob_skill_aoe", "mob_skill_distance",
            "mob_anim_time", "mob_prepare_time", "mob_valid_targets", "mob_skill_flag",
            "mob_skill_param", "knockback", "primary_sc", "secondary_sc", "tertiary_sc"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "mob_skills.sql"), "mob_skills", cols):
        name = unquote(r["mob_skill_name"])
        rows.append((
            int(unquote(r["mob_skill_id"])), int(unquote(r["mob_anim_id"])), name, normalize(name),
            int(unquote(r["mob_skill_aoe"])), float(unquote(r["mob_skill_distance"])), int(unquote(r["mob_anim_time"])),
            int(unquote(r["mob_prepare_time"])), int(unquote(r["mob_valid_targets"])), int(unquote(r["mob_skill_flag"])),
        ))
    con.execute("DELETE FROM topaz_mob_skills")
    con.executemany("INSERT OR REPLACE INTO topaz_mob_skills VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_spell_list(con: sqlite3.Connection) -> int:
    # Real finding: Topaz's spell_list.sql (unlike DSP's) HAS `family` (24 cols, confirmed via
    # CREATE TABLE) -- not carried into the stored table, same as build_dsp_index.py/
    # build_lsb_index.py (neither's own comparison columns use it either), so this only affects
    # column-list alignment for parsing, not any data kept.
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["spellid", "name", "jobs", "group", "family", "element", "zonemisc", "validTargets",
            "skill", "mpCost", "castTime", "recastTime", "message", "magicBurstMessage",
            "animation", "animationTime", "AOE", "base", "multiplier", "CE", "VE",
            "requirements", "spell_range", "content_tag"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "spell_list.sql"), "spell_list", cols):
        name = unquote(r["name"])
        rows.append((
            int(unquote(r["spellid"])), name, normalize(name), int(unquote(r["element"])), int(unquote(r["skill"])),
            int(unquote(r["mpCost"])), int(unquote(r["castTime"])), int(unquote(r["recastTime"])),
        ))
    con.execute("DELETE FROM topaz_spell_list")
    con.executemany("INSERT OR REPLACE INTO topaz_spell_list VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_abilities(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["abilityId", "name", "job", "level", "validTarget", "recastTime", "recastId",
            "message1", "message2", "animation", "animationTime", "castTime", "actionType",
            "range", "isAOE", "CE", "VE", "meritModID", "addType", "content_tag"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "abilities.sql"), "abilities", cols):
        name = unquote(r["name"])
        rows.append((
            int(unquote(r["abilityId"])), name, normalize(name), int(unquote(r["job"])), int(unquote(r["level"])),
            int(unquote(r["recastTime"])), int(unquote(r["recastId"])), int(unquote(r["animation"])),
        ))
    con.execute("DELETE FROM topaz_abilities")
    con.executemany("INSERT OR REPLACE INTO topaz_abilities VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_weapon_skills(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["weaponskillid", "name", "jobs", "type", "skilllevel", "element", "animation",
            "animationTime", "range", "aoe", "primary_sc", "secondary_sc",
            "tertiary_sc", "main_only", "unlock_id"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "weapon_skills.sql"), "weapon_skills", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["weaponskillid"])), name, normalize(name), int(unquote(r["skilllevel"])), int(unquote(r["animation"]))))
    con.execute("DELETE FROM topaz_weapon_skills")
    con.executemany("INSERT OR REPLACE INTO topaz_weapon_skills VALUES (?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_traits(con: sqlite3.Connection) -> int:
    # Real finding: Topaz's traits.sql (unlike DSP's) HAS `meritid` (9 cols, confirmed via CREATE
    # TABLE) -- not carried into the stored table, same reasoning as `family` above.
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["traitid", "name", "job", "level", "rank", "modifier", "value", "content_tag", "meritid"]
    seen = {}
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "traits.sql"), "traits", cols):
        name = unquote(r["name"])
        seen[int(unquote(r["traitid"]))] = (name, normalize(name))
    con.execute("DELETE FROM topaz_traits")
    con.executemany("INSERT OR REPLACE INTO topaz_traits VALUES (?,?,?)",
                     [(tid, name, norm) for tid, (name, norm) in seen.items()])
    con.commit()
    return len(seen)


def load_blue_spell_list(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["spellid", "mob_skill_id", "set_points", "trait_category", "trait_category_weight",
            "primary_sc", "secondary_sc"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "blue_spell_list.sql"), "blue_spell_list", cols):
        rows.append((int(unquote(r["spellid"])), int(unquote(r["mob_skill_id"]))))
    con.execute("DELETE FROM topaz_blue_spell_list")
    con.executemany("INSERT OR REPLACE INTO topaz_blue_spell_list VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_pet_list(con: sqlite3.Connection) -> int:
    if not TOPAZ_SQL_DIR:
        return _empty("topaz_server_path not configured / no sql/ checkout found")
    cols = ["petid", "name", "poolid", "minLevel", "maxLevel", "time", "element"]
    rows = []
    for r in parse_table_file(cleaned_path(TOPAZ_SQL_DIR / "pet_list.sql"), "pet_list", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["petid"])), name, normalize(name), int(unquote(r["poolid"]))))
    con.execute("DELETE FROM topaz_pet_list")
    con.executemany("INSERT OR REPLACE INTO topaz_pet_list VALUES (?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_keyitems(con: sqlite3.Connection) -> int:
    """Topaz's own scripts/globals/keyitems.lua tpz.keyItem table -- the backport-module
    counterpart to build_database.py's load_keyitems_ours() (which now reads LSB's
    scripts/enum/key_item.lua instead, per CORE_AGNOSTIC_DESIGN.md's LSB-primary rework). Same
    regex that function used to use against Topaz, unchanged -- this is the file it used to read.
    Root comes from TOPAZ_ROOT directly (not TOPAZ_SQL_DIR -- keyitems.lua lives under
    scripts/globals/, not sql/), same optional-degrades-to-0-rows pattern as every other loader
    here."""
    path = TOPAZ_ROOT / "scripts/globals/keyitems.lua" if TOPAZ_ROOT else None
    if not path or not path.exists():
        return _empty("topaz_server_path not configured / keyitems.lua not found")
    text = path.read_text(encoding="utf-8", errors="ignore")
    rows = []
    for m in re.finditer(r"^\s+([A-Z_0-9]+)\s*=\s*(\d+),?\s*$", text, re.M):
        const, kid = m.groups()
        name = const.replace("_", " ")
        rows.append((int(kid), const, normalize(name)))
    con.execute("DELETE FROM topaz_keyitems")
    con.executemany("INSERT OR REPLACE INTO topaz_keyitems VALUES (?,?,?)", rows)
    con.commit()
    return len(rows)


def build_all(con: sqlite3.Connection):
    print(f"topaz_item_basic: {load_item_basic(con)} rows")
    print(f"topaz_item_equipment: {load_item_equipment(con)} rows")
    print(f"topaz_item_weapon: {load_item_weapon(con)} rows")
    print(f"topaz_item_usable: {load_item_usable(con)} rows")
    print(f"topaz_npc_list: {load_npc_list(con)} rows")
    print(f"topaz_mob_pools: {load_mob_pools(con)} rows")
    print(f"topaz_mob_groups: {load_mob_groups(con)} rows")
    print(f"topaz_mob_droplist: {load_mob_droplist(con)} rows")
    print(f"topaz_mob_spawn_points: {load_mob_spawn_points(con)} rows")
    print(f"topaz_instance_entities: {load_instance_entities(con)} rows")
    print(f"topaz_instance_list: {load_instance_list(con)} rows")
    print(f"topaz_mob_skills: {load_mob_skills(con)} rows")
    print(f"topaz_spell_list: {load_spell_list(con)} rows")
    print(f"topaz_abilities: {load_abilities(con)} rows")
    print(f"topaz_weapon_skills: {load_weapon_skills(con)} rows")
    print(f"topaz_traits: {load_traits(con)} rows")
    print(f"topaz_blue_spell_list: {load_blue_spell_list(con)} rows")
    print(f"topaz_pet_list: {load_pet_list(con)} rows")
    print(f"topaz_keyitems: {load_keyitems(con)} rows")


def main():
    con = sqlite3.connect(DB_PATH)
    init_db(con)
    build_all(con)
    con.close()


if __name__ == "__main__":
    main()
