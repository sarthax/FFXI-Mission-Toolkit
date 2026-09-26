#!/usr/bin/env python3
"""
build_sql_index.py -- Mission Toolkit GUI, real Phase 2 (persisted SQL indexer).

LSB-primary rewrite (this dist-test copy, 2026-09-08): originally this parsed Topaz's own sql/
dump (settings.get_topaz_root()/sql). This clean-rebuild copy has no bundled Topaz checkout at
all, so it now parses the bundled LandSandBoat/server checkout's sql/ dump instead (same repo
build_lsb_index.py already indexes into lsb_* tables) -- SQL_DIR points at LSB_ROOT/"sql" below.

The sql_* table names/column shapes are kept IDENTICAL to what they always were (no norm_name
column, no LSB-only extra columns exposed) because gui_server.py's queries (item browser joins,
sql_browse, zero-position/unregistered reports, entity lookups) all depend on that exact shape --
grep gui_server.py for "sql_" to confirm. What changed per-table is the *source column list* fed
to parse_table_file(), which now matches LSB's real schema (extra columns, @VAR-style flag/type
fields) instead of Topaz's -- ported from build_lsb_index.py's already-proven per-table column
lists and resolve_sql_vars()/_resolve_field() variable resolution, not re-derived by guessing.

Usage:
    py -3 build_sql_index.py                    # parse and (re)load all tables
    py -3 build_sql_index.py --zero-position Nyzul_Isle   # zero-position npc_list rows in a zone
    py -3 build_sql_index.py --unregistered Nyzul_Isle    # npc_list/mob_spawn_points ids with no
                                                            # instance_entities row, in a zone
"""
import argparse
import io
import re
import sqlite3
import sys
from pathlib import Path

import settings

TOOLS_ROOT = Path(__file__).parent
TOPAZ_ROOT = settings.get_topaz_root()
DB_PATH = TOOLS_ROOT / "ffxi_zone_database.db"
LSB_ROOT = TOOLS_ROOT / "LandSandBoat"
SQL_DIR = LSB_ROOT / "sql"


