from __future__ import annotations

import json
import sqlite3

import pytest

from src.workbench.server_admin.auction_house.audit_ledger import (
    AuditLedgerError,
    ReplayAlreadyConsumed,
    append_validation_event,
    claim_replay_once,
    list_events,
    replay_status,
)


def _preview():
    return {
        "action": "list_item",
        "preview_provenance": {
            "preview_id": "preview-1",
            "audit_id": "audit-1",
            "replay_id": "replay-1",
            "environment": {"family": "lsb", "name": "Test LSB"},
        },
    }


def _report(status="ready"):
    return {
        "status": status,
        "operation": "list_item",
        "read_only_validation_ready": status == "ready",
        "execution_ready": False,
        "blockers": [] if status == "ready" else [{"stage": "policy", "code": "blocked", "message": "blocked"}],
    }


def test_validation_events_are_append_only_and_queryable(tmp_path):
    db = tmp_path / "ah-audit.db"
    first = append_validation_event(
        _preview(), _report(), path=db, event_id="event-1", occurred_at_utc="2026-10-04T20:00:00Z"
    )
    second = append_validation_event(
        _preview(), _report("blocked"), path=db, event_id="event-2", occurred_at_utc="2026-10-04T20:01:00Z"
    )
    assert first == 1
    assert second == 2

    rows = list_events(path=db, preview_id="preview-1")
    assert [row["event_id"] for row in rows] == ["event-2", "event-1"]
    assert rows[0]["validation_status"] == "blocked"
    payload = json.loads(rows[1]["payload_json"])
    assert payload["execution_ready"] is False
    assert payload["preview_provenance"]["audit_id"] == "audit-1"

    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM ah_audit_events").fetchone()[0] == 2


def test_replay_claim_is_atomic_insert_only_and_duplicate_fails(tmp_path):
    db = tmp_path / "ah-audit.db"
    assert replay_status("replay-1", path=db).consumed is False

    status = claim_replay_once(
        replay_id="replay-1",
        audit_id="audit-1",
        preview_id="preview-1",
        executor_ref="future-executor-test",
        path=db,
        consumed_at_utc="2026-10-04T20:02:00Z",
    )
    assert status.consumed is True
    assert replay_status("replay-1", path=db).executor_ref == "future-executor-test"

    with pytest.raises(ReplayAlreadyConsumed):
        claim_replay_once(
            replay_id="replay-1",
            audit_id="audit-1",
            preview_id="preview-1",
            executor_ref="second-attempt",
            path=db,
        )

    rows = list_events(path=db, replay_id="replay-1")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "replay_consumed"


def test_failed_replay_claim_does_not_append_second_event(tmp_path):
    db = tmp_path / "ah-audit.db"
    claim_replay_once(
        replay_id="replay-1",
        audit_id="audit-1",
        preview_id="preview-1",
        executor_ref="first",
        path=db,
    )
    with pytest.raises(ReplayAlreadyConsumed):
        claim_replay_once(
            replay_id="replay-1",
            audit_id="audit-2",
            preview_id="preview-2",
            executor_ref="second",
            path=db,
        )
    assert len(list_events(path=db, replay_id="replay-1")) == 1


def test_replay_claim_requires_complete_identity(tmp_path):
    with pytest.raises(AuditLedgerError):
        claim_replay_once(
            replay_id="",
            audit_id="audit-1",
            preview_id="preview-1",
            executor_ref="future",
            path=tmp_path / "ah-audit.db",
        )


def test_ledger_source_has_no_server_auction_mutation_or_event_row_update_delete():
    from pathlib import Path

    source = Path("src/workbench/server_admin/auction_house/audit_ledger.py").read_text(encoding="utf-8").upper()
    assert "UPDATE AUCTION_HOUSE" not in source
    assert "INSERT INTO AUCTION_HOUSE" not in source
    assert "DELETE FROM AUCTION_HOUSE" not in source
    assert "UPDATE AH_AUDIT_EVENTS" not in source
    assert "DELETE FROM AH_AUDIT_EVENTS" not in source
