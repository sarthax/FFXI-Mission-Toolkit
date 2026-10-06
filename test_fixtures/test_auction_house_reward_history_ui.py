from pathlib import Path


def test_reward_history_routes_and_ui_are_mounted():
    integration = Path("src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    api = Path("src/workbench/server_admin/auction_house/reward_history_api.py").read_text(encoding="utf-8")
    template = Path("gui/templates/auction_house_reward_history.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_reward_history.js").read_text(encoding="utf-8")
    console = Path("gui/static/auction_house_console.js").read_text(encoding="utf-8")
    assert "auction_house_reward_history_api_router" in integration
    assert "auction_house_reward_history_ui_router" in integration
    assert "/auction-house/reward-history" in console
    assert "retry-preview.json" in api
    assert "failed recipients only" in template.lower()
    assert "Preview failed-recipient retry" in script
    assert "/auction-house/reward-history" in script
