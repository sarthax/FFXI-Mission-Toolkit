"""Toolkit-local saved Auction House administration presets.

Presets store reusable operator configuration only. They never store confirmations, preview tokens,
credentials, or execution authorization. Every use must re-preview live server state.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from workbench.runtime.paths import DATA_ROOT

DEFAULT_PRESET_PATH = DATA_ROOT / "auction_house_presets.db"
PRESET_SCHEMA_VERSION = 1
_SUPPORTED_KINDS = {"cleanup", "synthetic_seed"}
_CLEANUP_FIELDS = {
    "seller_id", "seller_name", "category_id", "item_id", "min_price", "max_price",
    "min_age_days", "listed_before", "limit", "default_action",
}
_SEED_FIELDS = {"seller_id", "category_id", "price", "stack_mode", "copies_per_item", "limit_items"}


class PresetError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect(path: Path | str = DEFAULT_PRESET_PATH) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    _init_schema(con)
    return con


def _init_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS ah_preset_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ah_admin_presets (
            preset_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ah_admin_presets_kind_name
            ON ah_admin_presets(kind, name COLLATE NOCASE);
        """
    )
    con.execute(
        "INSERT OR IGNORE INTO ah_preset_meta(key,value) VALUES('schema_version',?)",
        (str(PRESET_SCHEMA_VERSION),),
    )
    con.commit()


def normalize_preset_config(kind: str, config: dict[str, Any]) -> dict[str, Any]:
    kind = str(kind or "").strip().lower()
    if kind not in _SUPPORTED_KINDS:
        raise PresetError(f"Unsupported Auction House preset kind: {kind or 'unknown'}")
    if not isinstance(config, dict):
        raise PresetError("Preset config must be an object")
    allowed = _CLEANUP_FIELDS if kind == "cleanup" else _SEED_FIELDS
    unknown = sorted(set(config) - allowed)
    if unknown:
        raise PresetError("Unsupported preset field(s): " + ", ".join(unknown))

    out = {key: value for key, value in config.items() if value not in (None, "")}
    if kind == "cleanup":
        for key in ("seller_id", "category_id", "item_id", "min_price", "max_price", "listed_before", "limit"):
            if key in out:
                out[key] = int(out[key])
        if "min_age_days" in out:
            out["min_age_days"] = float(out["min_age_days"])
            if out["min_age_days"] < 0:
                raise PresetError("min_age_days cannot be negative")
        if "limit" in out:
            out["limit"] = max(1, min(int(out["limit"]), 100))
        if "seller_name" in out:
            out["seller_name"] = str(out["seller_name"]).strip()
        if "default_action" in out:
            action = str(out["default_action"]).strip().lower()
            if action not in {"admin_buy", "return_to_seller"}:
                raise PresetError("default_action must be admin_buy or return_to_seller")
            out["default_action"] = action
        if "min_price" in out and "max_price" in out and out["min_price"] > out["max_price"]:
            raise PresetError("min_price cannot exceed max_price")
    else:
        for key in ("seller_id", "category_id", "price", "copies_per_item", "limit_items"):
            if key in out:
                out[key] = int(out[key])
        mode = str(out.get("stack_mode") or "single").strip().lower()
        if mode not in {"single", "stack", "auto"}:
            raise PresetError("stack_mode must be single, stack, or auto")
        out["stack_mode"] = mode
        out["copies_per_item"] = max(1, min(int(out.get("copies_per_item") or 1), 5))
        out["limit_items"] = max(1, min(int(out.get("limit_items") or 100), 250))
        for required in ("seller_id", "category_id", "price"):
            if int(out.get(required) or 0) <= 0:
                raise PresetError(f"{required} must be positive")
    return out


def save_preset(*, name: str, kind: str, config: dict[str, Any], preset_id: str | None = None,
                path: Path | str = DEFAULT_PRESET_PATH) -> dict[str, Any]:
    name = str(name or "").strip()
    if not name:
        raise PresetError("Preset name is required")
    if len(name) > 120:
        raise PresetError("Preset name is limited to 120 characters")
    kind = str(kind or "").strip().lower()
    normalized = normalize_preset_config(kind, config)
    now = _utc_now()
    preset_id = str(preset_id or uuid4())
    con = _connect(path)
    try:
        existing = con.execute(
            "SELECT created_at_utc FROM ah_admin_presets WHERE preset_id=?", (preset_id,)
        ).fetchone()
        created = str(existing["created_at_utc"]) if existing else now
        con.execute(
            """INSERT INTO ah_admin_presets(preset_id,name,kind,config_json,created_at_utc,updated_at_utc)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(preset_id) DO UPDATE SET
                   name=excluded.name,kind=excluded.kind,config_json=excluded.config_json,
                   updated_at_utc=excluded.updated_at_utc""",
            (preset_id, name, kind, json.dumps(normalized, sort_keys=True, separators=(",", ":")), created, now),
        )
        con.commit()
        return get_preset(preset_id, path=path)
    finally:
        con.close()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "preset_id": str(row["preset_id"]),
        "name": str(row["name"]),
        "kind": str(row["kind"]),
        "config": json.loads(str(row["config_json"])),
        "created_at_utc": str(row["created_at_utc"]),
        "updated_at_utc": str(row["updated_at_utc"]),
    }


def get_preset(preset_id: str, *, path: Path | str = DEFAULT_PRESET_PATH) -> dict[str, Any]:
    con = _connect(path)
    try:
        row = con.execute("SELECT * FROM ah_admin_presets WHERE preset_id=?", (str(preset_id),)).fetchone()
        if row is None:
            raise PresetError("Auction House preset was not found")
        return _row_dict(row)
    finally:
        con.close()


def list_presets(*, kind: str | None = None, path: Path | str = DEFAULT_PRESET_PATH) -> list[dict[str, Any]]:
    con = _connect(path)
    try:
        if kind:
            normalized_kind = str(kind).strip().lower()
            if normalized_kind not in _SUPPORTED_KINDS:
                raise PresetError("Unsupported preset kind")
            rows = con.execute(
                "SELECT * FROM ah_admin_presets WHERE kind=? ORDER BY name COLLATE NOCASE,preset_id",
                (normalized_kind,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM ah_admin_presets ORDER BY kind,name COLLATE NOCASE,preset_id"
            ).fetchall()
        return [_row_dict(row) for row in rows]
    finally:
        con.close()


def delete_preset(preset_id: str, *, path: Path | str = DEFAULT_PRESET_PATH) -> bool:
    con = _connect(path)
    try:
        cur = con.execute("DELETE FROM ah_admin_presets WHERE preset_id=?", (str(preset_id),))
        con.commit()
        return int(cur.rowcount or 0) == 1
    finally:
        con.close()
