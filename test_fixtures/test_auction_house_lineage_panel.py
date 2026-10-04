from pathlib import Path


def test_lineage_semantics_panel_is_visible_and_preserves_existing_admin_surface():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")

    assert 'id="ahLineageSemantics"' in template
    assert "/auction-house/lineage-semantics.json" in template
    assert "SEMANTICS GATE PASSED" in template
    assert "SOURCE VERIFIED · EXECUTION BLOCKED" in template
    assert "NO EXECUTOR" in template
    assert "PREVIEW ONLY" in template

    # Guard against accidentally replacing the newer economy-health/admin UI while
    # layering the lineage gate onto the page.
    for marker in (
        'id="ahHealth"',
        'id="ahHealthSummary"',
        'id="ahHealthStale"',
        'id="ahHealthMovement"',
        'id="ahHealthConcentration"',
        'id="ahHealthOutliers"',
        'id="ahListPreviewForm"',
        'id="ahPurchasePreviewForm"',
        'src="/static/auction_house_admin.js"',
    ):
        assert marker in template


def test_lineage_panel_does_not_add_write_routes():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")

    assert "/apply" not in template
    assert "/commit" not in template
    assert "fetch('/auction-house/lineage-semantics.json'" in template


if __name__ == "__main__":
    test_lineage_semantics_panel_is_visible_and_preserves_existing_admin_surface()
    test_lineage_panel_does_not_add_write_routes()
    print("Auction House lineage semantics panel regression: PASS")
