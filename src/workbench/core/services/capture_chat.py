"""Canonical capture chat/message observations.

Chat evidence from independent loggers stays source-specific here. Legacy source-specific
tables may remain for compatibility, but new consumers should use capture_chat_observations.
"""
from __future__ import annotations

import json
import sqlite3

from workbench.core.services import capture_integrity


def _next_seq(con: sqlite3.Connection, capture_id: int) -> int:
    row = con.execute(
        "SELECT COALESCE(MAX(seq), -1) + 1 FROM capture_chat_observations WHERE capture_id=?",
        (capture_id,),
    ).fetchone()
    return int(row[0] or 0)


def _existing_seq(
    con: sqlite3.Connection,
    capture_id: int,
    source_format: str,
    source_native_id: str | None,
) -> int | None:
    if not source_native_id:
        return None
    row = con.execute(
        """SELECT seq FROM capture_chat_observations
           WHERE capture_id=? AND source_format=? AND source_native_id=?""",
        (capture_id, source_format, source_native_id),
    ).fetchone()
    return int(row[0]) if row else None


def insert_chat_observation(
    con: sqlite3.Connection,
    capture_id: int,
    *,
    ts: str | None,
    direction: str | None,
    zone_id: int | None,
    zone_db: str | None,
    text: str,
    source_format: str,
    source_native_id: str | None,
    filename: str,
    source_sha256: str,
    locator_basis: str,
    start_line: int | None = None,
    end_line: int | None = None,
    start_offset: int | None = None,
    end_offset: int | None = None,
    details: dict | None = None,
) -> int:
    existing = _existing_seq(con, capture_id, source_format, source_native_id)
    seq = existing if existing is not None else _next_seq(con, capture_id)
    con.execute(
        """INSERT OR REPLACE INTO capture_chat_observations
           (capture_id,seq,ts,direction,zone_id,zone_db,text,source_format,source_native_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            capture_id, seq, ts, direction, zone_id, zone_db, text,
            source_format, source_native_id,
        ),
    )
    locator_details = {
        "source_format": source_format,
        "source_native_id": source_native_id,
        "timestamp": ts,
        "direction": direction,
        "zone_id": zone_id,
        "zone_db": zone_db,
    }
    if details:
        locator_details.update(details)
    capture_integrity.record_row_locator(
        con, capture_id, filename, "capture_chat_observations",
        json.dumps({"seq": seq}, sort_keys=True), locator_basis,
        source_sha256=source_sha256,
        start_line=start_line, end_line=end_line,
        start_offset=start_offset, end_offset=end_offset,
        details=locator_details,
    )
    return seq
