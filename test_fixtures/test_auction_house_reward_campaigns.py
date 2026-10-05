from pathlib import Path

from workbench.server_admin.auction_house.reward_campaigns import (
    failed_recipient_ids,
    get_campaign,
    list_campaigns,
    record_campaign,
)


def test_reward_campaign_round_trip_and_failed_selection(tmp_path: Path):
    db = tmp_path / "campaigns.db"
    campaign = record_campaign(
        environment={"name": "DSP Test", "family": "dsp", "kind": "test"},
        template={"template_id": "tpl-1", "name": "Welcome"},
        items=[{"item_id": 4096, "quantity": 1}],
        recipient_mode="selected",
        recipient_count=2,
        preview_id="preview-1",
        replay_id="replay-1",
        result={
            "status": "partial",
            "results": [
                {"char_id": 1, "char_name": "Alpha", "status": "committed", "rows": 1},
                {"char_id": 2, "char_name": "Beta", "status": "failed", "error": "mailbox blocked"},
            ],
        },
        path=db,
    )
    assert campaign["overall_status"] == "partial"
    assert campaign["completed_count"] == 1
    assert campaign["failed_count"] == 1
    assert failed_recipient_ids(campaign["campaign_id"], path=db) == [2]
    detail = get_campaign(campaign["campaign_id"], path=db)
    assert detail["items"] == [{"item_id": 4096, "quantity": 1}]
    assert detail["template_name"] == "Welcome"
    rows = list_campaigns(status="partial", template_id="tpl-1", path=db)
    assert [row["campaign_id"] for row in rows] == [campaign["campaign_id"]]


def test_reward_campaign_list_is_bounded(tmp_path: Path):
    db = tmp_path / "campaigns.db"
    for index in range(3):
        record_campaign(
            environment={"name": "Topaz Test"}, template=None,
            items=[{"item_id": 100 + index, "quantity": 1}],
            recipient_mode="selected", recipient_count=1,
            preview_id=f"p{index}", replay_id=f"r{index}",
            result={"status": "completed", "results": [{"char_id": index + 1, "char_name": "C", "status": "committed", "rows": 1}]},
            path=db,
        )
    assert len(list_campaigns(limit=2, path=db)) == 2
