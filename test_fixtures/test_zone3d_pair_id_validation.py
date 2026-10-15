"""Pairing must accept numerical IDs and use same source as map comparison."""
from pathlib import Path

VIEW = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_pairing_numeric_ids_and_full_zone_data():
    src = VIEW.read_text(encoding="utf-8")
    section = src.split("function pairEntityId(e) {", 1)[1].split("function updateEntityPair()", 1)[0]
    assert r"!/^\d+$/.test(String(raw))" in section
    assert r"!/^\\d+$/.test(String(raw))" not in section
    pair = src.split("function updateEntityPair() {", 1)[1].split("function inspectEntity(entity)", 1)[0]
    assert "spawnEntitiesAll.filter(e => pairEntityId(e) === id)" in pair
    assert "const b = projectLivePoint(live);" in pair
    assert "no matching record in loaded zone data" in pair