def split_sql_values(paren_body: str) -> list[str]:
    """Splits the inside of an INSERT ... VALUES (...) on top-level commas, respecting single
    quotes (with '' escaping) so a comma inside a quoted string or a hex literal never breaks a
    field boundary. Safer than a fixed-column-count regex per table -- schemas here have enough
    variation (binary blobs, NULLs, optional trailing columns) that a real tokenizer avoids the
    kind of off-by-one field misread that's bitten this project before."""
    fields = []
    buf = []
    in_quote = False
    i = 0
    n = len(paren_body)
    while i < n:
        c = paren_body[i]
        if in_quote:
            # Real dumps here mix both escaping styles for an embedded quote -- '' (SQL-standard)
            # and \' (found live: "Gigas\'s Bats") -- both need handling or the tokenizer treats
            # the backslash-quote as the string's real end and shreds every field after it.
            if c == "\\" and i + 1 < n and paren_body[i + 1] == "'":
                buf.append("\\'")
                i += 2
                continue
            if c == "'" and i + 1 < n and paren_body[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            if c == "'":
                in_quote = False
                buf.append(c)
                i += 1
                continue
            buf.append(c)
            i += 1
            continue
        if c == "'":
            in_quote = True
            buf.append(c)
            i += 1
            continue
        if c == ",":
            fields.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if buf:
        fields.append("".join(buf).strip())
    return fields


def unquote(v: str) -> str | None:
    if v == "NULL":
        return None
    if len(v) >= 2 and v[0] == "'" and v[-1] == "'":
        return v[1:-1].replace("''", "'").replace("\\'", "'")
    return v


SET_VAR_RE = re.compile(r"^SET\s+@(\w+)\s*=\s*([^;]+);")


def resolve_sql_vars(path: Path) -> dict[str, int]:
    """LSB's item_basic.sql/mob_droplist.sql/mob_skills.sql/spell_list.sql (unlike Topaz's, which
    wrote raw ints) define their flag/type/element/aH columns as `SET @NAME = <expr>;` variables,
    then reference them as bare `@NAME` -- real MariaDB session variables that only resolve at
    import time. Since this parser never actually runs the .sql through a server, walk the SET
    lines once (in file order, so a var defined from other already-defined vars resolves
    correctly) and evaluate each right-hand side ourselves. Ported verbatim from
    build_lsb_index.py, which proved this against LSB's real dumps first."""
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
    item_basic.sql/mob_droplist.sql/mob_skills.sql/spell_list.sql all mix both across their own
    rows."""
    raw = raw.strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    return _eval_flags_expr(raw, variables)


INSERT_RE = re.compile(r"^INSERT INTO `(\w+)` VALUES\s*(.*)$", re.DOTALL)


def split_insert_tuples(values_blob: str) -> list[str]:
    """Splits a `(...), (...), (...)` VALUES blob into each parenthesized row's raw inner text.

    Some legacy DSP dumps (confirmed on mob_spawn_points.sql and others) write real multi-row
    INSERT statements -- `INSERT INTO ... VALUES (...),(...),(...);` -- rather than one row per
    statement. _iter_sql_statements()/INSERT_RE only isolate the *statement*; without this, the
    ')' ending one row and the '(' opening the next both land inside split_sql_values()'s flat
    top-level-comma split (which tracks quoting but not parens), gluing one row's real column
    value to the next row's leading digits (e.g. a pos_x field ending up as "17021);179") and
    crashing float()/int() conversion downstream. Tracks paren depth and quoting (both ''
    SQL-standard and \\' escaping, matching split_sql_values()) so a comma or paren inside a
    quoted string never breaks a row boundary."""
    tuples = []
    depth = 0
    in_quote = False
    start = None
    i = 0
    n = len(values_blob)
    while i < n:
        c = values_blob[i]
        if in_quote:
            if c == "\\" and i + 1 < n and values_blob[i + 1] == "'":
                i += 2
                continue
            if c == "'" and i + 1 < n and values_blob[i + 1] == "'":
                i += 2
                continue
            if c == "'":
                in_quote = False
            i += 1
            continue
        if c == "'":
            in_quote = True
            i += 1
            continue
        if c == "(":
            if depth == 0:
                start = i + 1
            depth += 1
            i += 1
            continue
        if c == ")":
            depth -= 1
            if depth == 0 and start is not None:
                tuples.append(values_blob[start:i])
                start = None
            i += 1
            continue
        i += 1
    return tuples

_CLEAN_CACHE_DIR = TOOLS_ROOT / "mission_reports" / "_sql_clean"
_TRAILING_COMMENT_RE = re.compile(r"\);\s*--.*$")


def cleaned_path(path: Path) -> Path:
    """Some sql/ dumps (confirmed on both Topaz's and LandSandBoat's own mob_skills.sql/
    spell_list.sql) put an inline `-- explanation` comment after an INSERT statement's closing
    `);` -- INSERT_RE anchors on end-of-line right after `);`, so those lines fail to match and
    get silently dropped (not even a schema-drift warning, since the regex never matches at all).
    Rewriting a cleaned cached copy (comment stripped) is safer than loosening INSERT_RE itself,
    which risks matching a `);` that's genuinely mid-statement in some other file's INSERT."""
    if not path.exists():
        return path
    _CLEAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Keyed by a hash of the full resolved path, not just the filename -- both Topaz's and
    # LandSandBoat's checkouts have a sql/mob_skills.sql and sql/spell_list.sql (same filename,
    # same parent folder name "sql" too), and a weaker cache key would let one fork's cleaned copy
    # silently serve the other fork's parser.
    import hashlib
    key = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    out_path = _CLEAN_CACHE_DIR / f"{key}__{path.name}"
    if out_path.exists() and out_path.stat().st_mtime >= path.stat().st_mtime:
        return out_path
    text = path.read_text(encoding="utf-8", errors="ignore")
    cleaned = "\n".join(_TRAILING_COMMENT_RE.sub(");", line) for line in text.splitlines())
    out_path.write_text(cleaned, encoding="utf-8")
    return out_path


def _iter_sql_statements(text: str):
    """Yield (starting_line, statement) split on semicolons outside SQL single quotes.

    Some legacy DSP dumps place many complete INSERT statements on one physical line.
    A line-anchored greedy INSERT regex therefore merges those rows into one apparent row.
    This scanner also supports multiline INSERTs and ignores semicolons inside quoted strings.
    """
    buf=[]
    in_quote=False
    i=0
    line=1
    statement_line=1
    have_nonspace=False
    while i < len(text):
        ch=text[i]
        if not have_nonspace and not ch.isspace():
            statement_line=line
            have_nonspace=True
        if in_quote:
            if ch=="\\" and i+1 < len(text) and text[i+1]=="'":
                buf.extend((ch,text[i+1])); i+=2
                continue
            if ch=="'" and i+1 < len(text) and text[i+1]=="'":
                buf.extend((ch,text[i+1])); i+=2
                continue
            if ch=="'":
                in_quote=False
            buf.append(ch)
        else:
            if ch=="-" and i+1 < len(text) and text[i+1]=="-":
                # SQL line comment outside a quoted string. Skip through the newline so a
                # standalone comment cannot become a prefix of the next INSERT statement.
                while i < len(text) and text[i]!="\n":
                    i+=1
                if i < len(text) and text[i]=="\n":
                    line+=1
                    if buf:
                        buf.append("\n")
                    i+=1
                continue
            if ch=="'":
                in_quote=True
                buf.append(ch)
            elif ch==";":
                statement="".join(buf).strip()
                if statement:
                    yield statement_line,statement
                buf=[]
                have_nonspace=False
            else:
                buf.append(ch)
        if ch=="\n":
            line+=1
        i+=1
    statement="".join(buf).strip()
    if statement:
        yield statement_line,statement


def parse_table_file(path: Path, expected_table: str, columns: list[str]):
    """Yield one dict per INSERT row for expected_table.

    Statements are tokenized independently of physical lines because legacy DSP dumps may place
    multiple INSERTs on one line or span one INSERT across multiple lines. Rows with a genuinely
    different column count are still skipped with a visible schema-drift warning.
    """
    if not path.exists():
        return
    text=path.read_text(encoding="utf-8",errors="ignore")
    for lineno,statement in _iter_sql_statements(text):
        m=INSERT_RE.match(statement)
        if not m or m.group(1)!=expected_table:
            continue
        for tup_idx,tup in enumerate(split_insert_tuples(m.group(2)),1):
            values=split_sql_values(tup)
            if len(values)!=len(columns):
                print(f"  [!] {path.name}:{lineno} row {tup_idx} has {len(values)} values, "
                      f"expected {len(columns)} for {expected_table} -- skipped (schema drift?)")
                continue
            yield dict(zip(columns,values))


def init_db(con: sqlite3.Connection):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS sql_npc_list (
            npcid INTEGER PRIMARY KEY, name TEXT, polutils_name TEXT,
            pos_rot REAL, pos_x REAL, pos_y REAL, pos_z REAL,
            flag INTEGER, entityFlags INTEGER, content_tag TEXT
        );
        CREATE TABLE IF NOT EXISTS sql_mob_spawn_points (
            mobid INTEGER PRIMARY KEY, mobname TEXT, polutils_name TEXT,
            groupid INTEGER, pos_x REAL, pos_y REAL, pos_z REAL, pos_rot REAL
        );
        CREATE TABLE IF NOT EXISTS sql_mob_groups (
            zoneid INTEGER, groupid INTEGER, poolid INTEGER, name TEXT,
            respawntime INTEGER, minLevel INTEGER, maxLevel INTEGER,
            PRIMARY KEY (zoneid, groupid)
        );
        CREATE TABLE IF NOT EXISTS sql_mob_pools (
            poolid INTEGER PRIMARY KEY, name TEXT, packet_name TEXT, familyid INTEGER, modelid TEXT
        );
        CREATE TABLE IF NOT EXISTS sql_mob_droplist (
            dropid INTEGER, dropType INTEGER, groupId INTEGER, groupRate INTEGER,
            itemId INTEGER, itemRate INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_instance_entities (
            instanceid INTEGER, id INTEGER, PRIMARY KEY (instanceid, id)
        );
        CREATE TABLE IF NOT EXISTS sql_instance_list (
            instanceid INTEGER PRIMARY KEY, instance_name TEXT, instance_zone INTEGER,
            entrance_zone INTEGER, start_x REAL, start_y REAL, start_z REAL
        );
        CREATE TABLE IF NOT EXISTS sql_item_basic (
            itemid INTEGER PRIMARY KEY, name TEXT, sortname TEXT,
            stackSize INTEGER, flags INTEGER, aH INTEGER, NoSale INTEGER, BaseSell INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_item_equipment (
            itemid INTEGER PRIMARY KEY, name TEXT, level INTEGER, ilevel INTEGER,
            jobs INTEGER, shieldSize INTEGER, slot INTEGER, rslot INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_item_weapon (
            itemid INTEGER PRIMARY KEY, name TEXT, skill INTEGER, subskill INTEGER,
            dmgType INTEGER, delay INTEGER, dmg INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_item_usable (
            itemid INTEGER PRIMARY KEY, name TEXT, validTargets INTEGER, activation INTEGER,
            animation INTEGER, maxCharges INTEGER, useDelay INTEGER, reuseDelay INTEGER, aoe INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_mob_skills (
            mob_skill_id INTEGER PRIMARY KEY, mob_anim_id INTEGER, name TEXT,
            aoe INTEGER, distance REAL, anim_time INTEGER, prepare_time INTEGER,
            valid_targets INTEGER, skill_flag INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_spell_list (
            spellid INTEGER PRIMARY KEY, name TEXT, element INTEGER, skill INTEGER,
            mpCost INTEGER, castTime INTEGER, recastTime INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_abilities (
            abilityId INTEGER PRIMARY KEY, name TEXT, job INTEGER, level INTEGER,
            recastTime INTEGER, recastId INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_weapon_skills (
            weaponskillid INTEGER PRIMARY KEY, name TEXT, skilllevel INTEGER, animation INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_traits (
            traitid INTEGER PRIMARY KEY, name TEXT
        );
        CREATE TABLE IF NOT EXISTS sql_blue_spell_list (
            spellid INTEGER PRIMARY KEY, mob_skill_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS sql_pet_list (
            petid INTEGER PRIMARY KEY, name TEXT, poolid INTEGER
        );
    """)
    # sql_mob_groups predates the dropid column (drop-table integration added later) --
    # CREATE TABLE IF NOT EXISTS doesn't retrofit columns onto an already-existing table (same
    # trap hit earlier with sql_mob_pools/modelid and captures/content_type), so migrate it
    # explicitly rather than let load_mob_groups()'s INSERT silently fail on column-count mismatch.
    existing_cols = {r[1] for r in con.execute("PRAGMA table_info(sql_mob_groups)")}
    if "dropid" not in existing_cols:
        con.execute("ALTER TABLE sql_mob_groups ADD COLUMN dropid INTEGER")
    existing_pool_cols = {r[1] for r in con.execute("PRAGMA table_info(sql_mob_pools)")}
    if "cmbDelay" not in existing_pool_cols:
        con.execute("ALTER TABLE sql_mob_pools ADD COLUMN cmbDelay INTEGER")
    con.executescript("""
        CREATE INDEX IF NOT EXISTS idx_sql_mob_spawn_groupid ON sql_mob_spawn_points(groupid);
        CREATE INDEX IF NOT EXISTS idx_sql_mob_groups_poolid ON sql_mob_groups(poolid);
        CREATE INDEX IF NOT EXISTS idx_sql_mob_groups_dropid ON sql_mob_groups(dropid);
        CREATE INDEX IF NOT EXISTS idx_sql_mob_droplist_dropid ON sql_mob_droplist(dropid);
        CREATE INDEX IF NOT EXISTS idx_sql_instance_entities_id ON sql_instance_entities(id);
    """)
    con.commit()


def load_npc_list(con: sqlite3.Connection) -> int:
    # LSB's npc_list.sql has no explicit zoneid/content_tag columns either (same as Topaz's) --
    # real column list confirmed against build_lsb_index.py's load_npc_list(), which parsed this
    # exact file first.
    cols = ["npcid", "name", "polutils_name", "pos_rot", "pos_x", "pos_y", "pos_z", "flag",
            "speed", "speedsub", "animation", "animationsub", "namevis", "status",
            "entityFlags", "look", "name_prefix", "content_tag", "widescan"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "npc_list.sql"), "npc_list", cols):
        rows.append((
            int(r["npcid"]), unquote(r["name"]), unquote(r["polutils_name"]),
            float(r["pos_rot"]), float(r["pos_x"]), float(r["pos_y"]), float(r["pos_z"]),
            int(r["flag"]), int(r["entityFlags"]), unquote(r["content_tag"]),
        ))
    con.execute("DELETE FROM sql_npc_list")
    con.executemany(
        "INSERT OR REPLACE INTO sql_npc_list VALUES (?,?,?,?,?,?,?,?,?,?)", rows
    )
    con.commit()
    return len(rows)


