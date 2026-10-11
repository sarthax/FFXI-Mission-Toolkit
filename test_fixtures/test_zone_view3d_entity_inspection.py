from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_entity_inspection_read_only_panel_and_grounded_link():
    source = VIEWER.read_text(encoding="utf-8")
    for element in ("zone3d-entity-inspector", "zone3d-inspector-content",
                    "zone3d-inspector-links", "zone3d-inspector-close"):
        assert f'id="{element}"' in source
    assert "function inspectEntity(entity)" in source
    assert "entityInspectorContent.textContent = lines.join" in source
    assert "link.href = '/entity/' + encodeURIComponent(id)" in source
    assert "inspectEntity(spawnEntities[hoveredSpawnId])" in source
    assert "inspectEntity(entity);" in source
    assert "selectedEntity = null" in source
    assert "entityInspectorLinks.replaceChildren()" in source
