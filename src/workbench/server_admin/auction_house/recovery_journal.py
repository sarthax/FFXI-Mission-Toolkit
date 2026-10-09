"""Crash-persistent *diagnostic* journal for non-atomic DSP AH operations.

A pending entry is evidence of a possible interruption, NOT evidence that the
game DB operation failed or succeeded. Never auto-compensate from this journal.
"""
from __future__ import annotations

from contextlib import contextmanager

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from workbench.runtime.paths import DATA_ROOT

_DEFAULT = DATA_ROOT / "auction_house_recovery.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(path: Path | str):
    dbpath = Path(path)
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(dbpath, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS ah_recovery_cases (
        case_id TEXT PRIMARY KEY, operation TEXT NOT NULL, status TEXT NOT NULL,
        environment_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
        created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL
    )""")
    db.commit()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def begin_case(*, operation: str, environment: dict[str, Any],
               evidence: dict[str, Any], path: Path | str = _DEFAULT) -> str:
    if operation not in {"player_listing", "player_purchase"}:
        raise ValueError("Only non-atomic DSP listing and purchase have this diagnostic contract")
    if str(environment.get("family") or "").lower() != "dsp":
        raise ValueError("Recovery journal is DSP-only")
    case_id, now = str(uuid4()), _now()
    with _connect(path) as db:
        db.execute("INSERT INTO ah_recovery_cases VALUES (?,?,?,?,?,?,?)",
                   (case_id, operation, "possibly_interrupted",
                    json.dumps(environment, sort_keys=True, default=str),
                    json.dumps(evidence, sort_keys=True, default=str), now, now))
    return case_id


def set_case_status(case_id: str, status: str, *, details: dict | None = None,
                    path: Path | str = _DEFAULT) -> None:
    if status not in {"completed_non_atomic", "compensated", "recovery_required"}:
        raise ValueError("Unsupported case outcome")
    with _connect(path) as db:
        row = db.execute("SELECT evidence_json FROM ah_recovery_cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError("Recovery case missing")
        evidence = json.loads(row["evidence_json"])
        if details:
            evidence["outcome"] = details
        updated = db.execute(
            "UPDATE ah_recovery_cases SET status=?, evidence_json=?, updated_utc=? "
            "WHERE case_id=? AND status='possibly_interrupted'",
            (status, json.dumps(evidence, sort_keys=True, default=str), _now(), case_id),
        )
        if updated.rowcount != 1:
            raise ValueError("Recovery case already finalized")


def list_cases(*, environment_name: str | None = None, unresolved_only: bool = True,
               limit: int = 100, path: Path | str = _DEFAULT) -> list[dict[str, Any]]:
    with _connect(path) as db:
        q = "SELECT * FROM ah_recovery_cases"
        clauses = []
        args: list[Any] = []
        if unresolved_only:
            clauses.append("status IN ('possibly_interrupted', 'recovery_required')")
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_utc DESC LIMIT ?"
        args.append(max(1, min(int(limit), 500)))
        rows = db.execute(q, tuple(args)).fetchall()
    result = []
    for row in rows:
        env = json.loads(row["environment_json"])
        if environment_name is not None and env.get("name") != environment_name:
            continue
        result.append({
            "case_id": row["case_id"], "operation": row["operation"],
            "status": row["status"], "environment": env,
            "evidence": json.loads(row["evidence_json"]),
            "created_utc": row["created_utc"], "updated_utc": row["updated_utc"],
            "automatic_recovery_safe": False,
        })
    return result
