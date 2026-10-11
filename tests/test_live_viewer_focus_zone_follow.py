"""Focused regression for live 3D viewer direction and cross-zone following."""
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_heading_direction_uses_scene_positive_z_for_increasing_angle():
    html = VIEWER.read_text(encoding="utf-8")
    assert "Math.sin(position.heading + Number(liveHeading.value) * Math.PI / 180)" in html
    assert "-Math.sin(position.heading + Number(liveHeading.value) * Math.PI / 180)" not in html


def test_focus_enables_follow_and_zone_navigation_persists_follow():
    html = VIEWER.read_text(encoding="utf-8")
    focus = html.split("document.getElementById('ashita-live-focus').addEventListener", 1)[1].split("});", 1)[0]
    assert "liveFollowToggle.checked = true;" in focus
    assert "liveAutoZoneToggle.checked = true;" in focus
    assert "follow:liveFollowToggle.checked?'1':'0'" in html
    assert "liveFollowToggle.checked = liveQuery.get('follow') === '1';" in html
    assert "if (liveAutoZoneToggle.checked || liveFollowToggle.checked) await checkLiveZone(clientId, requestId);" in html
