#!/usr/bin/env python3
"""
lookup_entity.py -- Mission Toolkit GUI, Phase 2 scoped slice.

"Everything about entity X" in one command, instead of the multi-grep pattern used by hand all
session for every Nyzul/Assault question. Given an npc/mob id (or a name), reports:
  - real client name (from npc_names, built by build_npc_index.py)
  - every SQL row that references it, grouped by file/table (npc_list, mob_spawn_points,
    mob_groups, instance_entities, etc.)
  - every Lua script that references it, either by raw numeric id or by a named IDs.lua constant
    that resolves to it (zone's own IDs.lua is checked for a matching value)
  - whether it's registered in instance_entities.sql (the single most common gap found by hand
    this session -- an npc_list row with no instance registration)

Deliberately grep-based rather than a persisted SQL/Lua index: sql/'s ~100 files use enough
varied table shapes that a robust general parser is real, separate work; this answers the same
question live, correctly, today. A persisted indexer (per the Mission Toolkit GUI proposal,
Phase 2) is still worth building later for the position-plot/duplicate-key-detection features
that need it -- this tool does not replace that, it covers the lookup half now.

Usage:
    py -3 lookup_entity.py 17093430
    py -3 lookup_entity.py "Vending Box"
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


def resolve_query_to_ids(con: sqlite3.Connection, query: str, limit: int = 20, offset: int = 0) -> list[tuple[int, str, int]]:
    """Returns [(npcid, name, zoneid), ...] -- either the single exact id, or a page of name
    matches. limit/offset default to CLI-friendly values (one screenful); the GUI passes its own
    page size and uses count_name_matches() below for real pagination instead of this cap."""
    if query.isdigit():
        npcid = int(query)
        row = con.execute("SELECT name, zoneid FROM npc_names WHERE npcid = ?", (npcid,)).fetchone()
        return [(npcid, row[0], row[1])] if row else [(npcid, "(unknown -- not in npc_names index)", None)]
    # Real client names are wildly inconsistent in punctuation/spacing across entities -- confirmed
    # live that "Lamia No.13" (spaces + period, no underscore) and "Qiqirn_Treasure_Hunter" (all
    # underscores) are both real stored `name` values, so a raw-column search only ever matched
    # whichever exact style got extracted for that specific entity. norm_name (npc_names' own
    # normalized column, same normalize() as items_ours/lsb_* elsewhere) strips all spacing/
    # punctuation on both sides, so any typed variant converges to the same comparable string.
    from build_database import normalize
    norm_query = normalize(query)
    rows = con.execute(
        "SELECT npcid, name, zoneid FROM npc_names WHERE norm_name LIKE ? ORDER BY npcid LIMIT ? OFFSET ?",
        (f"%{norm_query}%", limit, offset),
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def count_name_matches(con: sqlite3.Connection, query: str) -> int:
    """Total real match count for a name search, for pagination (resolve_query_to_ids alone only
    returns one page and doesn't know the total). See resolve_query_to_ids' own comment on why
    this matches against norm_name, not the raw name column."""
    from build_database import normalize
    norm_query = normalize(query)
    return con.execute(
        "SELECT COUNT(*) FROM npc_names WHERE norm_name LIKE ?", (f"%{norm_query}%",)
    ).fetchone()[0]


def grep_sql(npcid: int) -> dict[str, list[str]]:
    """Searches every sql/*.sql (excluding sql/backups/, which is old snapshots not live data) for
    this id, grouped by filename. Pure Python (no external grep) -- Windows has no grep on PATH
    by default, and shelling out to it silently 500'd every entity-lookup page before this fix."""
    hits: dict[str, list[str]] = {}
    needle = str(npcid)
    sql_root = TOPAZ_ROOT / "sql"
    if not sql_root.is_dir():
        return hits
    for path in sql_root.rglob("*.sql"):
        if "backups" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            if needle in line:
                hits.setdefault(path.name, []).append(line.strip()[:160])
    return hits


# Real npc_list.sql schema, in order (see build_sql_index.py's own CREATE TABLE comment for the
# authoritative column list): npcid, name, polutils_name, pos_rot, pos_x, pos_y, pos_z, flag,
# speed, speedsub, animation, animationsub, namevis, status, entityFlags, look, name_prefix,
# content_tag, widescan. Captures every column, not just position/content_tag, so entity lookup
# can surface animation/entityFlags/status/etc. -- entityFlags in particular matters: bit 0x800
# is FLAG_UNTARGETABLE, the #1 repeat cause of "can't interact with X" found this session.
NPC_LIST_ROW_RE = re.compile(
    r"INSERT INTO `npc_list` VALUES \("
    r"\d+,'[^']*','[^']*',(\d+),"
    r"([\-\d.]+),([\-\d.]+),([\-\d.]+),"  # pos_rot, pos_x, pos_y, pos_z
    r"(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),"  # flag, speed, speedsub, animation, animationsub, namevis, status
    r"(\d+),0x([0-9A-Fa-f]+),(\d+),"  # entityFlags, look, name_prefix
    r"(NULL|'[^']*'),(\d+)\);"  # content_tag, widescan
)


def get_npc_list_row_detail(npcid: int) -> dict | None:
    """Parses this npcid's own npc_list.sql row for its full real column set -- none of these are
    stored in npc_names (that table only has id/name/zoneid). content_tag is a real server-side
    enable/disable flag for a whole content category (e.g. 'TOAU', 'SOA'), NOT proof an entity
    belongs to any specific mission using that zone -- Nyzul Isle in particular is shared by
    Assault, ToAU missions, and other battle content, so a tag match alone is never grounds to
    wire an entity into an Assault instance_entities row without real capture evidence (learned
    the hard way this session on the Moogle/Achieve_Master/_25x-prop sweep)."""
    npc_list_path = TOPAZ_ROOT / "sql/npc_list.sql"
    needle = f"VALUES ({npcid},"
    line = None
    if npc_list_path.exists():
        try:
            text = npc_list_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        for candidate in text.splitlines():
            if needle in candidate:
                line = candidate.strip()
                break
    if not line:
        return None
    m = NPC_LIST_ROW_RE.search(line)
    if not m:
        return None
    (pos_rot, pos_x, pos_y, pos_z, flag, speed, speedsub, animation, animationsub, namevis,
     status, entity_flags, look, name_prefix, content_tag, widescan) = m.groups()
    entity_flags_int = int(entity_flags)
    return {
        "pos": (float(pos_x), float(pos_y), float(pos_z)),
        "pos_rot": int(pos_rot),
        "flag": int(flag),
        "speed": int(speed),
        "speedsub": int(speedsub),
        "animation": int(animation),
        "animationsub": int(animationsub),
        "namevis": int(namevis),
        "status": int(status),
        "entity_flags": entity_flags_int,
        # FLAG_UNTARGETABLE = 0x800 -- confirmed the #1 repeat cause of "can't interact with X"
        # this session, but not always a bug (an entity can be deliberately hidden pre-reveal).
        "untargetable": bool(entity_flags_int & 0x800),
        "look": look,
        "name_prefix": int(name_prefix),
        "content_tag": None if content_tag == "NULL" else content_tag.strip("'"),
        "widescan": int(widescan),
    }


def get_mob_chain_detail(con: sqlite3.Connection, npcid: int, zoneid: int | None) -> dict | None:
    """If this id has a real mob_spawn_points row, follows spawn -> mob_groups -> mob_pools (via
    build_sql_index.py's already-parsed sql_* tables, not a fresh grep) for real level range,
    family id, respawn time, and pool name -- context npc_list alone doesn't carry.

    mob_groups' real primary key is (zoneid, groupid), NOT groupid alone -- groupid numbers are
    reused independently across different zones. A groupid-only lookup silently returns whichever
    zone's row happens to match first, which is a real, confirmed-live bug (found via 17002517,
    Lamia No. 13 in Ilrusi Atoll, resolving to a completely unrelated "fishtrap" pool from some
    other zone's same-numbered group). zoneid is required here specifically to prevent that."""
    spawn = con.execute(
        "SELECT groupid FROM sql_mob_spawn_points WHERE mobid = ?", (npcid,)
    ).fetchone()
    if not spawn:
        return None
    groupid = spawn[0]
    if zoneid is None:
        return {"groupid": groupid}
    group = con.execute(
        "SELECT poolid, name, respawntime, minLevel, maxLevel, dropid FROM sql_mob_groups "
        "WHERE groupid = ? AND zoneid = ?",
        (groupid, zoneid),
    ).fetchone()
    if not group:
        return {"groupid": groupid}
    poolid, group_name, respawntime, min_level, max_level, dropid = group
    pool = con.execute(
        "SELECT name, packet_name, familyid FROM sql_mob_pools WHERE poolid = ?", (poolid,)
    ).fetchone()
    detail = {
        "groupid": groupid, "poolid": poolid, "group_name": group_name,
        "respawntime": respawntime, "min_level": min_level, "max_level": max_level,
        "dropid": dropid,
    }
    if pool:
        detail.update({"pool_name": pool[0], "packet_name": pool[1], "familyid": pool[2]})
    return detail


def find_owning_zone_and_name(con: sqlite3.Connection, npcid: int) -> tuple[str | None, str | None]:
    row = con.execute("SELECT name FROM npc_names WHERE npcid = ?", (npcid,)).fetchone()
    if not row:
        return None, None
    real_name = row[0]
    # npc_list.name (the script-lookup key) usually strips spaces from the real display name --
    # confirmed convention across this session's own work (e.g. "Vending Box" -> "VendingBox").
    script_name_guess = real_name.replace(" ", "").replace("'", "")
    return script_name_guess, real_name


IDS_LUA_CONSTANT_RE_TEMPLATE = r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*{npcid}\s*,"


def zone_folder_name_guess(zname: str) -> str:
    """Best-effort ALL_CAPS zone constant -> Title_Case folder name (e.g. NYZUL_ISLE ->
    Nyzul_Isle, AHT_URHGAN_WHITEGATE -> Aht_Urhgan_Whitegate). Doesn't handle every real folder
    name (a few use hyphens, e.g. Dynamis-Windurst) -- find_ids_lua_constant just returns None
    gracefully if the guessed path doesn't exist, rather than needing this to be exhaustive."""
    return "_".join(w.capitalize() for w in zname.split("_"))


def find_ids_lua_constant(zone_folder_name: str, npcid: int) -> str | None:
    """Reverse-looks-up this npcid's own named constant in its zone's IDs.lua (e.g. 17093430 ->
    VENDING_BOX). Most Lua code -- instance files especially -- references an entity by this
    constant (ID.npc.VENDING_BOX), not the raw numeric id, so a plain grep for the number alone
    misses instance/mixin references entirely (confirmed live: grep_lua found IDs.lua and the
    npc's own script by name, but zero instance files, even though instances clearly do reference
    entities -- they just never spell out the raw id)."""
    ids_lua_path = TOPAZ_ROOT / "scripts/zones" / zone_folder_name / "IDs.lua"
    if not ids_lua_path.exists():
        return None
    text = ids_lua_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(IDS_LUA_CONSTANT_RE_TEMPLATE.format(npcid=npcid), text, re.M)
    return m.group(1) if m else None


def _lua_files_containing(root: Path, needle_re: "re.Pattern[str]") -> list[Path]:
    """Pure-Python replacement for `grep -rl --include=*.lua`: every .lua file under root whose
    contents match needle_re at least once."""
    if not root.is_dir():
        return []
    found = []
    for path in root.rglob("*.lua"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if needle_re.search(text):
            found.append(path)
    return found


def grep_lua(npcid: int, script_name_guess: str | None, zone_folder_name: str | None = None) -> dict[str, list[str]]:
    """Pure Python (no external grep/find) -- Windows has neither on PATH by default, and
    shelling out to them silently 500'd every entity-lookup page before this fix."""
    hits: dict[str, list[str]] = {}
    scripts_root = TOPAZ_ROOT / "scripts"
    id_re = re.compile(re.escape(str(npcid)))
    files = _lua_files_containing(scripts_root, id_re)

    # Also find the zone's own npc/mob script file by the guessed name, if any (this is the real
    # behavior script Topaz resolves via npc_list.name -- see topaz_npc_name_drives_script_lookup).
    if script_name_guess:
        zones_root = TOPAZ_ROOT / "scripts/zones"
        if zones_root.is_dir():
            target = f"{script_name_guess}.lua".lower()
            files += [p for p in zones_root.rglob("*.lua") if p.name.lower() == target]

    # Also search for the named IDs.lua constant, not just the raw numeric id -- this is what
    # instance files, mixins, and other cross-referencing scripts actually use. Scoped to this
    # zone's own directory (+ scripts/globals/, shared logic) rather than the whole scripts/
    # tree: constant names like RUNE_OF_RELEASE are reused independently per zone with a
    # different real id each time, so a tree-wide search pulls in unrelated zones' same-named,
    # different-valued constants (confirmed live: searching from Ilrusi Atoll's real
    # RUNE_OF_RELEASE also matched Mamool Ja's and Periqia's own separate constants of the
    # same name).
    constant_name = find_ids_lua_constant(zone_folder_name, npcid) if zone_folder_name else None
    if constant_name and zone_folder_name:
        const_re = re.compile(r"\b" + re.escape(constant_name) + r"\b")
        for search_root in (TOPAZ_ROOT / "scripts/zones" / zone_folder_name, TOPAZ_ROOT / "scripts/globals"):
            files += _lua_files_containing(search_root, const_re)

    for f in sorted(set(files)):
        hits[str(f.relative_to(TOPAZ_ROOT))] = []
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="An npc/mob id, or a name substring to search for")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    matches = resolve_query_to_ids(con, args.query)

    if not matches:
        print(f"No npc_names match for {args.query!r} -- try build_npc_index.py --all first, "
              f"or pass the numeric id directly if the zone isn't indexed yet.")
        return

    if len(matches) > 1:
        print(f"{len(matches)} name matches -- pass a specific id to drill into one:")
        for npcid, name, zoneid in matches:
            zname = con.execute("SELECT name FROM zones WHERE zoneid = ?", (zoneid,)).fetchone()
            zname = zname[0] if zname else "?"
            print(f"  {npcid}  {name!r}  ({zname})")
        return

    npcid, name, zoneid = matches[0]
    zname = None
    if zoneid is not None:
        row = con.execute("SELECT name FROM zones WHERE zoneid = ?", (zoneid,)).fetchone()
        zname = row[0] if row else None

    print(f"=== {npcid} ===")
    print(f"Real client name: {name!r}")
    if zname:
        print(f"Zone: {zname} ({zoneid})")

    detail = get_npc_list_row_detail(npcid)
    if detail:
        x, y, z = detail["pos"]
        pos_note = " (zero -- never positioned)" if (x, y, z) == (0.0, 0.0, 0.0) else ""
        print(f"Position: ({x}, {y}, {z}), rot={detail['pos_rot']}{pos_note}")
        print(f"animation={detail['animation']}  animationsub={detail['animationsub']}  "
              f"status={detail['status']}  speed={detail['speed']}/{detail['speedsub']}  "
              f"flag={detail['flag']}  namevis={detail['namevis']}  widescan={detail['widescan']}")
        print(f"entityFlags={detail['entity_flags']} (0x{detail['entity_flags']:X})"
              + ("  [!] FLAG_UNTARGETABLE set" if detail["untargetable"] else ""))
        print(f"look={detail['look']}  name_prefix={detail['name_prefix']}")
        if detail["content_tag"]:
            print(f"content_tag: {detail['content_tag']!r} -- a server-side content-category "
                  f"enable/disable flag, NOT proof this entity belongs to any specific mission "
                  f"in a shared zone. Do not wire this into an Assault instance without real "
                  f"capture evidence, especially in zones used by multiple content types "
                  f"(e.g. Nyzul Isle).")

    mob_chain = get_mob_chain_detail(con, npcid, zoneid)
    if mob_chain:
        print(f"Mob group {mob_chain.get('groupid')}: {mob_chain.get('group_name')}  "
              f"level {mob_chain.get('min_level')}-{mob_chain.get('max_level')}  "
              f"respawn {mob_chain.get('respawntime')}s")
        if "pool_name" in mob_chain:
            print(f"  pool {mob_chain['poolid']}: {mob_chain['pool_name']} "
                  f"(family {mob_chain['familyid']}, packet name {mob_chain['packet_name']!r})")

    script_name_guess, _ = find_owning_zone_and_name(con, npcid)
    if script_name_guess:
        print(f"Likely script filename: {script_name_guess}.lua")

    print("\nSQL references:")
    sql_hits = grep_sql(npcid)
    if not sql_hits:
        print("  (none found)")
    tag_suffix = f"  [content_tag={detail['content_tag']}]" if detail and detail["content_tag"] else ""
    for fname, lines in sql_hits.items():
        print(f"  {fname}: {len(lines)} row(s){tag_suffix}")
        for line in lines[:2]:
            print(f"    {line}")

    in_instance_entities = "instance_entities.sql" in sql_hits
    in_npc_or_mob_spawn = "npc_list.sql" in sql_hits or "mob_spawn_points.sql" in sql_hits
    if in_npc_or_mob_spawn and not in_instance_entities:
        print("  [!] Registered in npc_list/mob_spawn_points but NOT in instance_entities.sql --")
        print("      this is the single most common gap found by hand this session.")

    print("\nLua references:")
    zone_folder = zone_folder_name_guess(zname) if zname else None
    lua_hits = grep_lua(npcid, script_name_guess, zone_folder)
    if not lua_hits:
        print("  (none found)")
    for fname in lua_hits:
        print(f"  {fname}")

    con.close()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
