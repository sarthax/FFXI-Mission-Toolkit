"""Saved custom augmented item configurations; never authorizes delivery."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from workbench.runtime.paths import DATA_ROOT
from .reward_templates import RewardTemplateError

DEFAULT_PATH = DATA_ROOT / "auction_house_augment_catalog.db"


@contextmanager
def _db(path=DEFAULT_PATH):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS ah_augmented_reward_catalog (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, item_id INTEGER NOT NULL,
        family TEXT NOT NULL, augments_json TEXT NOT NULL, created_utc TEXT NOT NULL,
        updated_utc TEXT NOT NULL
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


def _decode(row):
    return {"id": row["id"], "name": row["name"], "item_id": row["item_id"],
            "family": row["family"], "augments": json.loads(row["augments_json"]),
            "created_utc": row["created_utc"], "updated_utc": row["updated_utc"]}


def list_configs(*, path=DEFAULT_PATH, limit=100):
    with _db(path) as db:
        rows = db.execute("SELECT * FROM ah_augmented_reward_catalog ORDER BY name,id LIMIT ?",
                          (max(1,min(500,int(limit))),)).fetchall()
        return [_decode(row) for row in rows]


def save_config(*, name, item_id, augments, family, config_id=None, path=DEFAULT_PATH):
    name = str(name or "").strip()
    if not name or len(name) > 120:
        raise RewardTemplateError("Catalog name must be 1–120 characters")
    item_id = int(item_id)
    if item_id <= 0:
        raise RewardTemplateError("Item ID must be positive")
    family = str(family or "").lower()
    if family not in {"dsp","topaz","lsb"}:
        raise RewardTemplateError("Unsupported server family")
    if not isinstance(augments,list) or not 1 <= len(augments) <= 4:
        raise RewardTemplateError("Select one to four augments")
    cleaned=[]
    for item in augments:
        if not isinstance(item,dict) or isinstance(item.get("id"),bool) or isinstance(item.get("value"),bool):
            raise RewardTemplateError("Invalid augment")
        try:
            aid, value=int(item["id"]),int(item["value"])
        except (TypeError,ValueError,KeyError) as exc:
            raise RewardTemplateError("Augment ID/value must be numeric") from exc
        if not 1 <= aid <= 2047 or not 0 <= value <= 31:
            raise RewardTemplateError("Augment ID/value outside server codec bounds")
        cleaned.append({"id":aid,"value":value})
    config_id = str(config_id or uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _db(path) as db:
        prior=db.execute("SELECT created_utc FROM ah_augmented_reward_catalog WHERE id=?",(config_id,)).fetchone()
        db.execute("INSERT OR REPLACE INTO ah_augmented_reward_catalog VALUES (?,?,?,?,?,?,?)",
                   (config_id,name,item_id,family,json.dumps(cleaned),
                    prior["created_utc"] if prior else now,now))
        row=db.execute("SELECT * FROM ah_augmented_reward_catalog WHERE id=?",(config_id,)).fetchone()
        return _decode(row)


def delete_config(config_id, *, path=DEFAULT_PATH):
    with _db(path) as db:
        row=db.execute("DELETE FROM ah_augmented_reward_catalog WHERE id=?",(str(config_id),))
        if row.rowcount != 1:
            raise KeyError("Augmented reward configuration not found")
    return {"deleted":True}
