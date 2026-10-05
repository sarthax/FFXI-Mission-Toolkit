from __future__ import annotations

import json
from pathlib import Path

from src.workbench.server_admin.auction_house import activity
from src.workbench.server_admin.auction_house.audit_ledger import (
    append_execution_event,
    list_execution_events,
)


def test_execution_events_are_append_only_filterable_and_payload_decoded(tmp_path):
    db = tmp_path / "ah-audit.db"
    append_execution_event(
        path=db,
        event_id="exec-1",
        occurred_at_utc="2026-10-05T01:00:00Z",
        environment={"family": "topaz", "name": "Test Topaz"},
        operation="player_purchase",
        status="committed",
        auction_id=91,
        character_id=22,
        item_id=1450,
        payload={"result": {"price": 5000}},
    )
    append_execution_event(
        path=db,
        event_id="exec-2",
        occurred_at_utc="2026-10-05T01:01:00Z",
        environment={"family": "dsp", "name": "Test DSP"},
        operation="return_to_seller",
        status="committed",
        auction_id=92,
        character_id=33,
        item_id=1451,
        payload={"result": {"return_method": "delivery_box"}},
    )

    rows = list_execution_events(path=db, environment_name="Test Topaz", character_id=22, item_id=1450)
    assert len(rows) == 1
    assert rows[0]["event_id"] == "exec-1"
    assert rows[0]["payload"]["result"]["price"] == 5000

    with db.open("rb") as handle:
        assert handle.read(16).startswith(b"SQLite format 3")


def test_record_executor_result_redacts_confirmation(monkeypatch):
    captured = {}

    def fake_append(**kwargs):
        captured.update(kwargs)
        return 7

    monkeypatch.setattr(activity, "append_execution_event", fake_append)
    seq = activity.record_executor_result(
        environment={"family": "topaz", "name": "Test Topaz"},
        operation="admin_buy",
        result={"status": "committed", "auction_id": 4, "seller_id": 9, "item_id": 100},
        request_payload={"auction_id": 4, "confirmation": "Test Topaz", "expected_price": 3000},
    )
    assert seq == 7
    assert captured["auction_id"] == 4
    assert captured["character_id"] == 9
    assert captured["item_id"] == 100
    assert "confirmation" not in captured["payload"]["request"]
    assert captured["payload"]["request"]["expected_price"] == 3000


def test_unified_activity_merges_execution_evidence_and_campaign(monkeypatch):
    monkeypatch.setattr(activity, "list_execution_events", lambda **kwargs: [{
        "event_id": "execution-1", "occurred_at_utc": "2026-10-05T03:00:00Z",
        "environment_name": "Test Topaz", "environment_family": "topaz",
        "operation": "admin_buy", "status": "committed", "auction_id": 11,
        "character_id": 44, "item_id": 100, "preview_id": None, "replay_id": None,
        "payload": {"result": {"status": "committed"}},
    }])
    monkeypatch.setattr(activity, "list_events", lambda **kwargs: [{
        "event_id": "replay-1", "occurred_at_utc": "2026-10-05T02:00:00Z",
        "event_type": "replay_consumed", "environment_name": None, "environment_family": None,
        "operation": None, "validation_status": None, "preview_id": "p1", "replay_id": "r1",
        "payload_json": json.dumps({"executor_ref": "reward"}),
    }])
    monkeypatch.setattr(activity, "list_campaigns", lambda **kwargs: [{
        "campaign_id": "campaign-1", "created_at_utc": "2026-10-05T01:00:00Z",
        "completed_at_utc": "2026-10-05T01:01:00Z", "environment": {"family": "dsp", "name": "Test DSP"},
        "overall_status": "partial", "items": [{"item_id": 200}], "preview_id": "p2", "replay_id": "r2",
    }])

    feed = activity.unified_activity(limit=20)
    assert [row["source"] for row in feed["rows"]] == ["execution", "evidence", "reward_campaign"]
    assert feed["read_only"] is True


def test_activity_route_ui_and_workspace_are_mounted():
    api = Path("src/workbench/server_admin/auction_house/activity_api.py").read_text(encoding="utf-8")
    integration = Path("src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    template = Path("gui/templates/auction_house_activity.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_activity.js").read_text(encoding="utf-8")

    assert '"/auction-house/activity"' in api
    assert '"/auction-house/activity.json"' in api
    assert '"AH Activity"' in integration
    assert '"/auction-house/activity"' in integration
    assert "aaCharacter" in template and "aaItem" in template and "aaEvidence" in template
    assert "/auction-house/activity.json" in script


def test_activity_layer_contains_no_server_mutation_sql():
    source = Path("src/workbench/server_admin/auction_house/activity.py").read_text(encoding="utf-8").upper()
    api = Path("src/workbench/server_admin/auction_house/activity_api.py").read_text(encoding="utf-8").upper()
    combined = source + api
    assert "UPDATE AUCTION_HOUSE" not in combined
    assert "INSERT INTO AUCTION_HOUSE" not in combined
    assert "DELETE FROM AUCTION_HOUSE" not in combined
