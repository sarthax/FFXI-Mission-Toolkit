from types import SimpleNamespace

from src.workbench.server_admin.auction_house import validation_report


class Replay:
    def as_dict(self):
        return {"replay_id": "replay-1", "consumed": False, "consumed_at_utc": None, "audit_id": None, "executor_ref": None}


def test_unified_validation_appends_local_audit_event(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        validation_report,
        "run_lsb_preview_validation",
        lambda **kwargs: {
            "status": "ready",
            "read_only_validation_ready": True,
            "execution_ready": False,
            "executor_enabled": False,
            "write_enabled": False,
            "operation": "list_item",
            "environment": kwargs["environment"],
            "stages": {},
            "blockers": [],
        },
    )

    def append(preview, report, *, event_id):
        captured["preview"] = preview
        captured["report"] = report
        captured["event_id"] = event_id
        return 42

    monkeypatch.setattr(validation_report, "append_validation_event", append)
    monkeypatch.setattr(validation_report, "replay_status", lambda replay_id: Replay())

    preview = {
        "action": "list_item",
        "preview_provenance": {
            "preview_id": "preview-1",
            "audit_id": "audit-1",
            "replay_id": "replay-1",
        },
    }
    service = SimpleNamespace(schema=SimpleNamespace(family_hint="lsb-compatible"))
    report = validation_report.run_preview_validation(
        service=service,
        environment={"family": "lsb", "is_active": True},
        preview=preview,
        server_root="/unused",
    )

    assert captured["preview"] is preview
    assert captured["event_id"].startswith("validation:preview-1:")
    assert report["audit_ledger"]["recorded"] is True
    assert report["audit_ledger"]["event_seq"] == 42
    assert report["audit_ledger"]["replay"]["consumed"] is False
    assert report["execution_ready"] is False
