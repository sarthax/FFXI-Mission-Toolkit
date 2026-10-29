"""Durable, append-only storage for offline evidence receipts (#1202 Phase A).

Wraps the pure ``offline_evidence_reconciliation`` core; it never grants authority. Tables live in the existing
feature-testing results database but are separate from ``feature_test_results``: a stored receipt is NOT an imported
result, is never v1-import eligible, and its authoritative verdict stays UNKNOWN. Nothing here writes
``feature_test_results``.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .offline_evidence_reconciliation import OfflineEvidenceLedger, _apply, _validate

STORE_FORMAT = "toolkit-offline-receipt-store/1"


class StoreIntegrityError(ValueError):
    """A stored receipt no longer matches its recorded digest or fails validation."""


def _connect(path: str | Path) -> sqlite3.Connection:
    target = Path(path)
    if not target.is_absolute():
        raise ValueError("database path must be absolute")
    conn = sqlite3.connect(str(target), isolation_level=None, timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS offline_receipts (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id TEXT NOT NULL, run_id TEXT NOT NULL, execution_id TEXT NOT NULL, attempt INTEGER NOT NULL,
        operation_id TEXT NOT NULL, phase TEXT NOT NULL, operation_state TEXT NOT NULL,
        evidence_sha256 TEXT NOT NULL, receipt_json TEXT NOT NULL, ingested_at TEXT NOT NULL, outcome TEXT NOT NULL,
        UNIQUE (run_id, execution_id, attempt, receipt_id))""")
    conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS offline_receipts_one_terminal
        ON offline_receipts (run_id, execution_id, attempt, operation_id) WHERE phase = 'TERMINAL'""")
    return conn


def _load(conn: sqlite3.Connection, keys: set) -> dict:
    """Rebuild reconciliation state for ``keys`` from stored rows, re-verifying every receipt."""
    attempts: dict = {}
    for run_id, execution_id, attempt in sorted(keys):
        rows = conn.execute("SELECT receipt_json, evidence_sha256 FROM offline_receipts "
                            "WHERE run_id=? AND execution_id=? AND attempt=? ORDER BY seq",
                            (run_id, execution_id, attempt)).fetchall()
        for text, digest in rows:
            try:
                receipt = _validate(json.loads(text))
            except (ValueError, TypeError) as exc:
                raise StoreIntegrityError(f"stored receipt failed validation: {exc}") from exc
            if receipt["evidence_digest"] != digest:
                raise StoreIntegrityError("stored receipt digest differs from its recorded digest")
            if _apply(attempts, receipt)["status"] == "BLOCKED":
                raise StoreIntegrityError("stored receipts are mutually inconsistent")
    return attempts


def ingest_many(db_path: str | Path, receipts: list[dict]) -> dict:
    """Atomic durable batch with the same classification as the in-memory ledger; nothing persists if any blocks."""
    if not isinstance(receipts, list) or not 1 <= len(receipts) <= 100:
        return {"status": "BLOCKED", "reason": "INVALID_BATCH", "results": []}
    valid = []
    for raw in receipts:
        try:
            valid.append(_validate(raw))
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            return {"status": "BLOCKED", "reason": str(exc), "results": []}
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            staged = _load(conn, {(r["run_id"], r["execution_id"], r["attempt"]) for r in valid})
            results, fresh = [], []
            for receipt in valid:
                verdict = _apply(staged, receipt)
                if verdict["status"] == "BLOCKED":
                    conn.execute("ROLLBACK")
                    return {"status": "BLOCKED", "reason": verdict["reason"], "results": []}
                results.append(verdict)
                if verdict["status"] != "NO_CHANGE":
                    fresh.append((receipt, verdict["status"]))
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for receipt, outcome in fresh:
                conn.execute("INSERT INTO offline_receipts (receipt_id, run_id, execution_id, attempt, operation_id,"
                             " phase, operation_state, evidence_sha256, receipt_json, ingested_at, outcome)"
                             " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (receipt["receipt_id"], receipt["run_id"], receipt["execution_id"], receipt["attempt"],
                              receipt["operation_id"], receipt["phase"], receipt["operation_state"],
                              receipt["evidence_digest"],
                              json.dumps(receipt, sort_keys=True, allow_nan=False), stamp, outcome))
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return {"status": "ACCEPTED", "results": results}


def ingest(db_path: str | Path, receipt: dict) -> dict:
    batch = ingest_many(db_path, [receipt])
    if batch["status"] == "BLOCKED":
        return {"status": "BLOCKED", "reason": batch["reason"], "authoritative_gameplay_verdict": "UNKNOWN"}
    return batch["results"][0]


def snapshot(db_path: str | Path, run_id: str, execution_id: str, attempt: int) -> dict | None:
    """Same shape as the in-memory snapshot, with ``durable`` True; never v1-import eligible, never a PASS."""
    if not Path(db_path).is_file():
        return None
    conn = _connect(db_path)
    try:
        attempts = _load(conn, {(run_id, execution_id, attempt)})
    finally:
        conn.close()
    ledger = OfflineEvidenceLedger()
    ledger._attempts = deepcopy(attempts)
    snap = ledger.snapshot(run_id, execution_id, attempt)
    if snap is not None:
        snap["durable"] = True
    return snap
