#!/usr/bin/env python3
"""
llm_db_tools.py -- a small, strictly READ-ONLY set of tools an LLM can call (via the
prompt-based tool-call loop in gui_server.py's "Allow read-only DB tool access" option) to query
mission_toolkit's own indexed SQLite database on demand, instead of a human having to pre-fetch
and paste in exactly the right rows every time.

Every tool here is physically incapable of writing: each connection is opened in SQLite's own
`mode=ro` URI mode -- enforced by the SQLite engine itself, not just by string-checking the query
text (that check also exists in query_sql() below, as defense in depth, but the real guarantee is
the read-only connection). This is intentionally the ONLY way an LLM gets DB access anywhere in
this toolkit -- never wire a write-capable connection into anything a model can trigger. Matches
the project's standing rule (see llm_client.py's own docstring): an LLM response is always a
draft a human verifies, never something that acts on its own.

Why a prompt-based tool-call protocol instead of the OpenAI-style `tools`/`tool_calls` API field:
verified live against this project's real local Open WebUI/Ollama setup (2026-09-14) that the
formal tool_calls round-trip doesn't actually work here -- the model emits a tool-call-shaped
response as plain text in `message.content` (not the structured `tool_calls` field), and a
followup `role: "tool"` message doesn't get a coherent response back (no `tool_call_id` to link
it to, since the model never produced a real tool_calls entry with one). A plain prompt-based
protocol -- ask the model to respond with a bare `{"tool": ..., "args": {...}}` JSON object, then
feed the real tool result back as a normal message and continue -- was verified live to work
end-to-end with the same model. Simpler and, in this environment, more reliable than the "real"
API.
"""
from __future__ import annotations

import json
import re
import sqlite3

import settings

MAX_ROWS = 50
MAX_RESULT_CHARS = 6000

_SELECT_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(
    r"\b(ATTACH|DETACH|PRAGMA|VACUUM|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|INTO)\b",
    re.IGNORECASE,
)


def _readonly_connection() -> sqlite3.Connection:
    """Opened with mode=ro -- SQLite itself refuses any write against this connection, regardless
    of what query text gets past the string checks in query_sql() below."""
    con = sqlite3.connect(f"file:{settings.DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def list_tables(**_ignored) -> dict:
    """Real table names + row counts -- lets a model discover the schema before querying it,
    rather than guessing table names."""
    con = _readonly_connection()
    try:
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()]
        counts = {}
        for t in tables:
            try:
                counts[t] = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except sqlite3.Error:
                counts[t] = None
        return {"tables": counts}
    finally:
        con.close()


# Hand-curated, evidence-checked real foreign-key-shaped relationships between this toolkit's
# indexed tables. Every entry here was verified live (2026-09-14) by actually running the join
# and confirming a real, near-total match rate against the live database -- NONE of these are
# inferred from column-name pattern-matching alone (a real project rule: this codebase's own
# id_drift/backport work has repeatedly found that a plausible-looking name match is not the same
# as a confirmed real relationship). Written prefix-agnostic (bare table names, e.g. "mob_groups"
# not "dsp_mob_groups") since the same real shape/relationship holds across this toolkit's four
# parallel data-source prefixes (dsp_/lsb_/topaz_/sql_) -- confirmed identical column shapes for
# mob_groups/mob_droplist across all four before relying on that. _relationships_for() below
# re-applies whichever prefix the caller actually asked about.
RELATIONSHIPS = [
    {"from": "mob_groups.dropid", "to": "mob_droplist.dropid",
     "note": "A mob group's real drop table (verified: 38129/38129 dsp_mob_groups rows have a matching dropid)."},
    {"from": "mob_droplist.itemId", "to": "item_basic.itemid",
     "note": "The item a drop-table row actually drops (verified: 32872/32873 dsp rows match)."},
    {"from": "mob_groups.poolid", "to": "mob_pools.poolid",
     "note": "Which mob TYPE a group spawns (verified: 12148/12149 dsp rows match)."},
    {"from": "mob_groups.zoneid", "to": "zones.zoneid",
     "note": "Verified: 12149/12149 dsp_mob_groups rows match a real zone."},
    {"from": "mob_spawn_points.groupid", "to": "mob_groups.groupid",
     "note": "Which group a spawn point belongs to -- groupid is globally unique (not per-zone), "
             "verified: 12149 dsp_mob_groups rows all have distinct groupid values, and "
             "62074/68287 dsp_mob_spawn_points rows match one."},
    {"from": "pet_list.poolid", "to": "mob_pools.poolid",
     "note": "Verified: 73/73 dsp_pet_list rows match."},
    {"from": "blue_spell_list.mob_skill_id", "to": "mob_skills.mob_skill_id",
     "note": "Which real mob skill a Blue Magic spell is learned from (verified: 154/160 dsp rows match)."},
    {"from": "npc_list.zoneid", "to": "zones.zoneid",
     "note": "Verified: 29450/29450 dsp_npc_list rows match a real zone."},
    {"from": "item_equipment.itemid", "to": "item_basic.itemid",
     "note": "Equipment-specific detail row for a real item (verified: 13329/13330 dsp rows match)."},
    {"from": "item_weapon.itemid", "to": "item_basic.itemid",
     "note": "Weapon-specific detail row for a real item (verified: 4466/4466 dsp rows match)."},
    {"from": "item_usable.itemid", "to": "item_basic.itemid",
     "note": "Usable-item-specific detail row for a real item (verified: 2128/2128 dsp rows match)."},
    {"from": "instance_entities.instanceid", "to": "instance_list.instanceid",
     "note": "LOW CONFIDENCE -- only 46/404 dsp_instance_entities rows match a real instance_list "
             "row. Real relationship exists (the column names and a nonzero match confirm it), "
             "but most rows don't resolve -- don't trust an unmatched instanceid as evidence of "
             "absence without checking further."},
    {"from": "instance_entities.id", "to": "npc_list.npcid or mob_spawn_points.mobid",
     "note": "POLYMORPHIC, not a single table -- instance_entities.id refers to EITHER an NPC or a "
             "mob spawn point depending on the entity's real type (verified: distinct real matches "
             "against both npc_list.npcid and mob_spawn_points.mobid, not just one). Check both."},
]


