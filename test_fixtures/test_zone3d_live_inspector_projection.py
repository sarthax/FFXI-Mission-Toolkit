"""Regression guards for live entity pick/focus axis projection and inspector labels."""
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_live_inspector_projection_contract():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "flyTo(liveHit.object.getWorldPosition(new THREE.Vector3()))" in text
    assert "flyTo(selectedEntity.live_observation ? projectLivePoint(selectedEntity) :" in text
    assert "const liveServer = {x: projected.x, y: -projected.y, z: -projected.z};" in text
    assert "return String(e.server_entity_id ?? ('slot:' + e.client_index));" in text
    assert 'id="zone3d-inspector-source"' in text
    assert "LIVE OBSERVATION · Ashita bridge" in text
    assert "MAP COMPARISON · loaded zone records" in text
