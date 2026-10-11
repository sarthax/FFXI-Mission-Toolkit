from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_secondary_client_heading_and_focus_controls():
    Environment().parse(SOURCE)
    for element_id in ("ashita-secondary-client", "ashita-secondary-focus",
                       "ashita-secondary-follow", "ashita-secondary-detail"):
        assert f'id="{element_id}"' in SOURCE
    assert "new THREE.ArrowHelper" in SOURCE
    assert "secondaryPositions.set(id" in SOURCE
    assert "function disposeSecondaryMarker(marker)" in SOURCE
    assert "arrow.line.geometry.dispose()" in SOURCE
    assert "secondaryFollow.checked && selected && !flyModeOn" in SOURCE
    assert "if (secondaryFollow.checked) liveFollowToggle.checked = false" in SOURCE
    assert "const current = projectLivePoint(selected)" in SOURCE
