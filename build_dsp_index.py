#!/usr/bin/env python3
"""
build_dsp_index.py -- indexes an old-DSP (DarkStar-lineage) server checkout as a real fourth data
layer for ID-drift checking, alongside Topaz's own sql/ (build_sql_index.py), LandSandBoat
(build_lsb_index.py), and the external retail-client reference (build_database.py).

Why this exists: the user asked whether this toolkit supports "older DSP sql and namespaces and
formats" -- a real schema audit (this session) found DSP's sql/ dumps are MOSTLY the same shape as
Topaz's/LSB's, but with real, confirmed differences that a naive "just point TOPAZ_ROOT at a DSP
checkout" approach would silently get wrong:

  - item_equipment.sql doesn't exist -- DSP calls it item_armor.sql (same 10-column shape, just a
    table/file rename).
  - mob_groups.sql has NO `name` column at all (11 cols vs Topaz's/LSB's 12) -- this script derives
    a display name via mob_pools.name (joined by poolid) instead, since every real mob_groups row
    has a poolid.
  - instance_list.sql is missing `instance_zone` (12 cols vs 13).
  - spell_list.sql is missing `family` (23 cols vs 24).
  - traits.sql is missing `meritid` (8 cols vs 9).
  - No `@variable`-style SQL (simpler than LSB's item_basic.sql/mob_droplist.sql/mob_skills.sql).
  - Trailing inline `-- comment` after many INSERT statements' closing `);` is FAR more common than
    in Topaz's or LSB's own dumps (confirmed live: mob_groups.sql alone has 1,217 such lines,
    mob_spawn_points.sql 591, blue_spell_list.sql 177, mob_skills.sql 128) -- build_sql_index.py's
    cleaned_path() is essential here, not optional.

Everything else (scripts/zones/*/npcs/*.lua using the same real player:startEvent(N) literal
convention, src/map/status_effect.h using the same hand-written C++ EFFECT_X = N enum) is
confirmed identical in shape to Topaz's own, so the same scraping approach build_lsb_index.py
already built is reused here directly (no new parsing logic needed for those two).

DSP's checkout is NOT bundled/downloaded like LandSandBoat -- it's a real pre-existing local
checkout the user already has, so its root comes from Settings' dsp_server_path
(settings.get_dsp_root()), same "the user tells us where it is" model as topaz_server_path. If
unset, every function here degrades to "0 rows" rather than guessing a path.

Usage:
    py -3 build_dsp_index.py                 # parse and (re)load every dsp_* table + event refs
"""
import re
import sqlite3
from pathlib import Path

import build_database
import build_sql_index as sqlidx
import settings

TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
DSP_ROOT = settings.get_dsp_root()
DSP_SQL_DIR = (DSP_ROOT / "sql") if DSP_ROOT else None
DSP_SCRIPTS_DIR = (DSP_ROOT / "scripts" / "zones") if DSP_ROOT else None
DSP_STATUS_EFFECT_H = (DSP_ROOT / "src" / "map" / "status_effect.h") if DSP_ROOT else None
TOPAZ_SCRIPTS_DIR = TOPAZ_ROOT / "scripts" / "zones"
TOPAZ_STATUS_EFFECT_H = TOPAZ_ROOT / "src" / "map" / "status_effect.h"

