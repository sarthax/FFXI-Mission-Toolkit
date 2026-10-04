"""Toolkit-local append-only audit and replay ledger for Auction House previews.

This module records validation evidence only. It never connects to or mutates an FFXI server
database. Replay consumption is represented by an insert-only unique claim so a future executor
can atomically claim one replay ID at most once before any server-side mutation is attempted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from workbench.runtime.paths import DATA_ROOT

DEFAULT_LEDGER_PATH = DATA_ROOT / "auction_house_audit.db"
LEDGER_SCHEMA_VERSION = 1


class AuditLedgerError(RuntimeError):
    pass


class ReplayAlreadyConsumed(AuditLedgerError):
    pass


@dataclass(frozen=True)
class ReplayStatus:
    replay_id: str
    consumed: bool
    consumed_at_utc: str | None = None
    audit_id: str | None = None
    executor_ref: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "consumed": self.consumed,
            "consumed_at_utc": self.consumed_at_utc,
            "audit_id": self.audit_id,
            "executor_ref": self.executor_ref,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect(path: Path | str = DEFAULT_LEDGER_PATH) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA foreign_keys=ON")
    _init_schema(con)
    return con


def _init_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS ah_audit_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ah_audit_events (
            event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            occurred_at_utc TEXT NOT NULL,
            event_type TEXT NOT NULL,
            preview_id TEXT,
            audit_id TEXT,
            replay_id TEXT,
            environment_family TEXT,
            environment_name TEXT,
            operation TEXT,
            validation_status TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ah_audit_events_preview ON ah_audit_events(preview_id, event_seq);
        CREATE INDEX IF NOT EXISTS idx_ah_audit_events_audit ON ah_audit_events(audit_id, event_seq);
        CREATE INDEX IF NOT EXISTS idx_ah_audit_events_replay ON ah_audit_events(replay_id, event_seq);
        CREATE TABLE IF NOT EXISTS ah_replay_consumptions (
            replay_id TEXT PRIMARY KEY,
            consumed_at_utc TEXT NOT NULL,
            audit_id TEXT NOT NULL,
            preview_id TEXT NOT NULL,
            executor_ref TEXT NOT NULL
        );
        """
    )
    con.execute(
        "INSERT OR IGNORE INTO ah_audit_meta(key,value) VALUES('schema_version',?)",
        (str(LEDGER_SCHEMA_VERSION),),
    )
    con.commit()


def _provenance(preview: dict[str, Any]) -> dict[str, Any]:
    value = preview.get("preview_provenance")
    return dict(value) if isinstance(value, dict) else {}


def append_validation_event(
    preview: dict[str, Any],
    report: dict[str, Any],
    *,
    path: Path | str = DEFAULT_LEDGER_PATH,
    event_id: str,
    occurred_at_utc: str | None = None,
) -> int:
    """Append one immutable preview-validation event and return its sequence number."""
    provenance = _provenance(preview)
    env = dict(provenance.get("environment") or report.get("environment") or {})
    payload = {
        "preview_provenance": provenance,
        "status": report.get("status"),
        "read_only_validation_ready": bool(report.get("read_only_validation_ready", False)),
        "execution_ready": False,
        "blockers": list(report.get("blockers") or []),
    }
    con = _connect(path)
    try:
        cur = con.execute(
            """INSERT INTO ah_audit_events(
                   event_id,occurred_at_utc,event_type,preview_id,audit_id,replay_id,
                   environment_family,environment_name,operation,validation_status,payload_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(event_id),
                occurred_at_utc or _utc_now(),
                "preview_validation",
                provenance.get("preview_id"),
                provenance.get("audit_id"),
                provenance.get("replay_id"),
                env.get("family"),
                env.get("name"),
                report.get("operation") or preview.get("action"),
                report.get("status"),
                json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str),
            ),
        )
        con.commit()
        return int(cur.lastrowid)
    finally:
        con.close()


def replay_status(replay_id: str, *, path: Path | str = DEFAULT_LEDGER_PATH) -> ReplayStatus:
    con = _connect(path)
    try:
        row = con.execute(
            "SELECT replay_id,consumed_at_utc,audit_id,executor_ref FROM ah_replay_consumptions WHERE replay_id=?",
            (str(replay_id),),
        ).fetchone()
        if row is None:
            return ReplayStatus(str(replay_id), False)
        return ReplayStatus(
            replay_id=str(row["replay_id"]),
            consumed=True,
            consumed_at_utc=str(row["consumed_at_utc"]),
            audit_id=str(row["audit_id"]),
            executor_ref=str(row["executor_ref"]),
        )
    finally:
        con.close()


def list_events(
    *,
    path: Path | str = DEFAULT_LEDGER_PATH,
    preview_id: str | None = None,
    audit_id: str | None = None,
    replay_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Read ledger events newest-first. This function never modifies existing event rows."""
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (("preview_id", preview_id), ("audit_id", audit_id), ("replay_id", replay_id)):
        if value:
            clauses.append(f"{column}=?")
            params.append(str(value))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(max(1, min(int(limit), 1000)))
    con = _connect(path)
    try:
        rows = con.execute(
            "SELECT * FROM ah_audit_events" + where + " ORDER BY event_seq DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def claim_replay_once(
    *,
    replay_id: str,
    audit_id: str,
    preview_id: str,
    executor_ref: str,
    path: Path | str = DEFAULT_LEDGER_PATH,
    consumed_at_utc: str | None = None,
) -> ReplayStatus:
    """Atomically claim one replay ID exactly once in toolkit-local storage.

    This does not enable or perform Auction House execution. A future executor may call this only
    immediately before its server transaction and must abort when ReplayAlreadyConsumed is raised.
    """
    if not all(str(value or "").strip() for value in (replay_id, audit_id, preview_id, executor_ref)):
        raise AuditLedgerError("replay_id, audit_id, preview_id, and executor_ref are required")
    con = _connect(path)
    timestamp = consumed_at_utc or _utc_now()
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            con.execute(
                "INSERT INTO ah_replay_consumptions(replay_id,consumed_at_utc,audit_id,preview_id,executor_ref) VALUES(?,?,?,?,?)",
                (str(replay_id), timestamp, str(audit_id), str(preview_id), str(executor_ref)),
            )
        except sqlite3.IntegrityError as exc:
            con.rollback()
            raise ReplayAlreadyConsumed(f"Replay ID {replay_id} has already been consumed") from exc
        con.execute(
            """INSERT INTO ah_audit_events(
                   event_id,occurred_at_utc,event_type,preview_id,audit_id,replay_id,
                   environment_family,environment_name,operation,validation_status,payload_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f"replay-consumed:{replay_id}", timestamp, "replay_consumed", str(preview_id),
                str(audit_id), str(replay_id), None, None, None, None,
                json.dumps({"executor_ref": str(executor_ref)}, sort_keys=True, separators=(",", ":")),
            ),
        )
        con.commit()
        return ReplayStatus(str(replay_id), True, timestamp, str(audit_id), str(executor_ref))
    except Exception:
        if con.in_transaction:
            con.rollback()
        raise
    finally:
        con.close()
