from pathlib import Path


TEMPLATES = [
    "auction_house.html",
    "auction_house_listing_manager.html",
    "auction_house_seeder.html",
    "auction_house_cleanup.html",
    "auction_house_presets.html",
    "auction_house_economy.html",
    "auction_house_rewards.html",
    "auction_house_reward_history.html",
    "auction_house_activity.html",
    "auction_house_help.html",
]


def test_major_auction_house_pages_use_shared_navigation_and_status():
    root = Path("gui/templates")
    for name in TEMPLATES:
        text = (root / name).read_text(encoding="utf-8")
        assert '{% include "_auction_house_nav.html" %}' in text, name

    partial = (root / "_auction_house_nav.html").read_text(encoding="utf-8")
    for href in (
        "/auction-house",
        "/auction-house/listing-manager",
        "/auction-house/seeder",
        "/auction-house/cleanup",
        "/auction-house/presets",
        "/auction-house/economy",
        "/auction-house/rewards",
        "/auction-house/reward-history",
        "/auction-house/activity",
        "/auction-house/help",
    ):
        assert f'href="{href}"' in partial
    assert "data-ah-shared-status" in partial


def test_overview_no_longer_claims_preview_only_or_no_executor():
    text = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")
    upper = text.upper()
    assert "PREVIEW ONLY" not in upper
    assert "NO EXECUTOR" not in upper
    assert "EXECUTION REMAINS DISABLED" not in upper
    assert "SCOPED TEST WRITES" in upper
    assert "UNRESTRICTED AND LIVE WRITES REMAIN DISABLED" in upper


def test_shared_status_uses_non_conflicting_capability_endpoint_and_normalizes_legacy_wording():
    status = Path("src/workbench/server_admin/auction_house/status_ui.py").read_text(encoding="utf-8")
    common = Path("gui/static/auction_house_common.js").read_text(encoding="utf-8")
    assert '@router.get("/auction-house/capability-status.json")' in status
    assert '@router.get("/auction-house/status.json")' not in status
    assert "/auction-house/capability-status.json" in common
    assert "Global executor:" in common
    assert "Scoped DSP/Topaz Test executors:" in common
    assert "MyISAM" in common


def test_help_route_and_workspace_entry_are_mounted():
    integration = Path("src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")
    status = Path("src/workbench/server_admin/auction_house/status_ui.py").read_text(encoding="utf-8")
    help_template = Path("gui/templates/auction_house_help.html").read_text(encoding="utf-8")
    assert "auction_house_status_router" in integration
    assert '"AH Help / Status", "/auction-house/help"' in integration
    assert '@router.get("/auction-house/help"' in status
    assert "Scoped DSP/Topaz Test writes" in help_template or "DSP/Topaz <strong>Test-environment</strong> executors" in help_template
    assert "Live writes" in help_template
    assert "MyISAM" in help_template
    assert "LSB writes" in help_template


def test_authoritative_capability_doc_exists_and_states_boundaries():
    text = Path("docs/workbench/AUCTION_HOUSE_CAPABILITY_STATUS.md").read_text(encoding="utf-8")
    assert "authoritative operator summary" in text
    assert "Scoped DSP/Topaz Test writes" in text
    assert "MyISAM" in text
    assert "Live writes remain blocked" in text
    assert "LSB execution should remain deferred" in text
