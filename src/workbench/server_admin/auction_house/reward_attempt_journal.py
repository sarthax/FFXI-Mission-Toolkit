"""Durable per-recipient diagnostic record for guarded Auction House Mog rewards.

No automatic retry is allowed for an in-flight/unknown result: delivery_box and
the toolkit SQLite journal cannot commit atomically with each other.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from workbench.runtime.paths import DATA_ROOT

DEFAULT_PATH = DATA_ROOT / "auction_house_reward_attempts.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open(path: Path | str):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS ah_reward_attempts (
        replay_id TEXT PRIMARY KEY,
        preview_id TEXT NOT NULL,
        created_utc TEXT NOT NULL,
        updated_utc TEXT NOT NULL,
        environment_json TEXT NOT NULL,
        items_json TEXT NOT NULL,
        status TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ah_reward_attempt_recipients (
        replay_id TEXT NOT NULL,
        char_id INTEGER NOT NULL,
        char_name TEXT NOT NULL,
        state TEXT NOT NULL,
        diagnostic TEXT,
        updated_utc TEXT NOT NULL,
        PRIMARY KEY(replay_id,char_id)
    );
    """)
    return db


def begin_attempt(*, replay_id: str, preview_id: str, environment: dict,
                  items: list[dict], recipients: list[dict],
                  path: Path | str = DEFAULT_PATH) -> None:
    if not replay_id or not preview_id or not recipients:
        raise ValueError("A replay, preview and recipients are required")
    ids = [int(r["char_id"]) for r in recipients]
    if any(i <= 0 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Recipient identities must be unique and positive")
    with _open(path) as db:
        timestamp = _now()
        db.execute("INSERT INTO ah_reward_attempts VALUES (?,?,?,?,?,?,?)",
                   (replay_id, preview_id, timestamp, timestamp,
                    json.dumps(environment, sort_keys=True, default=str),
                    json.dumps(items, sort_keys=True, default=str), "prepared"))
        db.executemany(
            "INSERT INTO ah_reward_attempt_recipients VALUES (?,?,?,?,?,?)",
            [(replay_id, int(r["char_id"]), str(r["char_name"]), "pending", None, timestamp)
             for r in recipients],
        )


def mark_recipient(replay_id: str, char_id: int, state: str,
                   diagnostic: str | None = None,
                   *, path: Path | str = DEFAULT_PATH) -> None:
    previous = {"in_flight": "pending", "committed": "in_flight", "failed": "in_flight"}
    if state not in previous:
        raise ValueError("Invalid delivery journal state")
    with _open(path) as db:
        row = db.execute(
            "UPDATE ah_reward_attempt_recipients SET state=?,diagnostic=?,updated_utc=? "
            "WHERE replay_id=? AND char_id=? AND state=?",
            (state, str(diagnostic)[:500] if diagnostic else None,
             _now(), replay_id, int(char_id), previous[state]),
        )
        if row.rowcount != 1:
            raise ValueError("Recipient journal state is unavailable or has changed")
        db.execute("UPDATE ah_reward_attempts SET status='running',updated_utc=? WHERE replay_id=?",
                   (_now(), replay_id))


def finish_attempt(replay_id: str, *, path: Path | str = DEFAULT_PATH) -> dict:
    report = get_attempt(replay_id, path=path)
    states = [r["state"] for r in report["recipients"]]
    if all(s == "committed" for s in states):
        status = "completed"
    elif all(s == "failed" for s in states):
        status = "failed"
    elif any(s in {"pending", "in_flight"} for s in states):
        status = "reconciliation_required"
    else:
        status = "partial"
    with _open(path) as db:
        db.execute("UPDATE ah_reward_attempts SET status=?,updated_utc=? WHERE replay_id=?",
                   (status, _now(), replay_id))
    return get_attempt(replay_id, path=path)


def get_attempt(replay_id: str, *, path: Path | str = DEFAULT_PATH) -> dict[str, Any]:
    with _open(path) as db:
        row = db.execute("SELECT * FROM ah_reward_attempts WHERE replay_id=?", (replay_id,)).fetchone()
        if row is None:
            raise KeyError("Reward attempt not found")
        recipients = db.execute(
            "SELECT char_id,char_name,state,diagnostic,updated_utc "
            "FROM ah_reward_attempt_recipients WHERE replay_id=? ORDER BY char_id",
            (replay_id,),
        ).fetchall()
    rr = [dict(x) for x in recipients]
    unknown = sum(r["state"] in {"pending", "in_flight"} for r in rr)
    return {
        "replay_id": replay_id, "preview_id": row["preview_id"],
        "created_utc": row["created_utc"], "updated_utc": row["updated_utc"],
        "status": row["status"], "environment": json.loads(row["environment_json"]),
        "items": json.loads(row["items_json"]), "recipients": rr,
        "unknown_recipients": unknown,
        "reconciliation_required": unknown > 0 or row["status"] == "reconciliation_required",
        "automatic_retry_safe": False,
        "note": "Inspect game delivery_box and attempt journal before retrying unknown recipients.",
    }


def list_attempts(*, path: Path | str = DEFAULT_PATH, limit=100) -> list[dict[str, Any]]:
    with _open(path) as db:
        rows = db.execute("SELECT replay_id FROM ah_reward_attempts ORDER BY created_utc DESC LIMIT ?",
                          (max(1, min(int(limit), 500)),)).fetchall()
    return [get_attempt(r["replay_id"], path=path) for r in rows]