def load_mob_spawn_points(con: sqlite3.Connection) -> int:
    # LSB carries minLevel/maxLevel/spawnHour/despawnHour that Topaz's dump doesn't -- confirmed
    # against build_lsb_index.py's load_mob_spawn_points(), same file.
    cols = ["mobid", "spawnslotid", "mobname", "polutils_name", "groupid", "minLevel", "maxLevel",
            "pos_x", "pos_y", "pos_z", "pos_rot", "spawnHour", "despawnHour"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "mob_spawn_points.sql"), "mob_spawn_points", cols):
        rows.append((
            int(r["mobid"]), unquote(r["mobname"]), unquote(r["polutils_name"]),
            int(r["groupid"]), float(r["pos_x"]), float(r["pos_y"]), float(r["pos_z"]),
            float(r["pos_rot"]),
        ))
    con.execute("DELETE FROM sql_mob_spawn_points")
    con.executemany(
        "INSERT OR REPLACE INTO sql_mob_spawn_points VALUES (?,?,?,?,?,?,?,?)", rows
    )
    con.commit()
    return len(rows)


def load_mob_groups(con: sqlite3.Connection) -> int:
    # LSB's mob_groups.sql has no minLevel/maxLevel columns (those live on mob_spawn_points here)
    # and carries content_tag instead -- confirmed against build_lsb_index.py's load_mob_groups().
    cols = ["groupid", "poolid", "zoneid", "name", "respawntime", "spawntype", "dropid",
            "HP", "MP", "allegiance", "content_tag"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "mob_groups.sql"), "mob_groups", cols):
        rows.append((
            int(r["zoneid"]), int(r["groupid"]), int(r["poolid"]), unquote(r["name"]),
            int(r["respawntime"]), 0, 0, int(r["dropid"]),
        ))
    con.execute("DELETE FROM sql_mob_groups")
    con.executemany(
        "INSERT OR REPLACE INTO sql_mob_groups VALUES (?,?,?,?,?,?,?,?)", rows
    )
    con.commit()
    return len(rows)


