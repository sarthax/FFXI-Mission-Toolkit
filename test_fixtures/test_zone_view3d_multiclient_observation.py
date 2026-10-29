from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_secondary_client_tracking_is_read_only_and_bounded():
    Environment().parse(SOURCE)
    assert 'id="ashita-other-clients"' in SOURCE
    assert 'id="ashita-telemetry-health"' in SOURCE
    assert "function clearOtherClientMarkers()" in SOURCE
    assert "async function refreshOtherClientMarkers()" in SOURCE
    assert "slice(0, 12)" in SOURCE
    assert "Promise.allSettled" in SOURCE
    assert "generation !== secondaryPollGeneration" in SOURCE
    assert "data?.visible" in SOURCE
    assert "scene.remove(marker); marker.geometry.dispose(); marker.material.dispose();" in SOURCE
    assert "setInterval(refreshOtherClientMarkers, 2000)" in SOURCE
    assert "'Bridge ' + roundTripMs + ' ms" in SOURCE
