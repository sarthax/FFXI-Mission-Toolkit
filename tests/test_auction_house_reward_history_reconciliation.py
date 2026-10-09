"""Campaign detail explicitly surfaces uncertain delivery results."""
from workbench.server_admin.auction_house.reward_campaigns import record_campaign


def test_campaign_detail_exposes_reconciliation_required(tmp_path):
    campaign = record_campaign(
        environment={"name": "DSP Test", "family": "dsp", "environment": "test"},
        template=None, items=[{"item_id": 123, "quantity": 1}],
        recipient_mode="selected", recipient_count=2,
        preview_id="p", replay_id="r",
        result={"status": "partial", "results": [
            {"char_id": 1, "char_name": "A", "status": "committed", "rows": 1}
        ]},
        path=tmp_path / "campaign.db",
    )
    assert campaign["reconciliation_required"] is True
    assert "recipient_outcomes_incomplete" in campaign["reconciliation_issues"]


def test_complete_campaign_needs_no_manual_reconciliation(tmp_path):
    campaign = record_campaign(
        environment={}, template=None, items=[{"item_id": 123, "quantity": 1}],
        recipient_mode="selected", recipient_count=1,
        preview_id="p", replay_id="r",
        result={"status": "completed", "results": [
            {"char_id": 1, "char_name": "A", "status": "committed", "rows": 1}
        ]},
        path=tmp_path / "campaign.db",
    )
    assert campaign["reconciliation_required"] is False
    assert campaign["reconciliation_issues"] == []
