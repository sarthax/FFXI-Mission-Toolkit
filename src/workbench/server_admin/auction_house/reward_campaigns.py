"""Toolkit-local reward campaign history for Auction House administration."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

_DEFAULT_PATH = Path("data/auction_house_reward_campaigns.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(path: Path | str = _DEFAULT_PATH) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS ah_reward_campaigns (
            campaign_id TEXT PRIMARY KEY,
            created_at_utc TEXT NOT NULL,
            completed_at_utc TEXT,
            environment_json TEXT NOT NULL,
            template_id TEXT,
            template_name TEXT,
            items_json TEXT NOT NULL,
            recipient_mode TEXT NOT NULL,
            recipient_count INTEGER NOT NULL,
            preview_id TEXT NOT NULL,
            replay_id TEXT NOT NULL,
            overall_status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ah_reward_campaign_recipients (
            campaign_id TEXT NOT NULL,
            char_id INTEGER NOT NULL,
            char_name TEXT NOT NULL,
            status TEXT NOT NULL,
            error_text TEXT,
            delivery_rows INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (campaign_id, char_id),
            FOREIGN KEY (campaign_id) REFERENCES ah_reward_campaigns(campaign_id)
        );
        CREATE INDEX IF NOT EXISTS idx_reward_campaigns_created ON ah_reward_campaigns(created_at_utc DESC);
        CREATE INDEX IF NOT EXISTS idx_reward_campaigns_status ON ah_reward_campaigns(overall_status, created_at_utc DESC);
        """
    )
    return connection


def record_campaign(*, environment: dict[str, Any], template: dict[str, Any] | None,
                    items: list[dict[str, Any]], recipient_mode: str, recipient_count: int,
                    preview_id: str, replay_id: str, result: dict[str, Any],
                    path: Path | str = _DEFAULT_PATH) -> dict[str, Any]:
    campaign_id = str(uuid4())
    created = _now()
    completed = _now()
    rows = list(result.get("results") or [])
    with _connect(path) as db:
        db.execute(
            "INSERT INTO ah_reward_campaigns "
            "(campaign_id,created_at_utc,completed_at_utc,environment_json,template_id,template_name,items_json,recipient_mode,recipient_count,preview_id,replay_id,overall_status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                campaign_id, created, completed,
                json.dumps(environment, sort_keys=True, default=str),
                None if not template else str(template.get("template_id") or "") or None,
                None if not template else str(template.get("name") or "") or None,
                json.dumps(items, sort_keys=True, default=str),
                str(recipient_mode), int(recipient_count), str(preview_id), str(replay_id),
                str(result.get("status") or "unknown"),
            ),
        )
        for row in rows:
            db.execute(
                "INSERT INTO ah_reward_campaign_recipients "
                "(campaign_id,char_id,char_name,status,error_text,delivery_rows) VALUES (?,?,?,?,?,?)",
                (
                    campaign_id, int(row.get("char_id") or 0), str(row.get("char_name") or ""),
                    str(row.get("status") or "unknown"),
                    None if not row.get("error") else str(row.get("error")),
                    int(row.get("rows") or 0),
                ),
            )
    return get_campaign(campaign_id, path=path)


def list_campaigns(*, status: str | None = None, template_id: str | None = None,
                   limit: int = 100, path: Path | str = _DEFAULT_PATH) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("c.overall_status=?")
        params.append(str(status))
    if template_id:
        clauses.append("c.template_id=?")
        params.append(str(template_id))
    safe_limit = max(1, min(int(limit), 500))
    sql = (
        "SELECT c.*, "
        "SUM(CASE WHEN r.status='committed' THEN 1 ELSE 0 END) AS completed_count, "
        "SUM(CASE WHEN r.status='failed' THEN 1 ELSE 0 END) AS failed_count "
        "FROM ah_reward_campaigns c LEFT JOIN ah_reward_campaign_recipients r USING(campaign_id)"
    )
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " GROUP BY c.campaign_id ORDER BY c.created_at_utc DESC LIMIT ?"
    params.append(safe_limit)
    with _connect(path) as db:
        rows = db.execute(sql, tuple(params)).fetchall()
    return [_campaign_row(row) for row in rows]


