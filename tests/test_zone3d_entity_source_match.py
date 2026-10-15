from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_comparison_uses_complete_loaded_data():
    assert "spawnEntitiesAll.filter(e => String(e.id ?? '') === String(entity.server_entity_id))" in HTML
    assert "spawnEntities.filter(e => String(e.id ?? '') === String(entity.server_entity_id))" not in HTML

def test_source_provenance_is_distinct():
    assert "const mapSourceIsCapture = Boolean(CAPTURE_SPATIAL_URL)" in HTML
    assert "Capture map observation: " in HTML
    assert "Server zone-data record: " in HTML
    assert "Capture-recorded XYZ: " in HTML
    assert "Map-record XYZ: " in HTML
    assert "identity not independently verified" in HTML
    assert "not automatically a data error" in HTML

def test_unresolved_identity_explicit():
    assert "Match unavailable: no reported server ID" in HTML
    assert "ambiguous (" in HTML
