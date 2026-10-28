"""Opt-in local operator-only MOG-09 execution and durable job history.

No model tools, arbitrary commands, or general-purpose scripting. The separate
operator token is never returned by this module; HTTP routes must require it.
"""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .execution_cli import execute_mog09

_LOCK = threading.Lock()
_THREADS: dict[str, threading.Thread] = {}


def _db_path() -> Path:
    configured = os.environ.get("MISSION_TOOLKIT_TEST_JOBS_DB", "")
    if not configured:
        raise ValueError("MISSION_TOOLKIT_TEST_JOBS_DB not configured")
    path = Path(configured)
    if not path.is_absolute() or not path.parent.is_dir():
        raise ValueError("job database path must be absolute and parent must exist")
    return path


def authorize_operator(token: str | None) -> None:
    expected = os.environ.get("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN", "")
    if len(expected) < 32 or not token or not hmac.compare_digest(token, expected):
        raise PermissionError("Operator execution not configured or unauthorized")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), timeout=5)
    conn.execute("""CREATE TABLE IF NOT EXISTS feature_test_jobs (
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        case_id TEXT NOT NULL, status TEXT NOT NULL, account TEXT NOT NULL,
        charid INTEGER NOT NULL, run_id TEXT, verdict TEXT, error TEXT)""")
    existing = {row[1] for row in conn.execute("PRAGMA table_info(feature_test_jobs)")}
    if "phase" not in existing:
        conn.execute("ALTER TABLE feature_test_jobs ADD COLUMN phase TEXT NOT NULL DEFAULT 'not_started'")
    if "phase_updated_at" not in existing:
        conn.execute("ALTER TABLE feature_test_jobs ADD COLUMN phase_updated_at TEXT")
    return conn


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def jobs(limit: int = 20) -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("invalid job history limit")
    with _LOCK, _connect() as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT * FROM feature_test_jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def job_for_run(run_id: str) -> dict | None:
    """The runner job that produced ``run_id``: status, phase, verdict and error only (never account or character).

    Read-only. Returns None when no job store is configured or present, or no job recorded that run. It never
    creates the store.
    """
    try:
        path = _db_path()
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        with _LOCK, _connect() as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT status, phase, verdict, error FROM feature_test_jobs WHERE run_id=? "
                             "ORDER BY created_at DESC LIMIT 1", (run_id,)).fetchone()
    except sqlite3.Error:
        return None
    return dict(row) if row else None


def _set_phase(job_id: str, phase: str) -> None:
    if phase not in {"not_started", "runner_invoked", "runner_finished", "report_validated", "evidence_imported", "operator_reconciled", "failed"}:
        raise ValueError("unknown execution phase")
    with _LOCK, _connect() as db:
        db.execute("UPDATE feature_test_jobs SET phase=?, phase_updated_at=?, updated_at=? WHERE id=? AND status IN ('QUEUED','RUNNING')",
                   (phase, _stamp(), _stamp(), job_id))


def _set_status(job_id: str, status: str, *, run_id=None, verdict=None, error=None) -> None:
    with _LOCK, _connect() as db:
        db.execute("UPDATE feature_test_jobs SET status=?, updated_at=?, run_id=?, verdict=?, error=? WHERE id=?",
                   (status, _stamp(), run_id, verdict, error, job_id))


def _run(job_id: str, account: str, charid: int, port: int, artifacts: Path) -> None:
    _set_status(job_id, "RUNNING")
    _set_phase(job_id, "runner_invoked")
    try:
        outcome = execute_mog09(account=account, charid=charid, out_dir=artifacts,
                                supervisor=f"http://127.0.0.1:{port}", approved=True,
                                progress=lambda phase: _set_phase(job_id, phase))
    except ValueError as exc:  # pre-launch validation text is operator-safe and says what to fix
        _set_phase(job_id, "failed")
        _set_status(job_id, "ERROR", error=str(exc)[:300])
    except Exception:
        _set_phase(job_id, "failed")
        # Diagnostics remain in local artifacts; do not disclose command output or credentials.
        _set_status(job_id, "ERROR", error="Runner failed; inspect local test artifacts and service logs")
    else:
        _set_status(job_id, "COMPLETED", run_id=outcome["run_id"], verdict=outcome["verdict"])


def enqueue(account: str, charid: int, port: int) -> str:
    from .test_builder import build_plan
    plan = build_plan(account, charid, port)
    if not plan["ready_for_operator_review"]:
        raise ValueError("Test is not ready for operator launch or character not approved")
    folder = os.environ.get("MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT", "")
    root = Path(folder)
    if not folder or not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise ValueError("MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT must be an existing absolute directory")
    with _LOCK, _connect() as db:
        active = db.execute("SELECT COUNT(*) FROM feature_test_jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0]
        if active:
            raise ValueError("Another test job is already active; investigate stale jobs before retrying")
        job_id = uuid.uuid4().hex
        stamp = _stamp()
        db.execute("INSERT INTO feature_test_jobs (id, created_at, updated_at, case_id, status, account, charid) VALUES (?,?,?,?,?,?,?)",
                   (job_id, stamp, stamp, "MOG-09", "QUEUED", account, charid))
    artifacts = root / ("mog09-" + job_id)
    thread = threading.Thread(target=_run, args=(job_id, account, charid, port, artifacts),
                              name="mog09-" + job_id[:8], daemon=True)
    _THREADS[job_id] = thread
    try:
        thread.start()
    except RuntimeError:
        _set_status(job_id, "ERROR", error="Could not start local runner thread")
        _THREADS.pop(job_id, None)
        raise
    return job_id


def recover_interrupted(job_id: str, *, acknowledged: bool) -> dict:
    """Explicit operator reconciliation; never kill a process or claim cancellation.

    Only jobs with no live thread in this worker may be acknowledged. An operator
    must separately confirm no other Toolkit worker or XiHeadless runner is
    executing this character before calling this endpoint.
    """
    if not acknowledged:
        raise ValueError("Operator must acknowledge external runner/process inspection")
    if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
        raise ValueError("invalid job identifier")
    with _LOCK, _connect() as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM feature_test_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("unknown job")
        if row["status"] not in ("QUEUED", "RUNNING"):
            raise ValueError("only active jobs can be reconciled")
        active_thread = _THREADS.get(job_id)
        if active_thread and active_thread.is_alive():
            raise ValueError("job is still running in this Toolkit process")
        db.execute("UPDATE feature_test_jobs SET status='INTERRUPTED', phase='operator_reconciled', phase_updated_at=?, updated_at=?, error=? WHERE id=? AND status IN ('QUEUED','RUNNING')",
                   (_stamp(), _stamp(), "Operator reconciled after confirming no external runner is active; evidence not automatically authenticated", job_id))
        return {"job_id": job_id, "status": "INTERRUPTED",
                "note": "Manual reconciliation only; no subprocess termination occurred"}
