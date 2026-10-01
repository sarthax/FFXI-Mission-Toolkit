"""Read-only contract for exact capture row source locators.

Consumers outside the Captures component may query normalized capture-row provenance through
this module without importing capture ingestion/integrity implementation services.
"""
from __future__ import annotations

import json
import sqlite3


def canonical_row_key(row_key) -> str:
    """Return the stable serialized identity used by capture row-locator records."""
    if isinstance(row_key, str):
        try:
            parsed = json.loads(row_key)
        except (TypeError, json.JSONDecodeError):
            return row_key
        if isinstance(parsed, (dict, list)):
            return json.dumps(parsed, sort_keys=True)
        return row_key
    if isinstance(row_key, (dict, list)):
        return json.dumps(row_key, sort_keys=True)
    return str(row_key)


def find_row_locators(
    con: sqlite3.Connection,
    capture_id: int,
    target_table: str,
    row_key,
) -> list[dict]:
    """Return every exact source locator recorded for one normalized capture row.

    Multiple matches are intentionally preserved. Consumers must surface overlapping ownership
    rather than silently selecting one source.
    """
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='capture_row_locators'"
    ).fetchone():
        return []
    key = canonical_row_key(row_key)
    old_factory = con.row_factory
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT capture_id,filename,target_table,row_key,source_sha256,locator_basis,
                      start_line,end_line,start_offset,end_offset,details_json
               FROM capture_row_locators
               WHERE capture_id=? AND target_table=? AND row_key=?
               ORDER BY filename""",
            (int(capture_id), target_table, key),
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["details"] = json.loads(item.pop("details_json") or "{}")
            except json.JSONDecodeError:
                item["details"] = {}
                item.pop("details_json", None)
            out.append(item)
        return out
    finally:
        con.row_factory = old_factory