def _campaign_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "campaign_id": row["campaign_id"],
        "created_at_utc": row["created_at_utc"],
        "completed_at_utc": row["completed_at_utc"],
        "environment": json.loads(row["environment_json"]),
        "template_id": row["template_id"],
        "template_name": row["template_name"],
        "items": json.loads(row["items_json"]),
        "recipient_mode": row["recipient_mode"],
        "recipient_count": int(row["recipient_count"]),
        "preview_id": row["preview_id"],
        "replay_id": row["replay_id"],
        "overall_status": row["overall_status"],
        "completed_count": int(row["completed_count"] or 0) if "completed_count" in row.keys() else None,
        "failed_count": int(row["failed_count"] or 0) if "failed_count" in row.keys() else None,
    }


def get_campaign(campaign_id: str, *, path: Path | str = _DEFAULT_PATH) -> dict[str, Any]:
    with _connect(path) as db:
        row = db.execute("SELECT * FROM ah_reward_campaigns WHERE campaign_id=?", (str(campaign_id),)).fetchone()
        if row is None:
            raise KeyError("Reward campaign was not found")
        recipients = db.execute(
            "SELECT char_id,char_name,status,error_text,delivery_rows FROM ah_reward_campaign_recipients "
            "WHERE campaign_id=? ORDER BY char_id",
            (str(campaign_id),),
        ).fetchall()
    out = _campaign_row(row)
    out["recipients"] = [
        {
            "char_id": int(r[0]), "char_name": str(r[1]), "status": str(r[2]),
            "error": r[3], "delivery_rows": int(r[4] or 0),
        }
        for r in recipients
    ]
    out["completed_count"] = sum(1 for r in out["recipients"] if r["status"] == "committed")
    out["failed_count"] = sum(1 for r in out["recipients"] if r["status"] == "failed")
    out["retry_integrity"] = retry_integrity(out)
    return out



def retry_integrity(campaign: dict[str, Any]) -> dict[str, Any]:
    """Report whether a saved campaign has a complete, unambiguous retry set.

    Unknown or missing recipient outcomes must be reconciled manually: treating
    them as failures could duplicate previously committed Mog deliveries.
    """
    recipients = list(campaign.get("recipients") or [])
    expected = int(campaign.get("recipient_count") or 0)
    committed = sum(r.get("status") == "committed" for r in recipients)
    failed = sum(r.get("status") == "failed" for r in recipients)
    unknown = len(recipients) - committed - failed
    ids = [int(r.get("char_id") or 0) for r in recipients]
    issues = []
    if expected <= 0 or expected != len(recipients):
        issues.append("recipient_outcomes_incomplete")
    if unknown:
        issues.append("recipient_status_unknown")
    if any(i <= 0 for i in ids) or len(set(ids)) != len(ids):
        issues.append("recipient_identity_invalid")
    status = str(campaign.get("overall_status") or "").lower()
    calculated = "completed" if failed == 0 else ("failed" if committed == 0 else "partial")
    if status not in {"completed", "failed", "partial"} or (not issues and status != calculated):
        issues.append("campaign_status_inconsistent")
    return {
        "safe_retry_preview": not issues and failed > 0,
        "expected_recipients": expected,
        "recorded_recipients": len(recipients),
        "committed_recipients": committed,
        "failed_recipients": failed,
        "unknown_recipients": unknown,
        "issues": issues,
        "retry_character_ids": [int(r["char_id"]) for r in recipients if r.get("status") == "failed"] if not issues else [],
    }


def failed_recipient_ids(campaign_id: str, *, path: Path | str = _DEFAULT_PATH) -> list[int]:
    campaign = get_campaign(campaign_id, path=path)
    integrity = retry_integrity(campaign)
    if integrity["issues"]:
        raise ValueError("Campaign recipient outcomes require reconciliation before retry: " + ", ".join(integrity["issues"]))
    return integrity["retry_character_ids"]
