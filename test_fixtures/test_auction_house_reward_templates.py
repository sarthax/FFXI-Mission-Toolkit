from pathlib import Path

import pytest

from workbench.server_admin.auction_house.reward_templates import (
    RewardTemplateError,
    delete_reward_template,
    get_reward_template,
    list_reward_templates,
    save_reward_template,
)


def test_reward_template_round_trip(tmp_path: Path):
    db = tmp_path / "rewards.db"
    row = save_reward_template(name="Launch", items=[{"item_id": 100, "quantity": 2}], path=db)
    assert row["items"] == [{"item_id": 100, "quantity": 2}]
    assert get_reward_template(row["template_id"], path=db)["name"] == "Launch"
    assert len(list_reward_templates(path=db)) == 1
    assert "confirmation" not in row
    assert "preview_token" not in row
    assert delete_reward_template(row["template_id"], path=db) is True


def test_reward_template_rejects_duplicate_items_and_too_many_rows(tmp_path: Path):
    db = tmp_path / "rewards.db"
    with pytest.raises(RewardTemplateError, match="Duplicate"):
        save_reward_template(
            name="Bad",
            items=[{"item_id": 100, "quantity": 1}, {"item_id": 100, "quantity": 2}],
            path=db,
        )
    with pytest.raises(RewardTemplateError, match="at most 20"):
        save_reward_template(
            name="Too many",
            items=[{"item_id": i + 1, "quantity": 1} for i in range(21)],
            path=db,
        )


def test_reward_routes_and_ui_are_mounted():
    integration = Path("src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    template = Path("gui/templates/auction_house_rewards.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_rewards.js").read_text(encoding="utf-8")
    assert "auction_house_reward_api_router" in integration
    assert "auction_house_reward_ui_router" in integration
    assert '"AH Rewards"' in integration
    assert "/auction-house/rewards" in integration
    assert "/auction-house/rewards/preview.json" in script
    assert "/auction-house/rewards/execute.json" in script
    assert "fresh preview" in template
