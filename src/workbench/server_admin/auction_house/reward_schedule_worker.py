"""Explicitly approved DSP/Topaz TEST scheduled Mog reward dispatcher.

A due schedule is claimed at most once. If the process exits after the claim,
the status stays 'running' and must be reviewed; no automatic replay occurs.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import threading
from typing import Any

from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root

from .factory import open_auction_house
from .legacy_test_executor import evaluate_legacy_test_write_gate
from .reward_delivery import preview_reward_delivery, execute_reward_delivery
from .reward_campaigns import record_campaign
from .reward_schedules import _connect, _DEFAULT, get_schedule


def _identity_matches(expected: dict, active: dict) -> bool:
    return all(
        str(expected.get(key) or "").strip().lower()
        == str(active.get(key) or "").strip().lower()
        and bool(str(expected.get(key) or "").strip())
        for key in ("name", "family", "environment")
    )


def _claim(schedule_id: str, path=_DEFAULT) -> bool:
    with _connect(path) as db:
        row = db.execute(
            "UPDATE ah_reward_schedules SET status='running',updated_utc=? "
            "WHERE schedule_id=? AND status='pending' AND due_utc<=?",
            (datetime.now(timezone.utc).isoformat(), schedule_id,
             datetime.now(timezone.utc).isoformat()),
        )
        return row.rowcount == 1


def _end(schedule_id: str, status: str, *, path=_DEFAULT) -> None:
    if status not in {"completed", "partial", "failed", "review_required", "expired_review"}:
        raise ValueError("Invalid scheduled reward outcome")
    with _connect(path) as db:
        db.execute(
            "UPDATE ah_reward_schedules SET status=?,updated_utc=? "
            "WHERE schedule_id=? AND status='running'",
            (status, datetime.now(timezone.utc).isoformat(), schedule_id),
        )


def dispatch_due_once(*, path=_DEFAULT, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Scheduler clock must be timezone-aware")
    now = now.astimezone(timezone.utc)
    identity = get_active_server_identity()
    root = get_active_server_root()
    if root is None or str(identity.get("environment") or "").lower() != "test":
        return []
    with _connect(path) as db:
        due = db.execute(
            "SELECT schedule_id FROM ah_reward_schedules "
            "WHERE status='pending' AND due_utc<=? ORDER BY due_utc LIMIT 10",
            (now.isoformat(),),
        ).fetchall()
    outcomes: list[dict[str, Any]] = []
    for row in due:
        schedule = get_schedule(row["schedule_id"], path=path)
        if not _identity_matches(schedule["environment"], identity):
            continue
        # No late surprise deliveries after extended downtime.
        deadline = datetime.fromisoformat(schedule["due_utc"])
        if now - deadline > timedelta(hours=24):
            if _claim(schedule["schedule_id"], path):
                _end(schedule["schedule_id"], "expired_review", path=path)
            outcomes.append({"schedule_id": schedule["schedule_id"], "status": "expired_review"})
            continue
        # Claim before touching the game server. No concurrent or crash replay.
        if not _claim(schedule["schedule_id"], path):
            continue
        try:
            ctx = open_auction_house(root)
            try:
                gate = evaluate_legacy_test_write_gate(
                    environment=identity, schema_family_hint=ctx.service.schema.family_hint,
                    confirmation=str(identity.get("name") or ""),
                )
                if not gate.ready:
                    raise RuntimeError("Active Test write gate failed at scheduled execution")
                fresh = preview_reward_delivery(
                    service=ctx.service, mode="selected",
                    character_ids=schedule["character_ids"], items=schedule["items"],
                )
                result = execute_reward_delivery(
                    service=ctx.service, environment=identity, mode="selected",
                    character_ids=schedule["character_ids"], items=schedule["items"],
                    preview_token=fresh["preview_token"], preview_id=fresh["preview_id"],
                    replay_id=fresh["replay_id"], confirmation=str(identity["name"]),
                )
                record_campaign(
                    environment=identity, template=None, items=schedule["items"],
                    recipient_mode="selected", recipient_count=int(result["recipient_count"]),
                    preview_id=fresh["preview_id"], replay_id=fresh["replay_id"], result=result,
                )
            finally:
                ctx.close()
            _end(schedule["schedule_id"], result["status"], path=path)
            outcomes.append({"schedule_id": schedule["schedule_id"], "status": result["status"]})
        except Exception:
            # Unknown if a game DB commit occurred; stop, never automatically retry.
            _end(schedule["schedule_id"], "review_required", path=path)
            outcomes.append({"schedule_id": schedule["schedule_id"], "status": "review_required"})
    return outcomes


_started = False
_guard = threading.Lock()


def start_schedule_worker(interval_seconds: int = 60) -> None:
    """Start the opt-in-by-schedule worker; no schedules means no DB writes."""
    global _started
    with _guard:
        if _started:
            return
        _started = True

    def run() -> None:
        import time
        while True:
            try:
                dispatch_due_once()
            except Exception:
                # A schedule remains pending/running for review on restart.
                pass
            time.sleep(max(30, int(interval_seconds)))

    threading.Thread(target=run, name="ah-reward-test-scheduler", daemon=True).start()
