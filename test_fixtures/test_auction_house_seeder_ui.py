from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_seeder_page_route_and_workspace_mount():
    route = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "seeder_ui.py").read_text(encoding="utf-8")
    bridge = (ROOT / "src" / "workbench" / "server_admin" / "auction_house" / "integration.py").read_text(encoding="utf-8")
    assert '@router.get("/auction-house/seeder"' in route
    assert "auction_house_seeder.html" in route
    assert "auction_house_seeder_ui_router" in bridge
    assert '("AH Seeder", "/auction-house/seeder", "/auction-house/listing-manager")' in bridge


def test_seeder_template_exposes_both_listing_modes():
    template = (ROOT / "gui" / "templates" / "auction_house_seeder.html").read_text(encoding="utf-8")
    assert "Player-backed listing" in template
    assert "Synthetic category seeding" in template
    assert 'id="seedPlayerReadiness"' in template
    assert 'id="seedPlayerPost"' in template
    assert 'id="seedSyntheticPreview"' in template
    assert 'id="seedSyntheticExecute"' in template
    assert "/static/auction_house_seeder.js" in template


def test_seeder_script_uses_guarded_existing_endpoints_and_stale_preview_check():
    script = (ROOT / "gui" / "static" / "auction_house_seeder.js").read_text(encoding="utf-8")
    assert "/auction-house/test-write/player-listing-readiness.json" in script
    assert "/auction-house/test-write/player-listing.json" in script
    assert "/auction-house/test-write/synthetic-category-preview.json" in script
    assert "/auction-house/test-write/synthetic-category-seed.json" in script
    assert "Inputs changed after preview" in script
    assert "confirmation" in script
    assert "payload.get(\"sql\")" not in script
