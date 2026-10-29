"""Zone correlation works from exact IDs and retains coverage uncertainty."""
from pathlib import Path

VIEW = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_zone_correlation_contract():
    js = VIEW.read_text(encoding="utf-8")
    assert 'id="zone3d-correlation-summary"' in js
    assert 'id="zone3d-correlation-filter"' in js
    assert 'id="zone3d-correlation-threshold"' in js
    assert "const id = pairEntityId(e);" in js
    assert "if (liveEntityAgeSeconds(e) > 3) continue;" in js
    assert "new THREE.Vector3(m.x,-m.y,-m.z).distanceTo(projectLivePoint(l))" in js
    assert "kind = 'live_only'" in js
    assert "kind = 'server_only'" in js
    assert "kind = 'ambiguous'" in js
    assert "? 'displaced' : 'paired'" in js
    assert "const fresh = zoneCorrelationRows().find(" in js
    assert "if (fresh?.entity) inspectEntity(fresh.entity)" in js
