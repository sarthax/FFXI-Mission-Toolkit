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

import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "ffxi_zone_database.db"

# Keep the stored prompt/response bounded -- this is a review log, not a full transcript archive;
# a multi-thousand-line generated Lua conversion or capture-log summary would otherwise bloat the
# settings DB for no real benefit (the full text is always still on disk wherever the caller wrote
# it, if it wrote it anywhere at all).
MAX_STORED_CHARS = 4000


def init_db(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS llm_call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at REAL NOT NULL,
            source TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt TEXT NOT NULL,
            response TEXT,
            error TEXT
        )
    """)
    con.commit()


def _truncate(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= MAX_STORED_CHARS:
        return text
    return text[:MAX_STORED_CHARS] + f"\n... [truncated, {len(text)} chars total]"


def record(source: str, model: str, prompt: str, response: str | None = None,
           error: str | None = None) -> None:
    """`source` is a short caller-chosen label -- "manual" for the GUI's LLM Assistant page, or
    a tool's own name (e.g. "capture_log_summarizer") for automated calls. Exactly one of
    `response`/`error` should normally be set (a call either succeeded or it didn't), but both
    being None just means "no response text to show," not an error in this function itself."""
    con = sqlite3.connect(str(DB_PATH))
    try:
        init_db(con)
        con.execute(
            "INSERT INTO llm_call_log (created_at, source, model, prompt, response, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), source, model, _truncate(prompt), _truncate(response), _truncate(error)),
        )
        con.commit()
    finally:
        con.close()


def recent(limit: int = 50) -> list[dict]:
    con = sqlite3.connect(str(DB_PATH))
    try:
        init_db(con)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM llm_call_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            # Formatted here, not via a Jinja filter -- matches this GUI's existing convention
            # (gui_server.py formats every other displayed timestamp in Python before the
            # template ever sees it, e.g. its own "ts_display"/"mtime" fields).
            d["created_display"] = datetime.fromtimestamp(d["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
            out.append(d)
        return out
    finally:
        con.close()
