from pathlib import Path


def test_auction_house_preview_ui_remains_preview_validation_only():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_admin.js").read_text(encoding="utf-8")

    assert "PREVIEW / VALIDATE" in template
    assert "preview/validation surfaces" in template
    assert "dedicated Listings, Seeder, Cleanup, or Rewards pages" in template
    assert "ahListPreviewForm" in template
    assert "ahPurchasePreviewForm" in template
    assert "/auction-house/admin/list/preview.json" in script
    assert "/auction-house/admin/purchase/preview.json" in script
    assert "/apply" not in script
    assert "/commit" not in script
    assert "apply_supported" in script
    assert "PREVIEW ONLY" not in template


if __name__ == "__main__":
    test_auction_house_preview_ui_remains_preview_validation_only()
    print("Auction House preview UI regression: PASS")