def _relationships_for(table: str) -> list[dict]:
    """Real relationships (from RELATIONSHIPS) involving `table`, with the placeholder bare table
    names re-prefixed to match `table`'s own real prefix (dsp_/lsb_/topaz_/sql_/none)."""
    prefix = ""
    for p in ("dsp_", "lsb_", "topaz_", "sql_"):
        if table.startswith(p):
            prefix = p
            break
    bare = table[len(prefix):] if prefix else table

    def reprefix(ref: str) -> str:
        # ref looks like "mob_groups.dropid" or "npc_list.npcid or mob_spawn_points.mobid" --
        # re-prefix every bare table name mentioned, not just a single simple case. "zones" is a
        # real single SHARED table (no dsp_/lsb_/topaz_/sql_ copies of it exist) -- never
        # re-prefix it, unlike every other table here which genuinely has 4 parallel copies.
        out = ref
        for other in ({r["from"].split(".")[0] for r in RELATIONSHIPS} | {
            t.split(".")[0] for r in RELATIONSHIPS for t in r["to"].replace(" or ", "|").split("|")
        }) - {"zones"}:
            out = re.sub(rf"\b{re.escape(other)}\b", prefix + other, out)
        return out

    hits = []
    for r in RELATIONSHIPS:
        from_table = r["from"].split(".")[0]
        to_tables = [t.split(".")[0] for t in r["to"].replace(" or ", "|").split("|")]
        if bare == from_table or bare in to_tables:
            hits.append({"from": reprefix(r["from"]), "to": reprefix(r["to"]), "note": r["note"]})
    return hits


def describe_table(name: str = "", **_ignored) -> dict:
    """Real column names/types for one table, via PRAGMA table_info (a read, not a write --
    PRAGMA is blocked by _FORBIDDEN_RE in query_sql() for the general case, but this dedicated
    tool needs it specifically, so it's implemented directly rather than routed through there).
    Also returns any known real relationships (RELATIONSHIPS above) involving this table, so a
    model exploring a table's columns gets real join guidance for free, right when it needs it,
    instead of having to separately discover or guess at how tables connect."""
    if not name:
        return {"error": "name is required."}
    con = _readonly_connection()
    try:
        rows = con.execute(f'PRAGMA table_info("{name}")').fetchall()
        if not rows:
            return {"error": f"No such table: {name!r} (or it has no columns). Try list_tables first."}
        result = {"columns": [{"name": r["name"], "type": r["type"]} for r in rows]}
        relationships = _relationships_for(name)
        if relationships:
            result["known_relationships"] = relationships
        return result
    except sqlite3.Error as e:
        return {"error": f"SQL error: {e}"}
    finally:
        con.close()


def query_sql(sql: str = "", **_ignored) -> dict:
    """Runs exactly one real read-only SELECT/WITH statement. Refuses anything else outright by
    string-checking the query (belt) on top of the connection itself being physically read-only
    (suspenders) -- neither check alone is trusted. Truncates large results rather than returning
    everything, so one broad query can't blow the model's context budget."""
    if not sql.strip():
        return {"error": "sql is required."}
    cleaned = sql.strip().rstrip(";")
    if ";" in cleaned:
        return {"error": "Only a single SQL statement is allowed (no ';'-separated statements)."}
    if not _SELECT_RE.match(cleaned):
        return {"error": "Only SELECT/WITH statements are allowed."}
    if _FORBIDDEN_RE.search(cleaned):
        return {"error": "Query contains a disallowed keyword -- writes are never permitted through this tool."}

    con = _readonly_connection()
    try:
        cur = con.execute(cleaned)
        rows = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        result = {
            "columns": [d[0] for d in cur.description] if cur.description else [],
            "rows": [list(r) for r in rows],
            "truncated": truncated,
        }
        if truncated:
            result["note"] = f"Result truncated at {MAX_ROWS} rows -- narrow the query (WHERE/LIMIT) for more."
        text = json.dumps(result)
        if len(text) > MAX_RESULT_CHARS:
            return {"error": f"Result too large ({len(text)} chars) even after row capping -- "
                              f"select fewer columns or add a more specific WHERE clause."}
        return result
    except sqlite3.Error as e:
        return {"error": f"SQL error: {e}"}
    finally:
        con.close()


# name -> (function, human-readable one-line description for the system prompt)
TOOLS = {
    "list_tables": (list_tables, "list_tables(): real table names and row counts."),
    "describe_table": (describe_table, "describe_table(name): real column names/types for one table."),
    "query_sql": (query_sql, "query_sql(sql): runs one real read-only SELECT/WITH statement, returns matching rows (capped)."),
}


def call_tool(name: str, args: dict) -> dict:
    """Dispatches to one of TOOLS by name. Returns {"error": ...} for an unknown tool name or a
    non-dict args value, same shape as every other tool's own error return -- callers never need
    to special-case "the tool name itself was wrong" differently from "the tool call failed"."""
    entry = TOOLS.get(name)
    if entry is None:
        return {"error": f"Unknown tool: {name!r}. Available: {', '.join(TOOLS)}."}
    if not isinstance(args, dict):
        return {"error": "args must be a JSON object."}
    fn, _ = entry
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
