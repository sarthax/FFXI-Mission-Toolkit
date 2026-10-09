"""Guard the opt-in 3D live marker integration without requiring browser graphics."""
from pathlib import Path


def test_zone_viewer_live_overlay_is_opt_in_and_uses_safe_projection():
    path = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"
    content = path.read_text(encoding="utf-8")
    assert 'id="ashita-live-toggle" type="checkbox"' in content
    assert "if (!liveToggle.checked) { clearLiveMarker();" in content
    assert "/live-client/bridge/projection?client_id=" in content
    assert "&zone_id=' + ZONEID" in content
    assert "if (!data.visible || !data.player || !data.player.position)" in content
    assert "clearLiveMarker(); liveStatus.textContent = 'No fresh matching-zone telemetry'" in content
    assert "liveMarker.position.set(position.x, position.z, -position.y)" in content
    assert "setInterval(pollAshitaPosition, 1500)" in content
    assert "fetch('/live-client/bridge/clients')" in content
