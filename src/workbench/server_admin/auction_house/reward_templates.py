"""Toolkit-local saved item bundles for Auction House reward delivery."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from workbench.runtime.paths import DATA_ROOT

DEFAULT_REWARD_TEMPLATE_PATH = DATA_ROOT / "auction_house_reward_templates.db"
_MAX_ITEMS = 20


class RewardTemplateError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect(path: Path | str = DEFAULT_REWARD_TEMPLATE_PATH) -> sqlite3.Connection:
    db = Path(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db, timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute(
        """CREATE TABLE IF NOT EXISTS ah_reward_templates (
               template_id TEXT PRIMARY KEY,
               name TEXT NOT NULL,
               items_json TEXT NOT NULL,
               created_at_utc TEXT NOT NULL,
               updated_at_utc TEXT NOT NULL
           )"""
    )
    con.commit()
    return con


def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, int]]:
    if not isinstance(items, list) or not items:
        raise RewardTemplateError("Reward template requires at least one item")
    if len(items) > _MAX_ITEMS:
        raise RewardTemplateError(f"Reward template supports at most {_MAX_ITEMS} item rows")
    out: list[dict[str, int]] = []
    seen: set[int] = set()
    for raw in items:
        item_id = int(raw.get("item_id") or 0)
        quantity = int(raw.get("quantity") or 0)
        if item_id <= 0 or quantity <= 0:
            raise RewardTemplateError("item_id and quantity must be positive")
        if item_id in seen:
            raise RewardTemplateError("Duplicate item_id values are not allowed in one reward template")
        seen.add(item_id)
        out.append({"item_id": item_id, "quantity": quantity})
    return out


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "template_id": str(row["template_id"]),
        "name": str(row["name"]),
        "items": json.loads(str(row["items_json"])),
        "created_at_utc": str(row["created_at_utc"]),
        "updated_at_utc": str(row["updated_at_utc"]),
    }


def save_reward_template(*, name: str, items: list[dict[str, Any]], template_id: str | None = None,
                         path: Path | str = DEFAULT_REWARD_TEMPLATE_PATH) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise RewardTemplateError("Reward template name is required")
    if len(name) > 120:
        raise RewardTemplateError("Reward template name is too long")
    normalized = normalize_items(items)
    template_id = str(template_id or uuid4())
    now = _utc_now()
    con = _connect(path)
    try:
        existing = con.execute(
            "SELECT created_at_utc FROM ah_reward_templates WHERE template_id=?", (template_id,)
        ).fetchone()
        created = str(existing[0]) if existing else now
        con.execute(
            """INSERT INTO ah_reward_templates(template_id,name,items_json,created_at_utc,updated_at_utc)
               VALUES(?,?,?,?,?)
               ON CONFLICT(template_id) DO UPDATE SET
                 name=excluded.name,items_json=excluded.items_json,updated_at_utc=excluded.updated_at_utc""",
            (template_id, name, json.dumps(normalized, sort_keys=True, separators=(",", ":")), created, now),
        )
        con.commit()
        row = con.execute("SELECT * FROM ah_reward_templates WHERE template_id=?", (template_id,)).fetchone()
        return _decode(row)
    finally:
        con.close()


def get_reward_template(template_id: str, *, path: Path | str = DEFAULT_REWARD_TEMPLATE_PATH) -> dict[str, Any]:
    con = _connect(path)
    try:
        row = con.execute("SELECT * FROM ah_reward_templates WHERE template_id=?", (str(template_id),)).fetchone()
        if row is None:
            raise RewardTemplateError("Reward template was not found")
        return _decode(row)
    finally:
        con.close()


def list_reward_templates(*, path: Path | str = DEFAULT_REWARD_TEMPLATE_PATH) -> list[dict[str, Any]]:
    con = _connect(path)
    try:
        return [_decode(row) for row in con.execute(
            "SELECT * FROM ah_reward_templates ORDER BY name COLLATE NOCASE,template_id"
        ).fetchall()]
    finally:
        con.close()


def delete_reward_template(template_id: str, *, path: Path | str = DEFAULT_REWARD_TEMPLATE_PATH) -> bool:
    con = _connect(path)
    try:
        cur = con.execute("DELETE FROM ah_reward_templates WHERE template_id=?", (str(template_id),))
        con.commit()
        return int(cur.rowcount or 0) == 1
    finally:
        con.close()
