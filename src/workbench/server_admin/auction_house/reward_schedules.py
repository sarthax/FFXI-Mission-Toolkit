"""Durable, operator-approved reward schedule definitions.

An operator explicitly approves a Test-only schedule with the named profile.
At execution time the worker rechecks the same profile and all Test write gates.
"""
from __future__ import annotations

from contextlib import contextmanager

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .reward_templates import normalize_items, RewardTemplateError

_DEFAULT = Path("data/auction_house_reward_schedules.db")


def _utc(iso: str) -> datetime:
    try:
        value = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise RewardTemplateError("Schedule needs a valid ISO-8601 timestamp") from exc
    if value.tzinfo is None:
        raise RewardTemplateError("Schedule timestamp requires a timezone")
    return value.astimezone(timezone.utc)


@contextmanager
def _connect(path):
    db = Path(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("""CREATE TABLE IF NOT EXISTS ah_reward_schedules (
        schedule_id TEXT PRIMARY KEY, due_utc TEXT NOT NULL, status TEXT NOT NULL,
        environment_json TEXT NOT NULL, recipient_mode TEXT NOT NULL,
        character_ids_json TEXT NOT NULL, items_json TEXT NOT NULL,
        created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL
    )""")
    con.commit()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def create_schedule(*, due_utc: str, environment: dict, recipient_mode: str,
                    character_ids: list[int], items: list[dict], confirmation: str, path=_DEFAULT) -> dict:
    due = _utc(due_utc)
    if due <= datetime.now(timezone.utc):
        raise RewardTemplateError("Scheduled time must be in the future")
    mode = str(recipient_mode).lower()
    if mode != "selected":
        raise RewardTemplateError("Scheduled campaigns require a frozen selected-recipient set")
    ids = sorted({int(i) for i in character_ids})
    if any(i <= 0 for i in ids) or (mode == "selected" and not ids) or (mode == "account" and len(ids) != 1):
        raise RewardTemplateError("Invalid scheduled character selection")
    if len(ids) > 5000:
        raise RewardTemplateError("Schedule exceeds recipient cap")
    normalized = normalize_items(items)
    if len(ids) * len(normalized) > 50000:
        raise RewardTemplateError("Schedule exceeds delivery-row cap")
    if str(confirmation or "") != str(environment.get("name") or ""):
        raise RewardTemplateError("Exact named Test profile confirmation is required")
    # Bind a future operator approval to the same named Test environment.
    if str(environment.get("environment") or "").lower() != "test" or not environment.get("name") or str(environment.get("family") or "").lower() not in {"dsp", "topaz"}:
        raise RewardTemplateError("Only a named DSP/Topaz Test environment can stage rewards")
    sid = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _connect(path) as db:
        db.execute("INSERT INTO ah_reward_schedules VALUES (?,?,?,?,?,?,?,?,?)",
                   (sid, due.isoformat(), "pending", json.dumps(environment, sort_keys=True),
                    mode, json.dumps(ids), json.dumps(normalized), now, now))
    return get_schedule(sid, path=path)


def get_schedule(schedule_id: str, *, path=_DEFAULT) -> dict:
    with _connect(path) as db:
        row = db.execute("SELECT * FROM ah_reward_schedules WHERE schedule_id=?", (schedule_id,)).fetchone()
    if row is None:
        raise KeyError("Reward schedule not found")
    return {
        "schedule_id": row["schedule_id"], "due_utc": row["due_utc"], "status": row["status"],
        "environment": json.loads(row["environment_json"]),
        "recipient_mode": row["recipient_mode"],
        "character_ids": json.loads(row["character_ids_json"]),
        "items": json.loads(row["items_json"]),
        "created_utc": row["created_utc"], "updated_utc": row["updated_utc"],
        "execution_policy": "operator_approved_test_once_revalidated_on_due_no_auto_retry",
    }


def list_schedules(*, path=_DEFAULT, limit=100) -> list[dict]:
    with _connect(path) as db:
        rows = db.execute("SELECT schedule_id FROM ah_reward_schedules ORDER BY due_utc LIMIT ?",
                          (max(1, min(int(limit), 500)),)).fetchall()
    return [get_schedule(r["schedule_id"], path=path) for r in rows]


def cancel_schedule(schedule_id: str, *, path=_DEFAULT) -> dict:
    with _connect(path) as db:
        result = db.execute("UPDATE ah_reward_schedules SET status='cancelled', updated_utc=? WHERE schedule_id=? AND status='pending'",
                            (datetime.now(timezone.utc).isoformat(), schedule_id))
        if result.rowcount != 1:
            raise RewardTemplateError("Only pending schedules can be cancelled")
    return get_schedule(schedule_id, path=path)
