#!/usr/bin/env python3
"""Development entity lookup service and CLI implementation.

Canonical home for the historical entity lookup tool. The retired root filename is no longer
part of the supported import/CLI surface.
"""
import argparse
import io
import re
import sqlite3
import sys
from pathlib import Path

from workbench.runtime import legacy_settings as settings
from workbench.runtime.paths import DATABASE_PATH

# The user's active server (Topaz or DSP), not necessarily Topaz.
TOPAZ_ROOT = settings.get_active_server_root()
DB_PATH = DATABASE_PATH


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def resolve_query_to_ids(con: sqlite3.Connection, query: str, limit: int = 20, offset: int = 0) -> list[tuple[int, str, int]]:
    """Returns [(npcid, name, zoneid), ...] for an id or normalized name search."""
    if query.isdigit():
        npcid = int(query)
        row = con.execute("SELECT name, zoneid FROM npc_names WHERE npcid = ?", (npcid,)).fetchone()
        return [(npcid, row[0], row[1])] if row else [(npcid, "(unknown -- not in npc_names index)", None)]
    norm_query = _normalize_name(query)
    rows = con.execute(
        "SELECT npcid, name, zoneid FROM npc_names WHERE norm_name LIKE ? ORDER BY npcid LIMIT ? OFFSET ?",
        (f"%{norm_query}%", limit, offset),
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def count_name_matches(con: sqlite3.Connection, query: str) -> int:
    norm_query = _normalize_name(query)
    return con.execute(
        "SELECT COUNT(*) FROM npc_names WHERE norm_name LIKE ?", (f"%{norm_query}%",)
    ).fetchone()[0]


def grep_sql(npcid: int) -> dict[str, list[str]]:
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


NPC_LIST_ROW_RE = re.compile(
    r"INSERT INTO `npc_list` VALUES \("
    r"\d+,'[^']*','[^']*',(\d+),"
    r"([\-\d.]+),([\-\d.]+),([\-\d.]+),"
    r"(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),"
    r"(\d+),0x([0-9A-Fa-f]+),(\d+),"
    r"(NULL|'[^']*'),(\d+)\);"
)


def get_npc_list_row_detail(npcid: int) -> dict | None:
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
        "untargetable": bool(entity_flags_int & 0x800),
        "look": look,
        "name_prefix": int(name_prefix),
        "content_tag": None if content_tag == "NULL" else content_tag.strip("'"),
        "widescan": int(widescan),
    }


def get_mob_chain_detail(con: sqlite3.Connection, npcid: int, zoneid: int | None) -> dict | None:
    _sqlp = settings.get_active_sql_prefix()
    pn = "packet_name" if "packet_name" in {r[1] for r in con.execute(f"PRAGMA table_info({_sqlp}mob_pools)")} else "name"
    spawn = con.execute(
        f"SELECT groupid FROM {_sqlp}mob_spawn_points WHERE mobid = ?", (npcid,)
    ).fetchone()
    if not spawn:
        return None
    groupid = spawn[0]
    if zoneid is None:
        return {"groupid": groupid}
    group = con.execute(
        f"SELECT poolid, name, respawntime, minLevel, maxLevel, dropid FROM {_sqlp}mob_groups "
        "WHERE groupid = ? AND zoneid = ?",
        (groupid, zoneid),
    ).fetchone()
    if not group:
        return {"groupid": groupid}
    poolid, group_name, respawntime, min_level, max_level, dropid = group
    pool = con.execute(
        f"SELECT name, {pn}, familyid FROM {_sqlp}mob_pools WHERE poolid = ?", (poolid,)
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
    script_name_guess = real_name.replace(" ", "").replace("'", "")
    return script_name_guess, real_name


IDS_LUA_CONSTANT_RE_TEMPLATE = r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*{npcid}\s*,"


def zone_folder_name_guess(zname: str) -> str:
    return "_".join(w.capitalize() for w in zname.split("_"))


def find_ids_lua_constant(zone_folder_name: str, npcid: int) -> str | None:
    ids_lua_path = TOPAZ_ROOT / "scripts/zones" / zone_folder_name / "IDs.lua"
    if not ids_lua_path.exists():
        return None
    text = ids_lua_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(IDS_LUA_CONSTANT_RE_TEMPLATE.format(npcid=npcid), text, re.M)
    return m.group(1) if m else None


def _lua_files_containing(root: Path, needle_re: "re.Pattern[str]") -> list[Path]:
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
    hits: dict[str, list[str]] = {}
    scripts_root = TOPAZ_ROOT / "scripts"
    id_re = re.compile(re.escape(str(npcid)))
    files = _lua_files_containing(scripts_root, id_re)

    if script_name_guess:
        zones_root = TOPAZ_ROOT / "scripts/zones"
        if zones_root.is_dir():
            target = f"{script_name_guess}.lua".lower()
            files += [p for p in zones_root.rglob("*.lua") if p.name.lower() == target]

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
