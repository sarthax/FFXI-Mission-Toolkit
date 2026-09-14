#!/usr/bin/env python3
"""
build_lsb_index.py -- indexes the bundled LandSandBoat/ checkout (D:\\Claude\\mission_toolkit\\
LandSandBoat) as a real third data layer for ID-drift checking, alongside Topaz's own sql/ (see
build_topaz_index.py's topaz_* tables) and the external retail-client reference (see
build_database.py's items_external/keyitems_external).

Post-CORE_AGNOSTIC_DESIGN.md phase 1/2 note: build_sql_index.py's sql_* tables are now the CORE
module's LSB-primary loader (its sql_* naming is a historical leftover, not a source label anymore)
-- Topaz's own SQL data lives in build_topaz_index.py's topaz_* tables instead. This file's own
lsb_* tables here are a separate, backport-module-only copy of the same LSB checkout, kept distinct
from build_sql_index.py's sql_* tables so the backport module's diffs don't depend on the core
module's primary loader having been run first.

Why this exists: LSB is what Topaz's Arrapago/Bhaflau/Zhayolm/Silver_Sea/Mamool_Ja/Nyzul_Isle content
was originally backported FROM. Two prior sessions' worth of bugs (wrong event/csid ids, wrong npc
ids, wrong dialog text ids) all came from this exact gap: nothing compared Topaz's own numbers
against LSB's, so a wrong id only ever surfaced by trial and error in-game. This script closes that
gap for two kinds of ground truth LSB actually has:

  1. SQL tables (sql/item_basic.sql, npc_list.sql, mob_groups.sql, mob_pools.sql, mob_droplist.sql,
     mob_spawn_points.sql, instance_entities.sql, instance_list.sql) -- same INSERT-dump format as
     Topaz's own, parsed with the identical tokenizer build_sql_index.py already has (imported, not
     copy-pasted). Loaded into lsb_* tables, each carrying a norm_name column so they can be
     name-joined against Topaz's own topaz_* tables (build_topaz_index.py) and against
     items_external/keyitems_external the
     same way the Item Browser already joins items_ours vs items_external.

  2. Real event/csid ids -- LSB has no per-zone id-constants file (confirmed: only text = {...}
     message-string tables exist, no csid enum). The only real ground truth for "what csid does this
     NPC's trigger actually fire" is the literal integer in each npc script's own
     player:startEvent(N) / csid == N calls. This scrapes those literals from BOTH LandSandBoat's
     scripts/zones/*/npcs/*.lua AND Topaz's own scripts/zones/*/npcs/*.lua (same relative path, same
     filename == same real NPC in both), into one npc_event_refs table tagged by source, so a
     mismatch between the two is a real, queryable row instead of something only found by playing
     through a whole instance again.

  3. Status effect ids -- a Topaz-vs-LSB registration check, not client-based (LSB's modern
     data/status_effects.yaml generates both its C++ enum and its Lua xi.effect table; Topaz's
     src/map/status_effect.h is a separate hand-written C++ enum) -- see load_effects().

LSB's checkout is now the FULL LandSandBoat/server repo (github.com/LandSandBoat/server, "base"
branch, ~180MB, pulled 2026-09-06 via install_external_tools.py's install_landsandboat_full() --
replacing an earlier partial extract that only had scripts/zones/ for 6 zones and no scripts/globals/
at all, which made effect-id comparison impossible). Every zone's scripts, the full sql/ dump, and
data/status_effects.yaml are all present now.

Usage:
    py -3 build_lsb_index.py                 # parse and (re)load every lsb_* table + event refs
"""
import re
import sqlite3
import sys
from pathlib import Path

import yaml

import build_database
import build_sql_index as sqlidx
import settings

TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
LSB_ROOT = TOOLS_ROOT / "LandSandBoat"
LSB_SQL_DIR = LSB_ROOT / "sql"
LSB_SCRIPTS_DIR = LSB_ROOT / "scripts" / "zones"
LSB_STATUS_EFFECTS_YAML = LSB_ROOT / "data" / "status_effects.yaml"
TOPAZ_SCRIPTS_DIR = TOPAZ_ROOT / "scripts" / "zones"
TOPAZ_STATUS_EFFECT_H = TOPAZ_ROOT / "src" / "map" / "status_effect.h"

normalize = build_database.normalize
parse_table_file = sqlidx.parse_table_file
unquote = sqlidx.unquote

