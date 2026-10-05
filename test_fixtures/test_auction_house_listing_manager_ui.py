from pathlib import Path


def test_listing_manager_ui_contract():
    template = Path("gui/templates/auction_house_listing_manager.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_listing_manager.js").read_text(encoding="utf-8")
    integration = Path("src/workbench/server_admin/auction_house/integration.py").read_text(encoding="utf-8")

    for text in ("Seller ID", "Seller name", "Category", "Item ID", "Load listings"):
        assert text in template
    assert "/static/auction_house_listing_manager.js" in template
    assert "/auction-house/listings.json" in script
    assert "/auction-house/test-write/admin-buy.json" in script
    assert "/auction-house/test-write/return-to-seller.json" in script
    assert "/auction-house/admin/purchase/preview.json" in script
    assert "AH Listing Manager" in integration
    assert "/auction-house/listing-manager" in integration
