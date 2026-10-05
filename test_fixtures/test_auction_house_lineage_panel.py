from pathlib import Path


def test_lineage_semantics_panel_is_visible_and_preserves_existing_admin_surface():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")

    assert 'id="ahLineageSemantics"' in template
    assert "/auction-house/lineage-semantics.json" in template
    assert "SEMANTICS GATE PASSED" in template
    assert "SOURCE VERIFIED · EXECUTION BLOCKED" in template
    assert "SCOPED TEST WRITES" in template
    assert "READ + SCOPED TEST WRITE" in template
    assert "PREVIEW ONLY" not in template
    assert "NO EXECUTOR" not in template

    # Guard against accidentally replacing the economy-health/admin UI while
    # layering the lineage gate and consolidated capability surface onto the page.
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
        '{% include "_auction_house_nav.html" %}',
    ):
        assert marker in template


def test_lineage_panel_does_not_add_unrestricted_write_routes():
    template = Path("gui/templates/auction_house.html").read_text(encoding="utf-8")

    # The overview remains preview/validation-only; scoped Test execution lives on
    # dedicated module pages and must not become a generic apply/commit surface here.
    for forbidden in (
        "fetch('/auction-house/apply",
        'fetch("/auction-house/apply',
        "fetch('/auction-house/commit",
        'fetch("/auction-house/commit',
        'action="/auction-house/apply',
        'action="/auction-house/commit',
    ):
        assert forbidden not in template
    assert "fetch('/auction-house/lineage-semantics.json'" in template
    assert "Unrestricted and Live writes remain disabled" in template


if __name__ == "__main__":
    test_lineage_semantics_panel_is_visible_and_preserves_existing_admin_surface()
    test_lineage_panel_does_not_add_unrestricted_write_routes()
    print("Auction House lineage semantics panel regression: PASS")