SET_VAR_RE = re.compile(r"^SET\s+@(\w+)\s*=\s*([^;]+);")


def resolve_sql_vars(path: Path) -> dict[str, int]:
    """LSB's item_basic.sql (unlike Topaz's, which writes raw ints) defines its flag/type/aH
    columns as `SET @NAME = <expr>;` variables, then references them as bare `@NAME` -- real
    MariaDB session variables that only resolve at import time. Since this parser never actually
    runs the .sql through a server, walk the SET lines once (in file order, so a var defined from
    other already-defined vars resolves correctly) and evaluate each right-hand side ourselves."""
    variables: dict[str, int] = {}
    if not path.exists():
        return variables
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = SET_VAR_RE.match(line.strip())
        if not m:
            continue
        name, expr = m.groups()
        variables[name] = _eval_flags_expr(expr, variables)
    return variables


def _eval_flags_expr(expr: str, variables: dict[str, int]) -> int:
    """Evaluates a `@A | @B | 3` style expression using only already-resolved variables and
    integer literals -- never Python eval() on data pulled from a file."""
    total = 0
    for token in expr.split("|"):
        token = token.strip().lstrip("@")
        if not token:
            continue
        if token.lstrip("-").isdigit():
            total |= int(token)
        elif token in variables:
            total |= variables[token]
    return total



