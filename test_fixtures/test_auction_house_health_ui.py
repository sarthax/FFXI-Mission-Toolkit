from pathlib import Path


def test_auction_house_health_ui_wires_read_only_diagnostics():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")
    script = Path("gui/static/auction_house_admin.js").read_text(encoding="utf-8")

    assert "Economy health" in template
    assert "ahHealth" in template
    assert "Stale listings" in template
    assert "Price / volume movement" in template
    assert "Participant concentration" in template
    assert "Transaction outliers" in template
    assert "/auction-house/health.json" in script
    assert "renderHealth" in script
    assert "/apply" not in script
    assert "/commit" not in script


if __name__ == "__main__":
    test_auction_house_health_ui_wires_read_only_diagnostics()
    print("Auction House health UI regression: PASS")
