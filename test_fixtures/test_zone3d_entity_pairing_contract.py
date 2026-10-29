"""Pairing must use reported server IDs and distinguish absence from proof of despawn."""
from pathlib import Path

VIEW = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_entity_pairing_contract():
    text = VIEW.read_text(encoding="utf-8")
    assert 'id="zone3d-pair-status"' in text
    assert "e?.live_observation ? e.server_entity_id : e?.id" in text
    assert "liveEntityAgeSeconds(e) <= 3" in text
    assert "const b = projectLivePoint(live);" in text
    assert "pairLineGeometry.setFromPoints([a,b]);" in text
    assert "pairLine.visible = false;" in text
    assert "updateEntityPair();" in text
    assert "no fresh Ashita observation" in text
    assert "no matching record in loaded zone data" in text
    assert "Ambiguous ID " in text