def _resolve_field(raw: str, variables: dict[str, int]) -> int:
    """A field value that's either a plain int literal or a `@VAR | @VAR2` expression -- LSB's
    item_basic.sql mixes both across its own rows (e.g. `@NONE` for aH, a literal for BaseSell)."""
    raw = raw.strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return _eval_flags_expr(raw, variables)


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS lsb_item_basic (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT,
            stackSize INTEGER, flags INTEGER, aH INTEGER, BaseSell INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_item_equipment (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, level INTEGER, ilevel INTEGER,
            jobs INTEGER, shieldSize INTEGER, slot INTEGER, rslot INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_item_weapon (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, skill INTEGER, subskill INTEGER,
            dmgType INTEGER, delay INTEGER, dmg INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_item_usable (
            itemid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, validTargets INTEGER,
            activation REAL, animation INTEGER, maxCharges INTEGER, useDelay INTEGER,
            reuseDelay INTEGER, aoe INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_npc_list (
            npcid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, zoneid INTEGER,
            pos_x REAL, pos_y REAL, pos_z REAL, pos_rot REAL, entityFlags INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_mob_groups (
            zoneid INTEGER, groupid INTEGER, poolid INTEGER, name TEXT, norm_name TEXT,
            respawntime INTEGER, minLevel INTEGER, maxLevel INTEGER, dropid INTEGER,
            PRIMARY KEY (zoneid, groupid)
        );
        CREATE TABLE IF NOT EXISTS lsb_mob_pools (
            poolid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, familyid INTEGER, modelid TEXT
        );
        CREATE TABLE IF NOT EXISTS lsb_mob_droplist (
            dropid INTEGER, dropType INTEGER, groupId INTEGER, groupRate INTEGER,
            itemId INTEGER, itemRate INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_mob_spawn_points (
            mobid INTEGER PRIMARY KEY, mobname TEXT, norm_name TEXT, groupid INTEGER,
            pos_x REAL, pos_y REAL, pos_z REAL, pos_rot REAL
        );
        CREATE TABLE IF NOT EXISTS lsb_instance_entities (
            instanceid INTEGER, id INTEGER, PRIMARY KEY (instanceid, id)
        );
        CREATE TABLE IF NOT EXISTS lsb_instance_list (
            instanceid INTEGER PRIMARY KEY, instance_name TEXT, instance_zone INTEGER,
            entrance_zone INTEGER, start_x REAL, start_y REAL, start_z REAL
        );
        CREATE TABLE IF NOT EXISTS lsb_mob_skills (
            mob_skill_id INTEGER PRIMARY KEY, mob_anim_id INTEGER, name TEXT, norm_name TEXT,
            aoe INTEGER, distance REAL, anim_time INTEGER, prepare_time INTEGER,
            valid_targets INTEGER, skill_flag INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_spell_list (
            spellid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, element INTEGER, skill INTEGER,
            mpCost INTEGER, castTime INTEGER, recastTime INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_abilities (
            abilityId INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, job INTEGER, level INTEGER,
            recastTime INTEGER, recastId INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_weapon_skills (
            weaponskillid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, skilllevel INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_traits (
            traitid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT
        );
        CREATE TABLE IF NOT EXISTS lsb_blue_spell_list (
            spellid INTEGER PRIMARY KEY, mob_skill_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_pet_list (
            petid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, poolid INTEGER
        );
        CREATE TABLE IF NOT EXISTS lsb_effects (
            effectid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT, display_name TEXT
        );
        CREATE TABLE IF NOT EXISTS topaz_effects (
            effectid INTEGER PRIMARY KEY, name TEXT, norm_name TEXT
        );
        CREATE TABLE IF NOT EXISTS npc_event_refs (
            source TEXT, zone_name TEXT, npc_script TEXT, csid INTEGER,
            PRIMARY KEY (source, zone_name, npc_script, csid)
        );
        CREATE INDEX IF NOT EXISTS idx_lsb_mob_groups_poolid ON lsb_mob_groups(poolid);
        CREATE INDEX IF NOT EXISTS idx_lsb_mob_spawn_groupid ON lsb_mob_spawn_points(groupid);
        CREATE INDEX IF NOT EXISTS idx_npc_event_refs_zone_npc ON npc_event_refs(zone_name, npc_script);
    """)
    con.commit()


def _zoneid_from_npcid(npcid: int) -> int:
    # Same real bit-encoding confirmed live this session (entity_profile.py:126,
    # Packetlyzer/analyzer/npc_lookup.py:82) -- npc_list here has no explicit zoneid column, same
    # as Topaz's own npc_list.sql, so both sides need this to derive one.
    return (npcid >> 12) & 0xFFF


def load_item_basic(con: sqlite3.Connection) -> int:
    cols = ["itemid", "subid", "name", "sortname", "name_jp", "type", "stackSize", "flags", "aH", "BaseSell"]
    variables = resolve_sql_vars(sqlidx.cleaned_path(LSB_SQL_DIR / "item_basic.sql"))
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "item_basic.sql"), "item_basic", cols):
        name = unquote(r["name"])
        rows.append((int(r["itemid"]), name, normalize(name),
                      _resolve_field(r["stackSize"], variables), _resolve_field(r["flags"], variables),
                      _resolve_field(r["aH"], variables), _resolve_field(r["BaseSell"], variables)))
    con.execute("DELETE FROM lsb_item_basic")
    con.executemany("INSERT OR REPLACE INTO lsb_item_basic VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_equipment(con: sqlite3.Connection) -> int:
    cols = ["itemId", "name", "level", "ilevel", "jobs", "MId", "shieldSize", "scriptType",
             "slot", "rslot", "rslotlook", "su_level"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "item_equipment.sql"), "item_equipment", cols):
        name = unquote(r["name"])
        rows.append((int(r["itemId"]), name, normalize(name), int(r["level"]), int(r["ilevel"]),
                      int(r["jobs"]), int(r["shieldSize"]), int(r["slot"]), int(r["rslot"])))
    con.execute("DELETE FROM lsb_item_equipment")
    con.executemany("INSERT OR REPLACE INTO lsb_item_equipment VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_weapon(con: sqlite3.Connection) -> int:
    cols = ["itemId", "name", "skill", "subskill", "ilvl_skill", "ilvl_parry", "ilvl_macc",
             "dmgType", "hit", "delay", "dmg", "unlock_points"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "item_weapon.sql"), "item_weapon", cols):
        name = unquote(r["name"])
        rows.append((int(r["itemId"]), name, normalize(name), int(r["skill"]), int(r["subskill"]),
                      int(r["dmgType"]), int(r["delay"]), int(r["dmg"])))
    con.execute("DELETE FROM lsb_item_weapon")
    con.executemany("INSERT OR REPLACE INTO lsb_item_weapon VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_usable(con: sqlite3.Connection) -> int:
    cols = ["itemid", "name", "validTargets", "activation", "animation", "animationTime",
             "maxCharges", "useDelay", "reuseDelay", "aoe"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "item_usable.sql"), "item_usable", cols):
        name = unquote(r["name"])
        rows.append((int(r["itemid"]), name, normalize(name), int(r["validTargets"]), float(r["activation"]),
                      int(r["animation"]), int(r["maxCharges"]), int(r["useDelay"]), int(r["reuseDelay"]),
                      int(r["aoe"])))
    con.execute("DELETE FROM lsb_item_usable")
    con.executemany("INSERT OR REPLACE INTO lsb_item_usable VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_npc_list(con: sqlite3.Connection) -> int:
    cols = ["npcid", "name", "polutils_name", "pos_rot", "pos_x", "pos_y", "pos_z", "flag",
            "speed", "speedsub", "animation", "animationsub", "namevis", "status",
            "entityFlags", "look", "name_prefix", "content_tag", "widescan"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "npc_list.sql"), "npc_list", cols):
        npcid = int(r["npcid"])
        name = unquote(r["name"])
        rows.append((npcid, name, normalize(name), _zoneid_from_npcid(npcid),
                      float(r["pos_x"]), float(r["pos_y"]), float(r["pos_z"]), float(r["pos_rot"]),
                      int(r["entityFlags"])))
    con.execute("DELETE FROM lsb_npc_list")
    con.executemany("INSERT OR REPLACE INTO lsb_npc_list VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_groups(con: sqlite3.Connection) -> int:
    cols = ["groupid", "poolid", "zoneid", "name", "respawntime", "spawntype", "dropid",
            "HP", "MP", "allegiance", "content_tag"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "mob_groups.sql"), "mob_groups", cols):
        name = unquote(r["name"])
        rows.append((int(r["zoneid"]), int(r["groupid"]), int(r["poolid"]), name, normalize(name),
                      int(r["respawntime"]), 0, 0, int(r["dropid"])))
    con.execute("DELETE FROM lsb_mob_groups")
    con.executemany("INSERT OR REPLACE INTO lsb_mob_groups VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_pools(con: sqlite3.Connection) -> int:
    cols = ["poolid", "name", "packet_name", "speciesid", "modelid", "mJob", "sJob", "cmbSkill",
            "cmbDelay", "cmbDmgMult", "behavior", "aggro", "true_detection", "links", "mobType",
            "immunity", "name_prefix", "flag", "entityFlags", "animationsub", "hasSpellScript",
            "spellList", "namevis", "roamflag", "skill_list_id", "resist_id", "modelSize", "modelHitboxSize"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "mob_pools.sql"), "mob_pools", cols):
        name = unquote(r["name"])
        rows.append((int(r["poolid"]), name, normalize(name), int(r["speciesid"]), r["modelid"]))
    con.execute("DELETE FROM lsb_mob_pools")
    con.executemany("INSERT OR REPLACE INTO lsb_mob_pools VALUES (?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_droplist(con: sqlite3.Connection) -> int:
    cols = ["dropId", "dropType", "groupId", "groupRate", "itemId", "itemRate"]
    variables = resolve_sql_vars(sqlidx.cleaned_path(LSB_SQL_DIR / "mob_droplist.sql"))
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "mob_droplist.sql"), "mob_droplist", cols):
        rows.append((int(r["dropId"]), int(r["dropType"]), int(r["groupId"]),
                      _resolve_field(r["groupRate"], variables),
                      int(r["itemId"]), _resolve_field(r["itemRate"], variables)))
    con.execute("DELETE FROM lsb_mob_droplist")
    con.executemany("INSERT INTO lsb_mob_droplist VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_spawn_points(con: sqlite3.Connection) -> int:
    cols = ["mobid", "spawnslotid", "mobname", "polutils_name", "groupid", "minLevel", "maxLevel",
            "pos_x", "pos_y", "pos_z", "pos_rot", "spawnHour", "despawnHour"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "mob_spawn_points.sql"), "mob_spawn_points", cols):
        name = unquote(r["mobname"])
        rows.append((int(r["mobid"]), name, normalize(name), int(r["groupid"]),
                      float(r["pos_x"]), float(r["pos_y"]), float(r["pos_z"]), float(r["pos_rot"])))
    con.execute("DELETE FROM lsb_mob_spawn_points")
    con.executemany("INSERT OR REPLACE INTO lsb_mob_spawn_points VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_entities(con: sqlite3.Connection) -> int:
    cols = ["instanceid", "id"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "instance_entities.sql"), "instance_entities", cols):
        rows.append((int(r["instanceid"]), int(r["id"])))
    con.execute("DELETE FROM lsb_instance_entities")
    con.executemany("INSERT OR REPLACE INTO lsb_instance_entities VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_list(con: sqlite3.Connection) -> int:
    cols = ["instanceid", "instance_name", "instance_zone", "entrance_zone", "overlay_id",
            "time_limit", "start_x", "start_y", "start_z", "start_rot", "music_day", "music_night",
            "battlesolo", "battlemulti"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "instance_list.sql"), "instance_list", cols):
        rows.append((int(r["instanceid"]), unquote(r["instance_name"]), int(r["instance_zone"]),
                      int(r["entrance_zone"]), float(r["start_x"]), float(r["start_y"]), float(r["start_z"])))
    con.execute("DELETE FROM lsb_instance_list")
    con.executemany("INSERT OR REPLACE INTO lsb_instance_list VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_skills(con: sqlite3.Connection) -> int:
    # LSB's own schema carries one extra column (mob_skill_aoe_radius) that Topaz's doesn't --
    # confirmed via direct CREATE TABLE comparison, not assumed from Topaz's shape.
    cols = ["mob_skill_id", "mob_anim_id", "mob_skill_name", "mob_skill_aoe", "mob_skill_aoe_radius",
            "mob_skill_distance", "mob_anim_time", "mob_prepare_time", "mob_valid_targets",
            "mob_skill_flag", "mob_skill_param", "knockback", "primary_sc", "secondary_sc", "tertiary_sc"]
    path = sqlidx.cleaned_path(LSB_SQL_DIR / "mob_skills.sql")
    variables = resolve_sql_vars(path)
    rows = []
    for r in parse_table_file(path, "mob_skills", cols):
        name = unquote(r["mob_skill_name"])
        rows.append((
            int(r["mob_skill_id"]), int(r["mob_anim_id"]), name, normalize(name),
            int(r["mob_skill_aoe"]), float(r["mob_skill_distance"]), int(r["mob_anim_time"]),
            int(r["mob_prepare_time"]), int(r["mob_valid_targets"]),
            _resolve_field(r["mob_skill_flag"], variables),
        ))
    con.execute("DELETE FROM lsb_mob_skills")
    con.executemany("INSERT OR REPLACE INTO lsb_mob_skills VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_spell_list(con: sqlite3.Connection) -> int:
    # LSB's schema has one extra column ("radius", before content_tag) vs Topaz's, and uses
    # @ELEMENT_*/@SKILL_* SQL variables for the element/skill fields instead of Topaz's raw ints.
    cols = ["spellid", "name", "jobs", "group", "family", "element", "zonemisc", "validTargets",
            "skill", "mpCost", "castTime", "recastTime", "message", "magicBurstMessage",
            "animation", "animationTime", "AOE", "base", "multiplier", "CE", "VE",
            "requirements", "spell_range", "radius", "content_tag"]
    path = sqlidx.cleaned_path(LSB_SQL_DIR / "spell_list.sql")
    variables = resolve_sql_vars(path)
    rows = []
    for r in parse_table_file(path, "spell_list", cols):
        name = unquote(r["name"])
        rows.append((
            int(r["spellid"]), name, normalize(name),
            _resolve_field(r["element"], variables), _resolve_field(r["skill"], variables),
            int(r["mpCost"]), int(r["castTime"]), int(r["recastTime"]),
        ))
    con.execute("DELETE FROM lsb_spell_list")
    con.executemany("INSERT OR REPLACE INTO lsb_spell_list VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_abilities(con: sqlite3.Connection) -> int:
    # LSB's schema has one extra column ("radius", right after isAOE) vs Topaz's.
    cols = ["abilityId", "name", "job", "level", "validTarget", "recastTime", "recastId",
            "message1", "message2", "animation", "animationTime", "castTime", "actionType",
            "range", "isAOE", "radius", "CE", "VE", "meritModID", "addType", "content_tag"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "abilities.sql"), "abilities", cols):
        name = unquote(r["name"])
        rows.append((
            int(r["abilityId"]), name, normalize(name), int(r["job"]), int(r["level"]),
            int(r["recastTime"]), int(r["recastId"]), int(r["animation"]),
        ))
    con.execute("DELETE FROM lsb_abilities")
    con.executemany("INSERT OR REPLACE INTO lsb_abilities VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_weapon_skills(con: sqlite3.Connection) -> int:
    # LSB has one extra column ("radius", right after aoe) vs Topaz's.
    cols = ["weaponskillid", "name", "jobs", "type", "skilllevel", "element", "animation",
            "animationTime", "range", "aoe", "radius", "primary_sc", "secondary_sc",
            "tertiary_sc", "main_only", "unlock_id"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "weapon_skills.sql"), "weapon_skills", cols):
        name = unquote(r["name"])
        rows.append((int(r["weaponskillid"]), name, normalize(name), int(r["skilllevel"]), int(r["animation"])))
    con.execute("DELETE FROM lsb_weapon_skills")
    con.executemany("INSERT OR REPLACE INTO lsb_weapon_skills VALUES (?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_traits(con: sqlite3.Connection) -> int:
    cols = ["traitid", "name", "job", "level", "rank", "modifier", "value", "content_tag", "meritid"]
    seen = {}
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "traits.sql"), "traits", cols):
        name = unquote(r["name"])
        seen[int(r["traitid"])] = (name, normalize(name))
    con.execute("DELETE FROM lsb_traits")
    con.executemany("INSERT OR REPLACE INTO lsb_traits VALUES (?,?,?)",
                     [(tid, name, norm) for tid, (name, norm) in seen.items()])
    con.commit()
    return len(seen)


def load_blue_spell_list(con: sqlite3.Connection) -> int:
    # LSB has two extra columns (tertiary_sc, knockback) after secondary_sc vs Topaz's.
    cols = ["spellid", "mob_skill_id", "set_points", "trait_category", "trait_category_weight",
            "primary_sc", "secondary_sc", "tertiary_sc", "knockback"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "blue_spell_list.sql"), "blue_spell_list", cols):
        rows.append((int(unquote(r["spellid"])), int(unquote(r["mob_skill_id"]))))
    con.execute("DELETE FROM lsb_blue_spell_list")
    con.executemany("INSERT OR REPLACE INTO lsb_blue_spell_list VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_pet_list(con: sqlite3.Connection) -> int:
    # LSB has one extra column ("damageType") appended vs Topaz's.
    cols = ["petid", "name", "poolid", "minLevel", "maxLevel", "time", "element", "damageType"]
    rows = []
    for r in parse_table_file(sqlidx.cleaned_path(LSB_SQL_DIR / "pet_list.sql"), "pet_list", cols):
        name = unquote(r["name"])
        rows.append((int(r["petid"]), name, normalize(name), int(r["poolid"])))
    con.execute("DELETE FROM lsb_pet_list")
    con.executemany("INSERT OR REPLACE INTO lsb_pet_list VALUES (?,?,?,?)", rows)
    con.commit()
    return len(rows)


def _lsb_effect_norm_name(key: str) -> str:
    """LSB's status_effects.yaml key names a rank-1 variant with an explicit "_i" suffix
    ("sleep_i", "curse_i", "charm_i", "encumbrance_i", "divine_caress_i" -- confirmed the only 5
    keys in the whole file that end this way), while Topaz's C++ enum never suffixes rank 1
    (EFFECT_SLEEP, EFFECT_CURSE, EFFECT_CHARM). Both sides suffix rank 2+ the same way (_ii/_II,
    _iii/_III), so stripping only a literal trailing "_i" (not "_ii"/"_iii", which don't end in
    the two characters "_i") aligns the two naming conventions without needing per-name guesses."""
    if key.endswith("_i"):
        key = key[:-2]
    return normalize(key)


def load_effects(con: sqlite3.Connection) -> tuple[int, int]:
    """Status effect ids, LSB-vs-Topaz -- a genuine registration/enum check per the user's own
    framing ("Topaz - LSB to make sure things are registered the same for effects"), not client-
    based. LSB (modern checkout) generates both its C++ enum and its Lua xi.effect table from this
    one data/status_effects.yaml at build time (confirmed via the file's own `meta.enum` header) --
    Topaz's side is still a hand-written C++ enum in src/map/status_effect.h with no such
    generator, so mismatches here are real drift, not a parsing artifact."""
    lsb_rows = []
    if LSB_STATUS_EFFECTS_YAML.exists():
        data = yaml.safe_load(LSB_STATUS_EFFECTS_YAML.read_text(encoding="utf-8", errors="ignore"))
        for key, entry in (data.get("status_effects") or {}).items():
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            lsb_rows.append((int(entry["id"]), key, _lsb_effect_norm_name(key), entry.get("name", key)))
    con.execute("DELETE FROM lsb_effects")
    con.executemany("INSERT OR REPLACE INTO lsb_effects VALUES (?,?,?,?)", lsb_rows)

    topaz_rows = []
    if TOPAZ_STATUS_EFFECT_H.exists():
        text = TOPAZ_STATUS_EFFECT_H.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"\bEFFECT_(\w+)\s*=\s*(\d+)\s*,", text):
            name, effectid = m.groups()
            topaz_rows.append((int(effectid), name.lower(), normalize(name)))
    con.execute("DELETE FROM topaz_effects")
    con.executemany("INSERT OR REPLACE INTO topaz_effects VALUES (?,?,?)", topaz_rows)

    con.commit()
    return len(lsb_rows), len(topaz_rows)


EVENT_ID_RE = re.compile(r"(?:startEvent|StartEvent)\s*\(\s*(\d+)|csid\s*==\s*(\d+)")


def _scan_npc_event_refs(zones_dir: Path) -> list[tuple[str, str, int]]:
    """Returns [(zone_name, npc_script, csid), ...] scraped from every scripts/zones/*/npcs/*.lua
    file under zones_dir -- real literal integers only (a variable-driven csid, e.g. a table
    lookup, contributes nothing here rather than a guessed value)."""
    rows = []
    if not zones_dir.is_dir():
        return rows
    for zone_dir in zones_dir.iterdir():
        npcs_dir = zone_dir / "npcs"
        if not npcs_dir.is_dir():
            continue
        for lua_file in npcs_dir.glob("*.lua"):
            text = lua_file.read_text(encoding="utf-8", errors="ignore")
            csids = set()
            for m in EVENT_ID_RE.finditer(text):
                csids.add(int(m.group(1) or m.group(2)))
            for csid in csids:
                rows.append((zone_dir.name, lua_file.stem, csid))
    return rows


def load_npc_event_refs(con: sqlite3.Connection) -> tuple[int, int]:
    lsb_rows = _scan_npc_event_refs(LSB_SCRIPTS_DIR)
    topaz_rows = _scan_npc_event_refs(TOPAZ_SCRIPTS_DIR)
    con.execute("DELETE FROM npc_event_refs WHERE source = 'lsb'")
    con.execute("DELETE FROM npc_event_refs WHERE source = 'topaz'")
    con.executemany("INSERT OR REPLACE INTO npc_event_refs VALUES ('lsb', ?, ?, ?)", lsb_rows)
    con.executemany("INSERT OR REPLACE INTO npc_event_refs VALUES ('topaz', ?, ?, ?)", topaz_rows)
    con.commit()
    return len(lsb_rows), len(topaz_rows)


def build_all(con: sqlite3.Connection):
    print(f"lsb_item_basic: {load_item_basic(con)} rows")
    print(f"lsb_item_equipment: {load_item_equipment(con)} rows")
    print(f"lsb_item_weapon: {load_item_weapon(con)} rows")
    print(f"lsb_item_usable: {load_item_usable(con)} rows")
    print(f"lsb_npc_list: {load_npc_list(con)} rows")
    print(f"lsb_mob_groups: {load_mob_groups(con)} rows")
    print(f"lsb_mob_pools: {load_mob_pools(con)} rows")
    print(f"lsb_mob_droplist: {load_mob_droplist(con)} rows")
    print(f"lsb_mob_spawn_points: {load_mob_spawn_points(con)} rows")
    print(f"lsb_instance_entities: {load_instance_entities(con)} rows")
    print(f"lsb_instance_list: {load_instance_list(con)} rows")
    print(f"lsb_mob_skills: {load_mob_skills(con)} rows")
    print(f"lsb_spell_list: {load_spell_list(con)} rows")
    print(f"lsb_abilities: {load_abilities(con)} rows")
    print(f"lsb_weapon_skills: {load_weapon_skills(con)} rows")
    print(f"lsb_traits: {load_traits(con)} rows")
    print(f"lsb_blue_spell_list: {load_blue_spell_list(con)} rows")
    print(f"lsb_pet_list: {load_pet_list(con)} rows")
    lsb_effects_n, topaz_effects_n = load_effects(con)
    print(f"lsb_effects: {lsb_effects_n} rows, topaz_effects: {topaz_effects_n} rows")
    lsb_n, topaz_n = load_npc_event_refs(con)
    print(f"npc_event_refs: {lsb_n} lsb rows, {topaz_n} topaz rows")


def main():
    con = sqlite3.connect(DB_PATH)
    init_db(con)
    build_all(con)
    con.close()


if __name__ == "__main__":
    main()