normalize = build_database.normalize
parse_table_file = sqlidx.parse_table_file
unquote = sqlidx.unquote


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS dsp_item_basic (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT,
            stackSize INTEGER, flags INTEGER, aH INTEGER, BaseSell INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_item_equipment (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, level INTEGER, ilevel INTEGER,
            jobs INTEGER, shieldSize INTEGER, slot INTEGER, rslot INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_item_weapon (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, skill INTEGER, subskill INTEGER,
            dmgType INTEGER, delay INTEGER, dmg INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_item_usable (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, validTargets INTEGER,
            activation REAL, animation INTEGER, maxCharges INTEGER, useDelay INTEGER,
            reuseDelay INTEGER, aoe INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_npc_list (
            npcid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, zoneid INTEGER,
            pos_x REAL, pos_y REAL, pos_z REAL, pos_rot REAL, entityFlags INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_mob_groups (
            zoneid INTEGER, groupid INTEGER, poolid INTEGER, name TEXT, norm_name TEXT,
            respawntime INTEGER, minLevel INTEGER, maxLevel INTEGER, dropid INTEGER,
            PRIMARY KEY (zoneid, groupid)
        );
        CREATE TABLE IF NOT EXISTS dsp_mob_pools (
            poolid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, familyid INTEGER, modelid TEXT
        );
        CREATE TABLE IF NOT EXISTS dsp_mob_droplist (
            dropid INTEGER, dropType INTEGER, groupId INTEGER, groupRate INTEGER,
            itemId INTEGER, itemRate INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_mob_spawn_points (
            mobid INTEGER PRIMARY KEY, mobname TEXT, norm_name TEXT, groupid INTEGER,
            pos_x REAL, pos_y REAL, pos_z REAL, pos_rot REAL
        );
        CREATE TABLE IF NOT EXISTS dsp_instance_entities (
            instanceid INTEGER, id INTEGER, PRIMARY KEY (instanceid, id)
        );
        CREATE TABLE IF NOT EXISTS dsp_instance_list (
            instanceid INTEGER PRIMARY KEY, instance_name TEXT, entrance_zone INTEGER,
            start_x REAL, start_y REAL, start_z REAL
        );
        CREATE TABLE IF NOT EXISTS dsp_mob_skills (
            mob_skill_id INTEGER PRIMARY KEY, mob_anim_id INTEGER, name TEXT, norm_name TEXT,
            aoe INTEGER, distance REAL, anim_time INTEGER, prepare_time INTEGER,
            valid_targets INTEGER, skill_flag INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_spell_list (
            spellid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, element INTEGER, skill INTEGER,
            mpCost INTEGER, castTime INTEGER, recastTime INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_abilities (
            abilityId INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, job INTEGER, level INTEGER,
            recastTime INTEGER, recastId INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_weapon_skills (
            weaponskillid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, skilllevel INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_traits (
            traitid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT
        );
        CREATE TABLE IF NOT EXISTS dsp_blue_spell_list (
            spellid INTEGER PRIMARY KEY, mob_skill_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_pet_list (
            petid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, poolid INTEGER
        );
        CREATE TABLE IF NOT EXISTS dsp_effects (
            effectid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_dsp_mob_groups_poolid ON dsp_mob_groups(poolid);
        CREATE INDEX IF NOT EXISTS idx_dsp_mob_spawn_groupid ON dsp_mob_spawn_points(groupid);
    """)
    # npc_event_refs and topaz_effects already exist (created by build_lsb_index.init_db) -- this
    # just adds the 'dsp' source rows to the same shared tables, not a separate schema.
    con.executescript("""
        CREATE TABLE IF NOT EXISTS npc_event_refs (
            source TEXT, zone_name TEXT, npc_script TEXT, csid INTEGER,
            PRIMARY KEY (source, zone_name, npc_script, csid)
        );
        CREATE TABLE IF NOT EXISTS topaz_effects (
            effectid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT
        );
    """)
    con.commit()


def _zoneid_from_npcid(npcid: int) -> int:
    return (npcid >> 12) & 0xFFF


def _empty(reason: str) -> int:
    print(f"  skipped -- {reason}")
    return 0


def load_item_basic(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["itemid", "subid", "name", "sortname", "stackSize", "flags", "aH", "NoSale", "BaseSell"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "item_basic.sql"), "item_basic", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemid"])), name, normalize(name),
                      int(unquote(r["stackSize"])), int(unquote(r["flags"])), int(unquote(r["aH"])), int(unquote(r["BaseSell"]))))
    con.execute("DELETE FROM dsp_item_basic")
    con.executemany("INSERT OR REPLACE INTO dsp_item_basic VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_equipment(con: sqlite3.Connection) -> int:
    # Real finding: DSP has no item_equipment.sql at all -- item_armor.sql is its real predecessor,
    # same 10-column shape (confirmed via direct CREATE TABLE comparison, not assumed).
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["itemId", "name", "level", "ilevel", "jobs", "MId", "shieldSize", "scriptType", "slot", "rslot"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "item_armor.sql"), "item_armor", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemId"])), name, normalize(name), int(unquote(r["level"])), int(unquote(r["ilevel"])),
                      int(unquote(r["jobs"])), int(unquote(r["shieldSize"])), int(unquote(r["slot"])), int(unquote(r["rslot"]))))
    con.execute("DELETE FROM dsp_item_equipment")
    con.executemany("INSERT OR REPLACE INTO dsp_item_equipment VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_weapon(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["itemId", "name", "skill", "subskill", "ilvl_skill", "ilvl_parry", "ilvl_macc",
            "dmgType", "hit", "delay", "dmg", "unlock_points"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "item_weapon.sql"), "item_weapon", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemId"])), name, normalize(name), int(unquote(r["skill"])), int(unquote(r["subskill"])),
                      int(unquote(r["dmgType"])), int(unquote(r["delay"])), int(unquote(r["dmg"]))))
    con.execute("DELETE FROM dsp_item_weapon")
    con.executemany("INSERT OR REPLACE INTO dsp_item_weapon VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_usable(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["itemid", "name", "validTargets", "activation", "animation", "animationTime",
            "maxCharges", "useDelay", "reuseDelay", "aoe"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "item_usable.sql"), "item_usable", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["itemid"])), name, normalize(name), int(unquote(r["validTargets"])), float(unquote(r["activation"])),
                      int(unquote(r["animation"])), int(unquote(r["maxCharges"])), int(unquote(r["useDelay"])), int(unquote(r["reuseDelay"])),
                      int(unquote(r["aoe"]))))
    con.execute("DELETE FROM dsp_item_usable")
    con.executemany("INSERT OR REPLACE INTO dsp_item_usable VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_npc_list(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["npcid", "name", "polutils_name", "pos_rot", "pos_x", "pos_y", "pos_z", "flag",
            "speed", "speedsub", "animation", "animationsub", "namevis", "status",
            "entityFlags", "look", "name_prefix", "content_tag", "widescan"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "npc_list.sql"), "npc_list", cols):
        npcid = int(unquote(r["npcid"]))
        name = unquote(r["name"])
        rows.append((npcid, name, normalize(name), _zoneid_from_npcid(npcid),
                      float(unquote(r["pos_x"])), float(unquote(r["pos_y"])), float(unquote(r["pos_z"])), float(unquote(r["pos_rot"])),
                      int(unquote(r["entityFlags"]))))
    con.execute("DELETE FROM dsp_npc_list")
    con.executemany("INSERT OR REPLACE INTO dsp_npc_list VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_pools(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["poolid", "name", "packet_name", "familyid", "modelid", "mJob", "sJob", "cmbSkill",
            "cmbDelay", "cmbDmgMult", "behavior", "aggro", "true_detection", "links", "mobType",
            "immunity", "name_prefix", "flag", "entityFlags", "animationsub", "hasSpellScript",
            "spellList", "namevis", "roamflag", "skill_list_id"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "mob_pools.sql"), "mob_pools", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["poolid"])), name, normalize(name), int(unquote(r["familyid"])), r["modelid"]))
    con.execute("DELETE FROM dsp_mob_pools")
    con.executemany("INSERT OR REPLACE INTO dsp_mob_pools VALUES (?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_groups(con: sqlite3.Connection) -> int:
    # Real finding: DSP's mob_groups.sql has NO `name` column at all (11 cols vs Topaz's/LSB's 12).
    # Every real row still has a poolid, and mob_pools always has a name, so that's used as the
    # display/comparison name instead -- requires load_mob_pools() to have already run this call.
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["groupid", "poolid", "zoneid", "respawntime", "spawntype", "dropid",
            "HP", "MP", "minLevel", "maxLevel", "allegiance"]
    pool_names = dict(con.execute("SELECT poolid, name FROM dsp_mob_pools").fetchall())
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "mob_groups.sql"), "mob_groups", cols):
        poolid = int(unquote(r["poolid"]))
        name = pool_names.get(poolid, f"pool_{poolid}")
        rows.append((int(unquote(r["zoneid"])), int(unquote(r["groupid"])), poolid, name, normalize(name),
                      int(unquote(r["respawntime"])), int(unquote(r["minLevel"])), int(unquote(r["maxLevel"])), int(unquote(r["dropid"]))))
    con.execute("DELETE FROM dsp_mob_groups")
    con.executemany("INSERT OR REPLACE INTO dsp_mob_groups VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_droplist(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["dropId", "dropType", "groupId", "groupRate", "itemId", "itemRate"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "mob_droplist.sql"), "mob_droplist", cols):
        rows.append((int(unquote(r["dropId"])), int(unquote(r["dropType"])), int(unquote(r["groupId"])), int(unquote(r["groupRate"])),
                      int(unquote(r["itemId"])), int(unquote(r["itemRate"]))))
    con.execute("DELETE FROM dsp_mob_droplist")
    con.executemany("INSERT INTO dsp_mob_droplist VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_spawn_points(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["mobid", "mobname", "polutils_name", "groupid", "pos_x", "pos_y", "pos_z", "pos_rot"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "mob_spawn_points.sql"), "mob_spawn_points", cols):
        name = unquote(r["mobname"])
        rows.append((int(unquote(r["mobid"])), name, normalize(name), int(unquote(r["groupid"])),
                      float(unquote(r["pos_x"])), float(unquote(r["pos_y"])), float(unquote(r["pos_z"])), float(unquote(r["pos_rot"]))))
    con.execute("DELETE FROM dsp_mob_spawn_points")
    con.executemany("INSERT OR REPLACE INTO dsp_mob_spawn_points VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_entities(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["instanceid", "id"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "instance_entities.sql"), "instance_entities", cols):
        rows.append((int(unquote(r["instanceid"])), int(unquote(r["id"]))))
    con.execute("DELETE FROM dsp_instance_entities")
    con.executemany("INSERT OR REPLACE INTO dsp_instance_entities VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_list(con: sqlite3.Connection) -> int:
    # Real finding: DSP's instance_list.sql has no `instance_zone` column (12 cols vs 13).
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["instanceid", "instance_name", "entrance_zone", "time_limit", "start_x", "start_y",
            "start_z", "start_rot", "music_day", "music_night", "battlesolo", "battlemulti"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "instance_list.sql"), "instance_list", cols):
        rows.append((int(unquote(r["instanceid"])), unquote(r["instance_name"]), int(unquote(r["entrance_zone"])),
                      float(unquote(r["start_x"])), float(unquote(r["start_y"])), float(unquote(r["start_z"]))))
    con.execute("DELETE FROM dsp_instance_list")
    con.executemany("INSERT OR REPLACE INTO dsp_instance_list VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_skills(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["mob_skill_id", "mob_anim_id", "mob_skill_name", "mob_skill_aoe", "mob_skill_distance",
            "mob_anim_time", "mob_prepare_time", "mob_valid_targets", "mob_skill_flag",
            "mob_skill_param", "knockback", "primary_sc", "secondary_sc", "tertiary_sc"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "mob_skills.sql"), "mob_skills", cols):
        name = unquote(r["mob_skill_name"])
        rows.append((
            int(unquote(r["mob_skill_id"])), int(unquote(r["mob_anim_id"])), name, normalize(name),
            int(unquote(r["mob_skill_aoe"])), float(unquote(r["mob_skill_distance"])), int(unquote(r["mob_anim_time"])),
            int(unquote(r["mob_prepare_time"])), int(unquote(r["mob_valid_targets"])), int(unquote(r["mob_skill_flag"])),
        ))
    con.execute("DELETE FROM dsp_mob_skills")
    con.executemany("INSERT OR REPLACE INTO dsp_mob_skills VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_spell_list(con: sqlite3.Connection) -> int:
    # Real finding: DSP's spell_list.sql has no `family` column (23 cols vs 24) -- not used by
    # sql_spell_list/lsb_spell_list's own comparison columns anyway, so this only affects parsing
    # alignment for the columns after it, not any data we actually keep.
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["spellid", "name", "jobs", "group", "element", "zonemisc", "validTargets",
            "skill", "mpCost", "castTime", "recastTime", "message", "magicBurstMessage",
            "animation", "animationTime", "AOE", "base", "multiplier", "CE", "VE",
            "requirements", "spell_range", "content_tag"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "spell_list.sql"), "spell_list", cols):
        name = unquote(r["name"])
        rows.append((
            int(unquote(r["spellid"])), name, normalize(name), int(unquote(r["element"])), int(unquote(r["skill"])),
            int(unquote(r["mpCost"])), int(unquote(r["castTime"])), int(unquote(r["recastTime"])),
        ))
    con.execute("DELETE FROM dsp_spell_list")
    con.executemany("INSERT OR REPLACE INTO dsp_spell_list VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_abilities(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["abilityId", "name", "job", "level", "validTarget", "recastTime", "recastId",
            "message1", "message2", "animation", "animationTime", "castTime", "actionType",
            "range", "isAOE", "CE", "VE", "meritModID", "addType", "content_tag"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "abilities.sql"), "abilities", cols):
        name = unquote(r["name"])
        rows.append((
            int(unquote(r["abilityId"])), name, normalize(name), int(unquote(r["job"])), int(unquote(r["level"])),
            int(unquote(r["recastTime"])), int(unquote(r["recastId"])), int(unquote(r["animation"])),
        ))
    con.execute("DELETE FROM dsp_abilities")
    con.executemany("INSERT OR REPLACE INTO dsp_abilities VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_weapon_skills(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["weaponskillid", "name", "jobs", "type", "skilllevel", "element", "animation",
            "animationTime", "range", "aoe", "primary_sc", "secondary_sc",
            "tertiary_sc", "main_only", "unlock_id"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "weapon_skills.sql"), "weapon_skills", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["weaponskillid"])), name, normalize(name), int(unquote(r["skilllevel"])), int(unquote(r["animation"]))))
    con.execute("DELETE FROM dsp_weapon_skills")
    con.executemany("INSERT OR REPLACE INTO dsp_weapon_skills VALUES (?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_traits(con: sqlite3.Connection) -> int:
    # Real finding: DSP's traits.sql has no `meritid` column (8 cols vs 9) -- not kept by our own
    # comparison table anyway (only traitid+name), so this only affects parsing alignment.
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["traitid", "name", "job", "level", "rank", "modifier", "value", "content_tag"]
    seen = {}
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "traits.sql"), "traits", cols):
        name = unquote(r["name"])
        seen[int(unquote(r["traitid"]))] = (name, normalize(name))
    con.execute("DELETE FROM dsp_traits")
    con.executemany("INSERT OR REPLACE INTO dsp_traits VALUES (?,?,?)",
                     [(tid, name, norm) for tid, (name, norm) in seen.items()])
    con.commit()
    return len(seen)


def load_blue_spell_list(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["spellid", "mob_skill_id", "set_points", "trait_category", "trait_category_weight",
            "primary_sc", "secondary_sc"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "blue_spell_list.sql"), "blue_spell_list", cols):
        rows.append((int(unquote(r["spellid"])), int(unquote(r["mob_skill_id"]))))
    con.execute("DELETE FROM dsp_blue_spell_list")
    con.executemany("INSERT OR REPLACE INTO dsp_blue_spell_list VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_pet_list(con: sqlite3.Connection) -> int:
    if not DSP_SQL_DIR:
        return _empty("dsp_server_path not configured")
    cols = ["petid", "name", "poolid", "minLevel", "maxLevel", "time", "element"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(DSP_SQL_DIR / "pet_list.sql"), "pet_list", cols):
        name = unquote(r["name"])
        rows.append((int(unquote(r["petid"])), name, normalize(name), int(unquote(r["poolid"]))))
    con.execute("DELETE FROM dsp_pet_list")
    con.executemany("INSERT OR REPLACE INTO dsp_pet_list VALUES (?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_effects(con: sqlite3.Connection) -> int:
    """DSP's status_effect.h uses the exact same hand-written `EFFECT_X = N,` C++ enum format as
    Topaz's own (confirmed live) -- same regex reused, no YAML/generator involved on either side
    (unlike modern LandSandBoat)."""
    if not DSP_STATUS_EFFECT_H or not DSP_STATUS_EFFECT_H.exists():
        return _empty("dsp_server_path not configured or src/map/status_effect.h missing")
    text = DSP_STATUS_EFFECT_H.read_text(encoding="utf-8", errors="ignore")
    rows = []
    for m in re.finditer(r"\bEFFECT_(\w+)\s*=\s*(\d+)\s*,", text):
        name, effectid = m.groups()
        rows.append((int(effectid), name.lower(), normalize(name)))
    con.execute("DELETE FROM dsp_effects")
    con.executemany("INSERT OR REPLACE INTO dsp_effects VALUES (?,?,?)", rows)
    con.commit()
    return len(rows)


EVENT_ID_RE = re.compile(r"(?:startEvent|StartEvent)\s*\(\s*(\d+)|csid\s*==\s*(\d+)")


def _scan_npc_event_refs(zones_dir: Path) -> list[tuple[str, str, int]]:
    rows = []
    if not zones_dir.is_dir():
        return rows
    for zone_dir in zones_dir.iterdir():
        npcs_dir = zone_dir / "npcs"
        if not npcs_dir.is_dir():
            continue
        for lua_file in npcs_dir.glob("*.lua"):
            text = lua_file.read_text(encoding="utf-8", errors="ignore")
            csids = {int(m.group(1) or m.group(2)) for m in EVENT_ID_RE.finditer(text)}
            for csid in csids:
                rows.append((zone_dir.name, lua_file.stem, csid))
    return rows


def load_npc_event_refs(con: sqlite3.Connection) -> int:
    """Adds 'dsp' rows to the SAME shared npc_event_refs table build_lsb_index.py already
    populates with 'lsb'/'topaz' rows -- so /iddrift's event-drift categories can compare any pair
    of sources, not just LSB-vs-Topaz."""
    if not DSP_SCRIPTS_DIR:
        return _empty("dsp_server_path not configured")
    dsp_rows = _scan_npc_event_refs(DSP_SCRIPTS_DIR)
    con.execute("DELETE FROM npc_event_refs WHERE source = 'dsp'")
    con.executemany("INSERT OR REPLACE INTO npc_event_refs VALUES ('dsp', ?, ?, ?)", dsp_rows)
    con.commit()
    return len(dsp_rows)


def build_all(con: sqlite3.Connection):
    print(f"dsp_item_basic: {load_item_basic(con)} rows")
    print(f"dsp_item_equipment: {load_item_equipment(con)} rows")
    print(f"dsp_item_weapon: {load_item_weapon(con)} rows")
    print(f"dsp_item_usable: {load_item_usable(con)} rows")
    print(f"dsp_npc_list: {load_npc_list(con)} rows")
    print(f"dsp_mob_pools: {load_mob_pools(con)} rows")
    print(f"dsp_mob_groups: {load_mob_groups(con)} rows")
    print(f"dsp_mob_droplist: {load_mob_droplist(con)} rows")
    print(f"dsp_mob_spawn_points: {load_mob_spawn_points(con)} rows")
    print(f"dsp_instance_entities: {load_instance_entities(con)} rows")
    print(f"dsp_instance_list: {load_instance_list(con)} rows")
    print(f"dsp_mob_skills: {load_mob_skills(con)} rows")
    print(f"dsp_spell_list: {load_spell_list(con)} rows")
    print(f"dsp_abilities: {load_abilities(con)} rows")
    print(f"dsp_weapon_skills: {load_weapon_skills(con)} rows")
    print(f"dsp_traits: {load_traits(con)} rows")
    print(f"dsp_blue_spell_list: {load_blue_spell_list(con)} rows")
    print(f"dsp_pet_list: {load_pet_list(con)} rows")
    print(f"dsp_effects: {load_effects(con)} rows")
    print(f"npc_event_refs (dsp): {load_npc_event_refs(con)} rows")


def main():
    con = sqlite3.connect(DB_PATH)
    init_db(con)
    build_all(con)
    con.close()


if __name__ == "__main__":
    main()
