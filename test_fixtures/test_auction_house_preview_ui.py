from pathlib import Path


def test_auction_house_preview_ui_is_explicitly_non_writing():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_admin.js").read_text(encoding="utf-8")

    assert "PREVIEW ONLY" in template
    assert "NO WRITES" in template
    assert "ahListPreviewForm" in template
    assert "ahPurchasePreviewForm" in template
    assert "/auction-house/admin/list/preview.json" in script
    assert "/auction-house/admin/purchase/preview.json" in script
    assert "/apply" not in script
    assert "/commit" not in script
    assert "apply_supported" in script


if __name__ == "__main__":
    test_auction_house_preview_ui_is_explicitly_non_writing()
    print("Auction House preview UI regression: PASS")
