"""Guard the opt-in 3D live marker integration without requiring browser graphics."""
from pathlib import Path


def test_zone_viewer_live_overlay_is_opt_in_and_uses_safe_projection():
    path = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"
    content = path.read_text(encoding="utf-8")
    assert 'id="ashita-live-toggle" type="checkbox"' in content
    assert "if (!liveToggle.checked) { clearLiveMarker();" in content
    assert "/live-client/bridge/projection?client_id=" in content
    assert "&zone_id=' + ZONEID" in content
    assert "if (!data.visible || !data.player || !data.player.position)" in content
    assert "liveStatus.textContent = 'No fresh matching-zone telemetry'" in content
    assert "if (liveAutoZoneToggle.checked) await checkLiveZone(clientId, requestId)" in content
    assert "const current = projectLivePoint(position)" in content
    assert "liveMarker.position.copy(current)" in content
    assert "setInterval(pollAshitaPosition, 1500)" in content
    assert "fetch('/live-client/bridge/clients')" in content


def test_zone_viewer_live_heading_entities_and_follow_are_opt_in():
    path = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"
    content = path.read_text(encoding="utf-8")
    assert 'id="ashita-live-entities" type="checkbox"' in content
    assert 'id="ashita-live-follow" type="checkbox"' in content
    assert "liveEntitiesToggle.checked && Array.isArray(data.entities)" in content
    assert "data.entities.slice(0, 100)" in content
    assert "Number.isFinite(position.heading)" in content
    assert "liveFollowToggle.checked && !flyModeOn && previous" in content
    assert "clearLiveEntities();" in content
    assert "requestId !== lastLiveRequest" in content


def test_live_entity_pool_reuses_geometry_and_cleans_heading():
    path = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"
    content = path.read_text(encoding="utf-8")
    assert "const liveEntityPool = []" in content
    assert "const liveEntityGeometry = new THREE.SphereGeometry" in content
    assert "let marker = liveEntityPool[entityCount]" in content
    assert "marker.visible = true" in content
    assert "for (const child of liveEntityPool) child.visible = false" in content
    assert "arrow.line.geometry.dispose()" in content
    assert "arrow.cone.geometry.dispose()" in content
    assert "data.entities_truncated" in content


def test_live_alignment_controls_require_fresh_observation_and_report_transform():
    content = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")
    assert 'id="ashita-live-focus"' in content
    assert 'id="ashita-live-copy"' in content
    assert 'href="/live-client/bridge/console"' in content
    assert "if (!liveToggle.checked || !lastLivePosition || flyModeOn)" in content
    assert "controls.target.copy(lastLivePosition)" in content
    assert "raw_position: {x:position.x,y:position.y,z:position.z,heading:position.heading}" in content
    assert "viewer_position: {x:current.x,y:current.y,z:current.z}" in content
    assert "await navigator.clipboard.writeText(JSON.stringify(lastLiveDiagnostic, null, 2))" in content
    assert "lastLiveDiagnostic = null" in content


def test_axis_preview_is_explicit_and_applies_to_entities():
    content = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")
    assert 'id="ashita-live-axes"' in content
    assert "function projectLivePoint(p)" in content
    assert "marker.position.copy(projectLivePoint(point))" in content
    assert "axis_preview: liveAxes.value" in content
    assert "liveAxes.addEventListener('change'" in content


def test_opt_in_auto_zone_navigation_requires_fresh_same_client_status():
    content = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")
    assert 'id="ashita-live-autozone" type="checkbox"' in content
    assert "liveAutoZoneToggle.checked" in content
    assert "status.connected || !status.snapshot" in content
    assert "requestId !== lastLiveRequest" in content
    assert "zone === ZONEID" in content
    assert "Number.isInteger(zone)" in content
    assert "location.assign('/zones/' + zone + '/view3d?'" in content
    assert "liveQuery.get('live') === '1'" in content
    assert "new URLSearchParams({live:'1',client:clientId,autozone:'1',axes:liveAxes.value,heading:liveHeading.value})" in content


def test_axis_and_heading_previews_survive_opt_in_zone_navigation():
    content = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")
    assert "const liveAxisOptions = new Set(['legacy','xyz','xzy','x-z-y'])" in content
    assert "liveAxisOptions.has(liveQuery.get('axes'))" in content
    assert "['0','90','180','270'].includes(liveQuery.get('heading'))" in content
    assert "axes:liveAxes.value,heading:liveHeading.value" in content
    assert 'id="ashita-live-heading"' in content
    assert "heading_preview_degrees: Number(liveHeading.value)" in content
    assert "liveHeading.addEventListener('change', pollAshitaPosition)" in content
