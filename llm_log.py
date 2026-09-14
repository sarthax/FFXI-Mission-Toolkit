#!/usr/bin/env python3
"""
llm_log.py -- shared call log for llm_client.py, recording every prompt/response that goes
through the local Open WebUI/Ollama instance, whether triggered manually (the GUI's "LLM
Assistant" page) or by an automated tool built on top of llm_client.chat(). Kept separate from
llm_client.py itself so that module stays dependency-free (no sqlite3 import forced on a caller
that only wants the HTTP wrapper) -- this module is the optional recording layer on top of it.

Uses the same sqlite DB as settings.py (ffxi_zone_database.db) and the same
"init_db-then-use" pattern. Never stores the API key or any auth material -- only prompt/response
text, so this table is fine to live in the routinely-stripped/rebuilt database (unlike the key
itself, see settings.py's llm_base_url/llm_default_model comment).

Any future automation should call record() right after every llm_client.chat() call it makes --
that's what makes the "automation we're building out" visible in the GUI's log, not a separate
mechanism per tool.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "ffxi_zone_database.db"

# Keep the stored prompt/response bounded -- this is a review log, not an unbounded archive. Set
# to match LLM_FILE_SUMMARY_MAX_CHARS (gui_server.py) -- the file-summarize quick action alone
# already builds prompts up to that size, so a lower cap here was silently truncating away a
# real, common case's own input before it ever reached the log, not just some hypothetical huge
# prompt. Any single call still over this (a very long tool-call transcript, a huge file) gets
# truncated with a visible marker rather than silently dropped.
MAX_STORED_CHARS = 40000


def init_db(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS llm_call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            source TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT,
            error TEXT,
            usage_json TEXT
        )
    """)
    con.commit()
    # Additive migration for rows created before usage_json existed -- ALTER TABLE ADD COLUMN is a
    # no-op error if it already exists, so probe first rather than try/except-swallow every call.
    cols = {row[1] for row in con.execute("PRAGMA table_info(llm_call_log)").fetchall()}
    if "usage_json" not in cols:
        con.execute("ALTER TABLE llm_call_log ADD COLUMN usage_json TEXT")
        con.commit()


def _truncate(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= MAX_STORED_CHARS:
        return text
    return text[:MAX_STORED_CHARS] + f"\n... [truncated, {len(text)} chars total]"


def record(source: str, model: str, prompt: str, response: str | None = None,
           error: str | None = None, usage: dict | None = None) -> None:
    """`source` is a short caller-chosen label -- "manual" for the GUI's LLM Assistant page, or
    a tool's own name (e.g. "capture_log_summarizer") for automated calls. Exactly one of
    `response`/`error` should normally be set (a call either succeeded or it didn't), but both
    being None just means "no response text to show," not an error in this function itself.
    `usage` is llm_client.chat_full()'s own `usage` dict (response_token/s, total_duration,
    prompt/completion token counts, etc.) -- stored verbatim as JSON, no schema assumed."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        init_db(con)
        con.execute(
            "INSERT INTO llm_call_log (created_at, source, model, prompt, response, error, usage_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (time.time(), source, model, _truncate(prompt), _truncate(response), _truncate(error),
             json.dumps(usage) if usage else None),
        )
        con.commit()
    finally:
        con.close()


def recent(limit: int = 50, source: str | None = None, model: str | None = None,
           q: str | None = None) -> list[dict]:
    """`source`/`model` filter on an exact match (both are short caller-chosen/model-id strings,
    not free text); `q` is a simple case-insensitive substring match against prompt OR response,
    for finding a specific past call once the log has more than a page's worth of rows."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        init_db(con)
        con.row_factory = sqlite3.Row
        clauses, params = [], []
        if source:
            clauses.append("source = ?")
            params.append(source)
        if model:
            clauses.append("model = ?")
            params.append(model)
        if q:
            clauses.append("(prompt LIKE ? OR response LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%"])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = con.execute(
            f"SELECT * FROM llm_call_log {where} ORDER BY id DESC LIMIT ?", params
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            # Formatted here, not via a Jinja filter -- matches this GUI's existing convention
            # (gui_server.py formats every other displayed timestamp in Python before the
            # template ever sees it, e.g. its own "ts_display"/"mtime" fields).
            d["created_display"] = datetime.fromtimestamp(d["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            usage = json.loads(d["usage_json"]) if d.get("usage_json") else {}
            tok_s = usage.get("response_token/s")
            total_s = usage.get("total_duration")
            d["usage_display"] = (
                f"{tok_s:.0f} tok/s, {total_s / 1e9:.1f}s" if tok_s and total_s
                else (f"{tok_s:.0f} tok/s" if tok_s else "")
            )
            out.append(d)
        return out
    finally:
        con.close()


def get_by_id(log_id: int) -> dict | None:
    """One full row (up to MAX_STORED_CHARS per field, same as recent() -- there is no separate
    unbounded copy anywhere) for the log detail page. None if no such id."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        init_db(con)
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM llm_call_log WHERE id = ?", (log_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["created_display"] = datetime.fromtimestamp(d["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        d["usage"] = json.loads(d["usage_json"]) if d.get("usage_json") else {}
        return d
    finally:
        con.close()


def distinct_sources() -> list[str]:
    """Every source label seen so far -- populates the log page's filter dropdown without
    hardcoding "manual" plus whatever automated tool names happen to exist."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        init_db(con)
        return [r[0] for r in con.execute(
            "SELECT DISTINCT source FROM llm_call_log ORDER BY source"
        ).fetchall()]
    finally:
        con.close()
