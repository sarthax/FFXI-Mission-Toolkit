from pathlib import Path

VIEWER = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_live_slot_is_not_a_server_identity():
    assert "id: entity.server_entity_id ?? null, k: 'c', live_observation: true" in VIEWER
    assert "slot:' + e.client_index" in VIEWER
    assert "entity.live_observation ? (entity.server_entity_id ?? '') : (entity.id ?? '')" in VIEWER
    assert "entity.live_observation ? entity.server_entity_id : entity.id" in VIEWER

def test_inspector_reuses_existing_panel_for_exact_id_comparison():
    assert "function inspectEntity(entity)" in VIEWER
    assert "inspectEntity(entity);" in VIEWER
    assert "spawnEntities.filter(e => String(e.id ?? '') === String(entity.server_entity_id))" in VIEWER
    assert "matches.length === 1" in VIEWER
    assert "ambiguous (" in VIEWER
    assert "movement may be expected" in VIEWER
    assert "Configured XYZ:" in VIEWER

def test_live_observation_provenance_is_visible():
    for label in ("Client slot:", "Reported server entity ID:", "Source client:", "Last observed:", "Heading:", "Raw status:"):
        assert label in VIEWER
