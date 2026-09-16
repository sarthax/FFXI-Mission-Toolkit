"""
backport_sql_convert.py -- Topaz -> DSP SQL row conversion for the backport module, plus two real
checks against DSP's actual indexed data (via ffxi_zone_database.db's dsp_* tables built by
build_dsp_index.py), not just a hand-diff of two dump files:

  - check_id_collisions(): does a candidate numeric id already exist in DSP?
  - check_content_duplication(): for tables whose real-world identity is a composite key wider
    than the id column (e.g. mob_groups: a "group" is really identified by (poolid, zoneid), not
    groupid alone -- groupid is just DSP's storage-level PK), does DSP already have a DIFFERENT
    id covering the SAME real content?

Added 2026-09-15 after a real incident (see D:\\Claude\\Topaz-Assault-Backport\\reports\\
dsp_repair_2026-09-15\\INCIDENT_REPORT.md): multiple backport passes, run at different times, each
minted a FRESH groupid for mob_groups content that a prior pass had already backported. Every pass
used a numeric range that was genuinely free, so check_id_collisions() alone reported "no
collision" every single time -- it structurally cannot catch "this content already exists under a
different id," only "this exact id is taken." 195 live mob_groups rows ended up silently pulling
wrong loot as a result (the live-wired duplicate used a raw, unconverted dropid that collided with
unrelated DSP-native content, while the correctly-remapped duplicate from an earlier pass sat
orphaned with zero spawns). check_content_duplication() closes that gap.

Mirrors backport_lua_convert.py's design/discipline: every schema mapping in
data/dsp_sql_schema_map.json is checked against the real CREATE TABLE in both C:\\topaz\\sql and
D:\\Claude\\old-dsp-reference\\sql (or whatever dsp_server_path points at) -- never guessed. This
module does NOT try to auto-resolve a real primary-key collision (e.g. mob_groups' groupid space
going from per-zone to server-global) -- it reports one so a human can pick a new safe id range,
the same "flag, don't guess" discipline the Lua converter uses for anything not fully confirmed.
Likewise, check_content_duplication() never auto-picks which duplicate to keep -- see the incident
report for real examples of content-key matches that turned out to be legitimate (e.g. the same
poolid spawning under different in-world names at different positions within the same zone, a
real, common FFXI pattern -- not every (poolid, zoneid) match is a bug).

Usage (library):
    import backport_sql_convert as bsc
    schema_map = bsc.load_schema_map()
    rows = bsc.parse_insert_values(sql_text)
    result = bsc.convert_table(table_name, rows, schema_map)
    collisions = bsc.check_id_collisions(con, table_name, result.converted_ids, schema_map)
    dupes = bsc.check_content_duplication(con, table_name, rows, schema_map)
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

MAP_PATH = Path(__file__).resolve().parent / "data" / "dsp_sql_schema_map.json"

# DSP table this Topaz table's collision check should query, and the column in that table holding
# the id. Kept separate from the schema map's own "id_column" (which is the TOPAZ/DSP shared name)
# since the indexed dsp_* table name has its own "dsp_" prefix convention.
DSP_INDEX_TABLE = {
    "npc_list": "dsp_npc_list",
    "mob_pools": "dsp_mob_pools",
    "mob_droplist": "dsp_mob_droplist",
    "mob_spawn_points": "dsp_mob_spawn_points",
    "instance_entities": "dsp_instance_entities",
    "instance_list": "dsp_instance_list",
    "mob_groups": "dsp_mob_groups",
    "mob_skills": "dsp_mob_skills",
    # mob_skill_lists has no indexed dsp_* table (not built by build_dsp_index.py) -- its
    # collision check reads old-dsp-reference's real sql/mob_skill_lists.sql directly instead,
    # see dsp_sql_schema_map.json's mob_skill_lists entry.
}

# Tables whose real-world identity is a composite key wider than their id column -- i.e. where
# check_id_collisions() checking the id column alone ("groupid") isn't enough, because two
# DIFFERENT groupids can legitimately (or, per the 2026-09-15 incident, illegitimately) both claim
# to represent the SAME real content. Maps Topaz table -> tuple of Topaz column names (must exist
# in that table's schema_map "topaz_columns") forming that real-world content key. Only add a table
# here once you've confirmed what actually identifies "the same content" for it -- for mob_groups
# this is confirmed via dsp_sql_schema_map.json's own primary_key_topaz note (composite
# (zoneid, groupid) in Topaz, bare groupid in DSP -- poolid+zoneid is what a human would call "the
# same spawn group", not groupid, which is just DSP's storage-level identity for it).
CONTENT_KEY_COLUMNS = {
    "mob_groups": ("poolid", "zoneid"),
}


def load_schema_map() -> dict:
    import json
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


_INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+`?(\w+)`?\s*(?:\([^)]*\)\s*)?VALUES\s*(.+?);",
    re.IGNORECASE | re.DOTALL,
)


def _split_top_level_tuples(values_blob: str) -> list[str]:
    """Split a `(...), (...), (...)` blob into each parenthesized tuple's raw inner text, correctly
    skipping over commas inside quoted strings or nested parens (e.g. a hex literal or a quoted
    string containing a comma)."""
    tuples = []
    depth = 0
    in_string = False
    string_char = ""
    start = None
    for i, ch in enumerate(values_blob):
        if in_string:
            if ch == string_char and values_blob[i - 1:i] != "\\":
                in_string = False
            continue
        if ch in ("'", '"'):
            in_string = True
            string_char = ch
            continue
        if ch == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start is not None:
                tuples.append(values_blob[start:i])
                start = None
    return tuples


def _split_tuple_fields(tuple_text: str) -> list[str]:
    """Split one tuple's raw text on top-level commas (not inside a quoted string), stripping outer
    whitespace and one layer of matching quotes from each field. Values stay as raw strings (may be
    numeric literals, quoted strings, or a 0x... hex literal) -- callers that need typed values
    should convert per-column using the schema map's knowledge of that column's type."""
    fields = []
    depth = 0
    in_string = False
    string_char = ""
    current = []
    for i, ch in enumerate(tuple_text):
        if in_string:
            current.append(ch)
            if ch == string_char and tuple_text[i - 1:i] != "\\":
                in_string = False
            continue
        if ch in ("'", '"'):
            in_string = True
            string_char = ch
            current.append(ch)
            continue
        if ch in "([":
            depth += 1
            current.append(ch)
        elif ch in ")]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            fields.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        fields.append("".join(current).strip())
    return fields


def _strip_sql_line_comments(sql_text: str) -> str:
    """Drop any `-- ...` line comment, so a commented-out INSERT (real dumps do this for known-bad/
    disabled rows, e.g. old-dsp-reference's mob_skill_lists.sql has several `-- INSERT INTO ...`
    lines with a literal `?` placeholder value) never gets parsed as real data. Only strips a `--`
    that starts a line (after optional leading whitespace) or follows a `;` -- a `--` inside a
    quoted string literal is left alone (real dump data can contain a name like "Puk's Lantern",
    though not "--", but this is deliberately conservative rather than a full SQL tokenizer)."""
    return re.sub(r"(?m)^[ \t]*--[^\n]*$", "", sql_text)


def parse_insert_values(sql_text: str) -> list[tuple[str, list[str]]]:
    """Parse every `INSERT INTO <table> [(...)] VALUES (...), (...), ...;` statement in sql_text.
    Returns a list of (table_name, field_values) per row, preserving statement order. field_values
    are raw text (not type-converted) -- e.g. "17092609", "'Armoury_Crate'",
    "0x0000320000000000000000000000000000000000". Commented-out `-- INSERT ...` lines are skipped."""
    sql_text = _strip_sql_line_comments(sql_text)
    out: list[tuple[str, list[str]]] = []
    for m in _INSERT_RE.finditer(sql_text):
        table, values_blob = m.group(1), m.group(2)
        for tup in _split_top_level_tuples(values_blob):
            out.append((table, _split_tuple_fields(tup)))
    return out


def _unquote(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1].replace("\\'", "'").replace('\\"', '"')
    return v


@dataclass
class SqlConversionResult:
    converted_sql: str
    warnings: list[dict] = field(default_factory=list)
    converted_ids: list[str] = field(default_factory=list)  # raw text of the id column per row
    id_to_name: dict[int, str] = field(default_factory=dict)  # numeric id -> Topaz name, for collision classification


def convert_table(table: str, rows: list[list[str]], schema_map: dict) -> SqlConversionResult:
    """Convert a list of Topaz-shaped field-value rows (already split by parse_insert_values, all
    for the SAME table) into DSP-shaped INSERT statements. Reorders/drops columns per the schema
    map; never invents a value for a column DSP requires that isn't confirmed derivable from the
    Topaz row -- those are flagged as warnings instead."""
    spec = schema_map.get(table)
    if spec is None:
        return SqlConversionResult(
            converted_sql=f"-- SQL-PORT-TODO: no schema mapping for table `{table}` in "
                          f"data/dsp_sql_schema_map.json -- add one (check both real CREATE TABLE "
                          f"statements) before converting this table.\n",
            warnings=[{"table": table, "reason": "no schema mapping"}],
        )

    topaz_cols = spec["topaz_columns"]
    dsp_cols = spec["dsp_columns"]
    dropped = set(spec.get("dropped_from_topaz", []))
    added = spec.get("added_by_dsp", [])
    id_col = spec.get("id_column")
    id_idx = topaz_cols.index(id_col) if id_col and id_col in topaz_cols else None
    name_col = spec.get("name_column")
    name_idx = topaz_cols.index(name_col) if name_col and name_col in topaz_cols else None

    warnings: list[dict] = []
    if dropped:
        warnings.append({
            "table": table, "reason": f"columns dropped (Topaz has them, DSP has no slot): {sorted(dropped)}",
            "detail": spec.get("evidence", ""),
        })
    if added:
        warnings.append({
            "table": table, "reason": f"columns DSP requires that aren't in Topaz's row: {added}",
            "detail": "No confirmed default -- fill these in by hand before using this output.",
        })
    if spec.get("warning"):
        warnings.append({"table": table, "reason": spec["warning"], "detail": spec.get("evidence", "")})

    lines = [f"-- Converted from Topaz `{table}` to DSP's real column order/shape."]
    if warnings:
        lines.append(f"-- SQL-PORT-TODO: see warnings below -- {len(warnings)} item(s) need review.")
    lines.append("")

    converted_ids: list[str] = []
    id_to_name: dict[int, str] = {}
    for row in rows:
        if len(row) != len(topaz_cols):
            warnings.append({
                "table": table,
                "reason": f"row has {len(row)} fields, expected {len(topaz_cols)} for Topaz's schema -- skipped",
                "detail": " ".join(row),
            })
            continue
        by_col = dict(zip(topaz_cols, row))
        dsp_values = []
        for col in dsp_cols:
            if col in by_col:
                dsp_values.append(by_col[col])
            else:
                dsp_values.append("/* SQL-PORT-TODO: no confirmed value for column '" + col + "' */ 0")
        lines.append(f"INSERT INTO `{table}` (`{'`, `'.join(dsp_cols)}`) VALUES ({', '.join(dsp_values)});")
        if id_idx is not None:
            converted_ids.append(row[id_idx])
            if name_idx is not None:
                try:
                    id_to_name[int(_unquote(row[id_idx]))] = _unquote(row[name_idx])
                except ValueError:
                    pass

    return SqlConversionResult(converted_sql="\n".join(lines) + "\n", warnings=warnings,
                                converted_ids=converted_ids, id_to_name=id_to_name)


def check_id_collisions(con: sqlite3.Connection, table: str, ids: list[str], schema_map: dict,
                         id_to_name: dict[int, str] | None = None) -> dict:
    """Check a list of (raw text, possibly quoted) ids against DSP's REAL, already-indexed data
    (ffxi_zone_database.db's dsp_* tables from build_dsp_index.py) for the given Topaz table name.

    When id_to_name is given (Topaz id -> Topaz name for that row) and the indexed DSP table has a
    'name' column, every colliding id is further classified:
      - "same_entity": DSP already has a row at this id with the SAME name -- not a real problem,
        this entity already exists in DSP (may still need position/flag reconciliation, but it's
        not an id-space conflict).
      - "name_mismatch": DSP has a DIFFERENT name at this id -- a REAL collision. Since a Lua
        script's onTrigger lookup is keyed by the entity's real `name` field (see
        [[topaz_npc_name_drives_script_lookup]] memory), this needs a human decision: rename the
        DSP row to match Topaz's name, or move this package's entity to a different free id --
        never guessed automatically.

    Returns {"checked_table", "id_column", "same_entity": [...], "name_mismatch": [...],
    "unclassified": [...] (collided but no name available to compare), "note"}.
    """
    spec = schema_map.get(table, {})
    id_col = spec.get("id_column")
    dsp_table = DSP_INDEX_TABLE.get(table)
    if not id_col or not dsp_table:
        return {"checked_table": dsp_table, "id_column": id_col, "same_entity": [],
                "name_mismatch": [], "unclassified": [],
                "note": f"No id-collision check defined for table `{table}` (either no id_column "
                        f"or no indexed dsp_* table for it)."}

    clean_ids: list[int] = []
    for raw in ids:
        v = _unquote(raw)
        try:
            clean_ids.append(int(v))
        except ValueError:
            continue
    distinct_ids = sorted(set(clean_ids))

    if not clean_ids:
        return {"checked_table": dsp_table, "id_column": id_col, "same_entity": [],
                "name_mismatch": [], "unclassified": [], "note": "No numeric ids to check."}

    placeholders = ",".join("?" * len(distinct_ids))
    # Use index_name_column when the indexed snapshot table (built by build_dsp_index.py) renamed
    # the name column from its real raw-SQL spelling (e.g. mob_skills' mob_skill_name -> name) --
    # falls back to name_column when the two already match.
    name_col = spec.get("index_name_column") or spec.get("name_column")
    has_name_col = False
    try:
        if name_col:
            cur = con.execute(f"PRAGMA table_info({dsp_table})")
            has_name_col = any(r[1] == name_col for r in cur.fetchall())
        select_cols = f"DISTINCT {id_col}, {name_col}" if has_name_col else f"DISTINCT {id_col}"
        cur = con.execute(f"SELECT {select_cols} FROM {dsp_table} WHERE {id_col} IN ({placeholders})", distinct_ids)
        dsp_rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        return {"checked_table": dsp_table, "id_column": id_col, "same_entity": [],
                "name_mismatch": [], "unclassified": [],
                "note": f"Could not query {dsp_table}.{id_col}: {e} -- has build_dsp_index.py been run?"}

    # A table without a unique id (e.g. mob_droplist's dropId, one id groups many item rows) can
    # still return >1 row per id even with DISTINCT if it also selected a non-unique name column --
    # dedupe by id itself, keeping the first name seen, so each colliding id is classified exactly
    # once rather than once per underlying row.
    seen_ids: dict = {}
    for row in dsp_rows:
        seen_ids.setdefault(row[0], row)
    dsp_rows = list(seen_ids.values())

    same_entity, name_mismatch, unclassified = [], [], []
    for row in dsp_rows:
        cid = row[0]
        dsp_name = row[1] if has_name_col and len(row) > 1 else None
        topaz_name = (id_to_name or {}).get(cid)
        if dsp_name is not None and topaz_name is not None:
            if str(dsp_name) == str(topaz_name):
                same_entity.append({"id": cid, "name": dsp_name})
            else:
                name_mismatch.append({"id": cid, "dsp_name": dsp_name, "topaz_name": topaz_name})
        else:
            unclassified.append({"id": cid, "dsp_name": dsp_name})

    total_collisions = len(same_entity) + len(name_mismatch) + len(unclassified)
    note = f"{total_collisions} of {len(distinct_ids)} distinct id(s) already exist in DSP's real {dsp_table}.{id_col}."
    if name_mismatch:
        note += f" {len(name_mismatch)} are REAL collisions (different entity already at that id)."
    if same_entity:
        note += f" {len(same_entity)} are the same entity already present (safe)."
    if not total_collisions:
        note = f"None of the {len(distinct_ids)} distinct id(s) checked collide with DSP's real {dsp_table}.{id_col}."

    return {
        "checked_table": dsp_table, "id_column": id_col, "checked_count": len(distinct_ids),
        "same_entity": same_entity, "name_mismatch": name_mismatch, "unclassified": unclassified,
        "note": note,
    }


def check_content_duplication(con: sqlite3.Connection, table: str, rows: list[list[str]],
                               schema_map: dict) -> dict:
    """Check whether DSP already has an existing row covering the SAME real-world content as each
    candidate row, keyed by CONTENT_KEY_COLUMNS (e.g. mob_groups' (poolid, zoneid)) rather than by
    id -- catches the class of bug check_id_collisions() cannot: a fresh, genuinely-unused id
    minted for content a prior backport pass already inserted under a DIFFERENT id.

    `rows` is the same Topaz-shaped field-value row list convert_table() takes (one list of raw
    field strings per row, all for the SAME table) -- this function needs the content-key columns
    together per row, not a pre-flattened id list.

    Returns {"checked_table", "content_key_columns", "checked_count", "duplicates": [...],
    "note"}. Each duplicate entry is {"content_key": {...}, "candidate_id": <this row's id>,
    "existing": [{"id": ..., <other indexed columns>...}, ...]} -- one or more existing DSP rows
    already at that content key. This function does NOT classify further (e.g. which existing row
    has live spawns, whether it's a real collision or a legitimate same-poolid-different-name
    variant per the incident report) -- that needs the real live DB (mob_spawn_points join), which
    this offline indexed snapshot doesn't carry in a form safe to assume is current. Use
    backport_sql_live_check.py for that live classification before deciding anything.
    """
    key_cols = CONTENT_KEY_COLUMNS.get(table)
    spec = schema_map.get(table, {})
    topaz_cols = spec.get("topaz_columns", [])
    id_col = spec.get("id_column")
    dsp_table = DSP_INDEX_TABLE.get(table)

    if not key_cols:
        return {"checked_table": dsp_table, "content_key_columns": None, "checked_count": 0,
                "duplicates": [],
                "note": f"No content-key columns defined for table `{table}` in "
                        f"CONTENT_KEY_COLUMNS -- either this table's real identity IS its id "
                        f"column (no composite-key risk), or this hasn't been confirmed/added yet."}
    if not dsp_table:
        return {"checked_table": dsp_table, "content_key_columns": key_cols, "checked_count": 0,
                "duplicates": [], "note": f"No indexed dsp_* table for `{table}`."}
    missing = [c for c in (*key_cols, id_col) if c not in topaz_cols]
    if missing:
        return {"checked_table": dsp_table, "content_key_columns": key_cols, "checked_count": 0,
                "duplicates": [],
                "note": f"Schema map for `{table}` is missing column(s) {missing} needed for this "
                        f"check -- fix data/dsp_sql_schema_map.json first."}

    key_idx = [topaz_cols.index(c) for c in key_cols]
    id_idx = topaz_cols.index(id_col)

    try:
        cur = con.execute(f"PRAGMA table_info({dsp_table})")
        dsp_cols = [r[1] for r in cur.fetchall()]
    except sqlite3.OperationalError as e:
        return {"checked_table": dsp_table, "content_key_columns": key_cols, "checked_count": 0,
                "duplicates": [], "note": f"Could not read {dsp_table}'s columns: {e}"}
    if not all(c in dsp_cols for c in key_cols):
        return {"checked_table": dsp_table, "content_key_columns": key_cols, "checked_count": 0,
                "duplicates": [],
                "note": f"Indexed table {dsp_table} doesn't have column(s) {key_cols} -- rebuild "
                        f"the index (build_dsp_index.py) or check its column names."}

    checked = 0
    seen_keys: set[tuple] = set()
    duplicates: list[dict] = []
    for row in rows:
        if len(row) != len(topaz_cols):
            continue
        try:
            key_vals = tuple(int(_unquote(row[i])) for i in key_idx)
            candidate_id = int(_unquote(row[id_idx]))
        except ValueError:
            continue
        if key_vals in seen_keys:
            continue  # only report each distinct content key once, even if the candidate batch repeats it
        seen_keys.add(key_vals)
        checked += 1

        where = " AND ".join(f"{c} = ?" for c in key_cols)
        select_cols = ", ".join(dsp_cols)
        cur = con.execute(f"SELECT {select_cols} FROM {dsp_table} WHERE {where}", key_vals)
        existing_rows = cur.fetchall()
        if not existing_rows:
            continue
        duplicates.append({
            "content_key": dict(zip(key_cols, key_vals)),
            "candidate_id": candidate_id,
            "existing": [dict(zip(dsp_cols, r)) for r in existing_rows],
        })

    note = (f"{len(duplicates)} of {checked} distinct content key(s) checked already have an "
            f"existing DSP row under a DIFFERENT id -- review each one (see backport_sql_live_check.py "
            f"for live spawn/loot classification before deciding whether to reuse or keep both).")
    if not duplicates:
        note = f"None of the {checked} distinct content key(s) checked already exist in DSP."

    return {
        "checked_table": dsp_table, "content_key_columns": key_cols, "checked_count": checked,
        "duplicates": duplicates, "note": note,
    }
