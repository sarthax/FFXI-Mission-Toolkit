"""Live entity search and freshness requirements for the existing Zone 3D inspector."""
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")

def test_entity_search_reuses_inspector_and_existing_markers():
    for text in ("id=\"ashita-entity-search\"", "liveEntityMatchesFilter",
                 "liveEntitySearch.addEventListener('input'",
                 "updateLiveEntityPicker()", "updateLiveEntityVisibility()",
                 "function inspectEntity(entity)"):
        assert text in HTML

def test_freshness_is_explicit_and_stale_markers_hidden():
    assert "Date.now() / 1000 - Number(entity.observed_at)" in HTML
    assert "liveEntityAgeSeconds(entity) > 3" in HTML
    assert "marker.visible = Boolean(entity && liveEntityMatchesFilter(entity) && !isStale)" in HTML
    assert "stale hidden" in HTML
    assert "Observation age: " in HTML

def test_identity_does_not_fallback_to_client_slot_for_server_links():
    assert "id: entity.server_entity_id ?? null, k: 'c', live_observation: true" in HTML
    assert "const id = String(entity.live_observation ? (entity.server_entity_id ?? '')" in HTML