def load_mob_droplist(con: sqlite3.Connection) -> int:
    """mob_groups.dropid (NOT mob_pools.poolid) is the real FK into this table -- confirmed
    directly against Topaz's own C++ (mobutils.cpp InstantiateAlly, zoneutils.cpp, instance_loader.cpp
    all read `dropid` off mob_groups/instance rows, never off mob_pools). A pool has no drop table
    of its own; every group spawned from that pool can carry its own dropid. LSB's dump uses
    @VAR-style groupRate/itemRate expressions in places -- resolved via resolve_sql_vars()/
    _resolve_field(), same as build_lsb_index.py's load_mob_droplist()."""
    cols = ["dropId", "dropType", "groupId", "groupRate", "itemId", "itemRate"]
    path = cleaned_path(SQL_DIR / "mob_droplist.sql")
    variables = resolve_sql_vars(path)
    rows = []
    for r in parse_table_file(path, "mob_droplist", cols):
        rows.append((
            int(r["dropId"]), int(r["dropType"]), int(r["groupId"]),
            _resolve_field(r["groupRate"], variables),
            int(r["itemId"]), _resolve_field(r["itemRate"], variables),
        ))
    con.execute("DELETE FROM sql_mob_droplist")
    con.executemany("INSERT INTO sql_mob_droplist VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_pools(con: sqlite3.Connection) -> int:
    # LSB's mob_pools.sql uses "speciesid" where Topaz's used "familyid" (same slot, different
    # column name) and carries several extra columns (resist_id, modelSize, modelHitboxSize, ...)
    # -- confirmed against build_lsb_index.py's load_mob_pools().
    cols = ["poolid", "name", "packet_name", "speciesid", "modelid", "mJob", "sJob", "cmbSkill",
            "cmbDelay", "cmbDmgMult", "behavior", "aggro", "true_detection", "links", "mobType",
            "immunity", "name_prefix", "flag", "entityFlags", "animationsub", "hasSpellScript",
            "spellList", "namevis", "roamflag", "skill_list_id", "resist_id", "modelSize", "modelHitboxSize"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "mob_pools.sql"), "mob_pools", cols):
        rows.append((int(r["poolid"]), unquote(r["name"]), unquote(r["packet_name"]), int(r["speciesid"]),
                     r["modelid"], int(r["cmbDelay"])))
    con.execute("DELETE FROM sql_mob_pools")
    con.executemany("INSERT OR REPLACE INTO sql_mob_pools VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_entities(con: sqlite3.Connection) -> int:
    cols = ["instanceid", "id"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "instance_entities.sql"), "instance_entities", cols):
        rows.append((int(r["instanceid"]), int(r["id"])))
    con.execute("DELETE FROM sql_instance_entities")
    con.executemany("INSERT OR REPLACE INTO sql_instance_entities VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_instance_list(con: sqlite3.Connection) -> int:
    # LSB carries overlay_id/start_rot/music_day/music_night/battlesolo/battlemulti too -- confirmed
    # against build_lsb_index.py's load_instance_list().
    cols = ["instanceid", "instance_name", "instance_zone", "entrance_zone", "overlay_id",
            "time_limit", "start_x", "start_y", "start_z", "start_rot", "music_day", "music_night",
            "battlesolo", "battlemulti"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "instance_list.sql"), "instance_list", cols):
        rows.append((
            int(r["instanceid"]), unquote(r["instance_name"]), int(r["instance_zone"]),
            int(r["entrance_zone"]), float(r["start_x"]), float(r["start_y"]), float(r["start_z"]),
        ))
    con.execute("DELETE FROM sql_instance_list")
    con.executemany("INSERT OR REPLACE INTO sql_instance_list VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_basic(con: sqlite3.Connection) -> int:
    # LSB's item_basic.sql has no NoSale column (Topaz's does) and defines flags/aH/BaseSell as
    # @VAR expressions -- confirmed against build_lsb_index.py's load_item_basic(). NoSale is kept
    # in the sql_item_basic table shape (GUI depends on the column existing) but always written 0
    # since LSB has nothing to source it from.
    cols = ["itemid", "subid", "name", "sortname", "name_jp", "type", "stackSize", "flags", "aH", "BaseSell"]
    path = cleaned_path(SQL_DIR / "item_basic.sql")
    variables = resolve_sql_vars(path)
    rows = []
    for r in parse_table_file(path, "item_basic", cols):
        rows.append((
            int(r["itemid"]), unquote(r["name"]), unquote(r["sortname"]),
            _resolve_field(r["stackSize"], variables), _resolve_field(r["flags"], variables),
            _resolve_field(r["aH"], variables), 0, _resolve_field(r["BaseSell"], variables),
        ))
    con.execute("DELETE FROM sql_item_basic")
    con.executemany("INSERT OR REPLACE INTO sql_item_basic VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_equipment(con: sqlite3.Connection) -> int:
    # LSB carries scriptType/rslotlook/su_level extra columns -- confirmed against
    # build_lsb_index.py's load_item_equipment().
    cols = ["itemId", "name", "level", "ilevel", "jobs", "MId", "shieldSize", "scriptType",
             "slot", "rslot", "rslotlook", "su_level"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "item_equipment.sql"), "item_equipment", cols):
        rows.append((
            int(r["itemId"]), unquote(r["name"]), int(r["level"]), int(r["ilevel"]),
            int(r["jobs"]), int(r["shieldSize"]), int(r["slot"]), int(r["rslot"]),
        ))
    con.execute("DELETE FROM sql_item_equipment")
    con.executemany("INSERT OR REPLACE INTO sql_item_equipment VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_weapon(con: sqlite3.Connection) -> int:
    cols = ["itemId", "name", "skill", "subskill", "ilvl_skill", "ilvl_parry", "ilvl_macc",
            "dmgType", "hit", "delay", "dmg", "unlock_points"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "item_weapon.sql"), "item_weapon", cols):
        rows.append((
            int(r["itemId"]), unquote(r["name"]), int(r["skill"]), int(r["subskill"]),
            int(r["dmgType"]), int(r["delay"]), int(r["dmg"]),
        ))
    con.execute("DELETE FROM sql_item_weapon")
    con.executemany("INSERT OR REPLACE INTO sql_item_weapon VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_item_usable(con: sqlite3.Connection) -> int:
    # LSB's activation column is a REAL (float), not an int (confirmed against
    # build_lsb_index.py's load_item_usable()) -- sql_item_usable.activation is declared INTEGER in
    # this table's own schema below, so the float is stored via SQLite's normal type affinity
    # coercion rather than truncated in Python, matching how sqlite already handles this column.
    cols = ["itemid", "name", "validTargets", "activation", "animation", "animationTime",
            "maxCharges", "useDelay", "reuseDelay", "aoe"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "item_usable.sql"), "item_usable", cols):
        rows.append((
            int(r["itemid"]), unquote(r["name"]), int(r["validTargets"]), float(r["activation"]),
            int(r["animation"]), int(r["maxCharges"]), int(r["useDelay"]), int(r["reuseDelay"]), int(r["aoe"]),
        ))
    con.execute("DELETE FROM sql_item_usable")
    con.executemany("INSERT OR REPLACE INTO sql_item_usable VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_mob_skills(con: sqlite3.Connection) -> int:
    # LSB's own schema carries one extra column (mob_skill_aoe_radius) that Topaz's doesn't, and
    # mob_skill_flag is an @VAR expression -- confirmed against build_lsb_index.py's load_mob_skills().
    cols = ["mob_skill_id", "mob_anim_id", "mob_skill_name", "mob_skill_aoe", "mob_skill_aoe_radius",
            "mob_skill_distance", "mob_anim_time", "mob_prepare_time", "mob_valid_targets",
            "mob_skill_flag", "mob_skill_param", "knockback", "primary_sc", "secondary_sc", "tertiary_sc"]
    path = cleaned_path(SQL_DIR / "mob_skills.sql")
    variables = resolve_sql_vars(path)
    rows = []
    for r in parse_table_file(path, "mob_skills", cols):
        rows.append((
            int(r["mob_skill_id"]), int(r["mob_anim_id"]), unquote(r["mob_skill_name"]),
            int(r["mob_skill_aoe"]), float(r["mob_skill_distance"]), int(r["mob_anim_time"]),
            int(r["mob_prepare_time"]), int(r["mob_valid_targets"]),
            _resolve_field(r["mob_skill_flag"], variables),
        ))
    con.execute("DELETE FROM sql_mob_skills")
    con.executemany("INSERT OR REPLACE INTO sql_mob_skills VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_spell_list(con: sqlite3.Connection) -> int:
    # LSB's schema has one extra column ("radius", before content_tag) vs Topaz's, and uses
    # @ELEMENT_*/@SKILL_* SQL variables for the element/skill fields instead of raw ints --
    # confirmed against build_lsb_index.py's load_spell_list().
    cols = ["spellid", "name", "jobs", "group", "family", "element", "zonemisc", "validTargets",
            "skill", "mpCost", "castTime", "recastTime", "message", "magicBurstMessage",
            "animation", "animationTime", "AOE", "base", "multiplier", "CE", "VE",
            "requirements", "spell_range", "radius", "content_tag"]
    path = cleaned_path(SQL_DIR / "spell_list.sql")
    variables = resolve_sql_vars(path)
    rows = []
    for r in parse_table_file(path, "spell_list", cols):
        rows.append((
            int(r["spellid"]), unquote(r["name"]),
            _resolve_field(r["element"], variables), _resolve_field(r["skill"], variables),
            int(r["mpCost"]), int(r["castTime"]), int(r["recastTime"]),
        ))
    con.execute("DELETE FROM sql_spell_list")
    con.executemany("INSERT OR REPLACE INTO sql_spell_list VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_abilities(con: sqlite3.Connection) -> int:
    # LSB's schema has one extra column ("radius", right after isAOE) vs Topaz's -- confirmed
    # against build_lsb_index.py's load_abilities().
    cols = ["abilityId", "name", "job", "level", "validTarget", "recastTime", "recastId",
            "message1", "message2", "animation", "animationTime", "castTime", "actionType",
            "range", "isAOE", "radius", "CE", "VE", "meritModID", "addType", "content_tag"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "abilities.sql"), "abilities", cols):
        rows.append((
            int(r["abilityId"]), unquote(r["name"]), int(r["job"]), int(r["level"]),
            int(r["recastTime"]), int(r["recastId"]), int(r["animation"]),
        ))
    con.execute("DELETE FROM sql_abilities")
    con.executemany("INSERT OR REPLACE INTO sql_abilities VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_weapon_skills(con: sqlite3.Connection) -> int:
    # LSB has one extra column ("radius", right after aoe) vs Topaz's -- confirmed against
    # build_lsb_index.py's load_weapon_skills().
    cols = ["weaponskillid", "name", "jobs", "type", "skilllevel", "element", "animation",
            "animationTime", "range", "aoe", "radius", "primary_sc", "secondary_sc",
            "tertiary_sc", "main_only", "unlock_id"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "weapon_skills.sql"), "weapon_skills", cols):
        rows.append((int(r["weaponskillid"]), unquote(r["name"]), int(r["skilllevel"]), int(r["animation"])))
    con.execute("DELETE FROM sql_weapon_skills")
    con.executemany("INSERT OR REPLACE INTO sql_weapon_skills VALUES (?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_traits(con: sqlite3.Connection) -> int:
    # traitid repeats across many rows (one per job/level tier), but always maps to the same real
    # name -- so this is a real id-name enum despite the base table not being 1-row-per-id.
    cols = ["traitid", "name", "job", "level", "rank", "modifier", "value", "content_tag", "meritid"]
    seen = {}
    for r in parse_table_file(cleaned_path(SQL_DIR / "traits.sql"), "traits", cols):
        seen[int(r["traitid"])] = unquote(r["name"])
    con.execute("DELETE FROM sql_traits")
    con.executemany("INSERT OR REPLACE INTO sql_traits VALUES (?,?)", seen.items())
    con.commit()
    return len(seen)


def load_blue_spell_list(con: sqlite3.Connection) -> int:
    # LSB has two extra columns (tertiary_sc, knockback) after secondary_sc vs Topaz's -- confirmed
    # against build_lsb_index.py's load_blue_spell_list(). unquote() before int() handles both
    # Topaz's quote-everything style and LSB's plain-numeric style in one pass.
    cols = ["spellid", "mob_skill_id", "set_points", "trait_category", "trait_category_weight",
            "primary_sc", "secondary_sc", "tertiary_sc", "knockback"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "blue_spell_list.sql"), "blue_spell_list", cols):
        rows.append((int(unquote(r["spellid"])), int(unquote(r["mob_skill_id"]))))
    con.execute("DELETE FROM sql_blue_spell_list")
    con.executemany("INSERT OR REPLACE INTO sql_blue_spell_list VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def load_pet_list(con: sqlite3.Connection) -> int:
    # LSB has one extra column ("damageType") appended vs Topaz's -- confirmed against
    # build_lsb_index.py's load_pet_list().
    cols = ["petid", "name", "poolid", "minLevel", "maxLevel", "time", "element", "damageType"]
    rows = []
    for r in parse_table_file(cleaned_path(SQL_DIR / "pet_list.sql"), "pet_list", cols):
        rows.append((int(r["petid"]), unquote(r["name"]), int(r["poolid"])))
    con.execute("DELETE FROM sql_pet_list")
    con.executemany("INSERT OR REPLACE INTO sql_pet_list VALUES (?,?,?)", rows)
    con.commit()
    return len(rows)


def build_all(con: sqlite3.Connection):
    print(f"npc_list: {load_npc_list(con)} rows")
    print(f"mob_spawn_points: {load_mob_spawn_points(con)} rows")
    print(f"mob_groups: {load_mob_groups(con)} rows")
    print(f"mob_pools: {load_mob_pools(con)} rows")
    print(f"mob_droplist: {load_mob_droplist(con)} rows")
    print(f"instance_entities: {load_instance_entities(con)} rows")
    print(f"instance_list: {load_instance_list(con)} rows")
    print(f"item_basic: {load_item_basic(con)} rows")
    print(f"item_equipment: {load_item_equipment(con)} rows")
    print(f"item_weapon: {load_item_weapon(con)} rows")
    print(f"item_usable: {load_item_usable(con)} rows")
    print(f"mob_skills: {load_mob_skills(con)} rows")
    print(f"spell_list: {load_spell_list(con)} rows")
    print(f"abilities: {load_abilities(con)} rows")
    print(f"weapon_skills: {load_weapon_skills(con)} rows")
    print(f"traits: {load_traits(con)} rows")
    print(f"blue_spell_list: {load_blue_spell_list(con)} rows")
    print(f"pet_list: {load_pet_list(con)} rows")


def resolve_zoneid_for_report(con: sqlite3.Connection, zone_folder_name: str) -> int | None:
    row = con.execute("SELECT zoneid FROM zones WHERE name = ?", (zone_folder_name.upper(),)).fetchone()
    return row[0] if row else None


def query_zero_position(con: sqlite3.Connection, zoneid: int) -> list[tuple[int, str, str | None]]:
    """Returns [(npcid, name, content_tag), ...] -- real query logic, shared by the CLI report
    below and the GUI's own zero-position/unregistered browser page (no reimplementation)."""
    return con.execute("""
        SELECT n.npcid, n.name, n.content_tag FROM sql_npc_list n
        JOIN npc_names nn ON nn.npcid = n.npcid AND nn.zoneid = ?
        WHERE n.pos_x = 0 AND n.pos_y = 0 AND n.pos_z = 0
        ORDER BY n.npcid
    """, (zoneid,)).fetchall()


def query_unregistered(con: sqlite3.Connection, zoneid: int) -> list[tuple[int, str, str | None]]:
    """Returns [(npcid, name, content_tag), ...] -- same sharing note as query_zero_position."""
    return con.execute("""
        SELECT n.npcid, n.name, n.content_tag FROM sql_npc_list n
        JOIN npc_names nn ON nn.npcid = n.npcid AND nn.zoneid = ?
        WHERE NOT EXISTS (SELECT 1 FROM sql_instance_entities ie WHERE ie.id = n.npcid)
          AND NOT EXISTS (SELECT 1 FROM sql_mob_spawn_points msp WHERE msp.mobid = n.npcid)
        ORDER BY n.npcid
    """, (zoneid,)).fetchall()


def zero_position_report(con: sqlite3.Connection, zone_folder_name: str):
    zoneid = resolve_zoneid_for_report(con, zone_folder_name)
    if zoneid is None:
        print(f"Could not resolve zoneid for {zone_folder_name}")
        return
    rows = query_zero_position(con, zoneid)
    print(f"{len(rows)} zero-position npc_list row(s) in {zone_folder_name} (zoneid {zoneid}):")
    for npcid, name, tag in rows:
        tag_note = f"  [content_tag={tag}]" if tag else ""
        print(f"  {npcid}  {name!r}{tag_note}")


def unregistered_report(con: sqlite3.Connection, zone_folder_name: str):
    zoneid = resolve_zoneid_for_report(con, zone_folder_name)
    if zoneid is None:
        print(f"Could not resolve zoneid for {zone_folder_name}")
        return
    rows = query_unregistered(con, zoneid)
    print(f"{len(rows)} npc_list row(s) in {zone_folder_name} with no instance_entities or "
          f"mob_spawn_points registration (zoneid {zoneid}):")
    for npcid, name, tag in rows:
        tag_note = f"  [content_tag={tag}]" if tag else ""
        print(f"  {npcid}  {name!r}{tag_note}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zero-position", metavar="ZONE", help="Report zero-position npc_list rows in a zone")
    ap.add_argument("--unregistered", metavar="ZONE", help="Report unregistered npc_list rows in a zone")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    init_db(con)

    if not args.zero_position and not args.unregistered:
        build_all(con)
    if args.zero_position:
        zero_position_report(con, args.zero_position)
    if args.unregistered:
        unregistered_report(con, args.unregistered)

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
