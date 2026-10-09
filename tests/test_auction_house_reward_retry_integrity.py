"""Campaign retry reconciliation contracts; no game database needed."""
import pytest

from workbench.server_admin.auction_house.reward_campaigns import retry_integrity


def campaign(status="partial", rows=None, expected=2):
    return {
        "overall_status": status,
        "recipient_count": expected,
        "recipients": rows if rows is not None else [
            {"char_id": 101, "status": "committed"},
            {"char_id": 102, "status": "failed"},
        ],
    }


def test_partial_campaign_retries_only_failed_recipient():
    result = retry_integrity(campaign())
    assert result["safe_retry_preview"] is True
    assert result["retry_character_ids"] == [102]
    assert result["committed_recipients"] == 1
    assert result["unknown_recipients"] == 0


@pytest.mark.parametrize("scenario,issue", [
    (campaign(expected=3), "recipient_outcomes_incomplete"),
    (campaign(rows=[{"char_id": 101, "status": "committed"}, {"char_id": 102, "status": "unknown"}]), "recipient_status_unknown"),
    (campaign(rows=[{"char_id": 101, "status": "committed"}, {"char_id": 101, "status": "failed"}]), "recipient_identity_invalid"),
    (campaign(status="completed"), "campaign_status_inconsistent"),
])
def test_unsafe_retry_sets_fail_closed(scenario, issue):
    result = retry_integrity(scenario)
    assert result["safe_retry_preview"] is False
    assert result["retry_character_ids"] == []
    assert issue in result["issues"]


def test_completed_campaign_has_no_retry_targets():
    result = retry_integrity(campaign(status="completed", rows=[
        {"char_id": 101, "status": "committed"}, {"char_id": 102, "status": "committed"},
    ]))
    assert result["issues"] == []
    assert not result["safe_retry_preview"]
