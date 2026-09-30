#!/usr/bin/env python3
"""Static regression for Zone Editor heading/compass/zoom UI contracts."""
from pathlib import Path


def main():
    template = (
        Path(__file__).resolve().parents[1]
        / "gui"
        / "templates"
        / "zone_plot.html"
    ).read_text(encoding="utf-8")

    # FFXI heading convention is intentionally east-indexed, not north-indexed.
    assert "0=East; values increase counter-clockwise (64=N, 128=W, 192=S)" in template
    assert "const ROT_DIRS=['E','NE','N','NW','W','SW','S','SE'];" in template
    assert "const bearing=(90-ffxiDeg+360)%360;" in template

    # Selected entities expose a real heading indicator and readable rotation details.
    assert "const headingArrow=new THREE.ArrowHelper" in template
    assert "updateHeadingArrow();" in template
    assert "rotText(e.r)" in template
    assert 'id="er-dir"' in template

    # World compass follows the projected world-North vector.
    assert 'id="map-compass"' in template
    assert 'id="compass-rose"' in template
    assert "add(new THREE.Vector3(0,0,25)).project(camera)" in template

    # Close zoom is deliberately finer than far-distance zoom.
    assert "d>300 ? 2.0" in template
    assert "d>8 ? 0.3 : 0.18" in template
    assert "renderer.domElement.addEventListener('wheel', ()=>{ updateZoomSpeed();" in template

    # First Zone Editor QOL priority stack.
    assert "const undoStack=[], redoStack=[];" in template
    assert "pre_restore_backup" in template
    for marker in (
        "recordUndo(`move/rotate ${e.id}`,j.backup)",
        "recordUndo(`animation ${e.id}`,j.backup)",
        "recordUndo(`delete ${e.id}`,j.backup)",
        "recordUndo(`add ${j.id}`,j.backup)",
        "recordUndo(`dropid ${dropsState.mobid}`,j.backup)",
        "recordUndo(`drop row ${dropsState.dropid}/${item_id}`,j.backup)",
        "recordUndo(`delete drop ${dropsState.dropid}/${origItem}`,j.backup)",
    ):
        assert marker.replace("\\`", "`") in template, marker

    assert "UNSAVED PREVIEW" in template
    assert "Discard unsaved position/rotation preview" in template
    assert "const selectionRing=new THREE.Mesh" in template
    assert "function frameSelected()" in template
    assert "selected-row" in template
    assert "ArrowLeft" in template and "PageUp" in template
    assert "rotateSelected" in template
    assert 'data-rpreset="64"' in template and 'data-rpreset="0"' in template
    assert "Ctrl+Z" in template and "Ctrl+Y" in template

    # Next Zone Editor QOL stacks: cameras/state, gizmo, SQL sync state, orthographic mode.
    assert "const perspectiveCamera = new THREE.PerspectiveCamera" in template
    assert "const orthoCamera = new THREE.OrthographicCamera" in template
    assert "function cameraPreset(name)" in template
    assert "ZONE_EDITOR_STATE_KEY='zoneEditor.ui.v1'" in template
    assert "localStorage.setItem" in template and "loadZoneEditorState()" in template
    assert 'data-cam="top"' in template and 'data-cam="north"' in template
    assert 'id="projection"' in template
    assert "camera.isOrthographicCamera" in template

    assert "TransformControls" in template
    assert "const transformProxy=new THREE.Object3D()" in template
    assert "transformControls.showX=mode==='translate'" in template
    assert "transformControls.showY=true" in template
    assert "transformControls.showZ=mode==='translate'" in template
    assert "e.r=Math.round(turns*256)%256" in template

    assert 'id="esyncstatus"' in template
    assert "const entitySyncState=new Map();" in template
    assert "Live DB: modified   SQL source: NOT SYNCED" in template
    assert "Live DB ✓   SQL source ✓" in template
    assert "markSqlSynced(lastTouched.k,lastTouched.id)" in template

    # Conservative multi-select / bulk transform workflow.
    assert "const multiSelected=new Set();" in template
    assert 'id="bulk-panel"' in template
    assert "Ctrl/Cmd-click dots or list rows to add/remove" in template
    assert "function toggleMultiSelect(i,fly=false)" in template
    assert "relative offsets only; relative spacing is preserved" in template
    assert "async function saveBulkTransform()" in template
    assert "fetch('/zoneplot/edit_bulk'" in template
    assert "recordUndo(`bulk transform ${j.count} entities`" in template
    assert 'id="bulk-sync"' in template
    assert "markSqlSynced(e.k,e.id)" in template

    zone_edit = (
        Path(__file__).resolve().parents[1]
        / "zone_edit.py"
    ).read_text(encoding="utf-8")
    gui_server = (
        Path(__file__).resolve().parents[1]
        / "gui_server.py"
    ).read_text(encoding="utf-8")
    nyzul_plot = (
        Path(__file__).resolve().parents[1]
        / "nyzul_plot.py"
    ).read_text(encoding="utf-8")
    zone_plot = (
        Path(__file__).resolve().parents[1]
        / "zone_plot.py"
    ).read_text(encoding="utf-8")
    assert "def update_positions_bulk(rows, comment=" in zone_edit
    assert "bulk transform is limited to 256 entities per action" in zone_edit
    assert "bulk transform must stay within one zone" in zone_edit
    assert "_save_backup(f\"bulk transform {len(normalized)} entities\"" in zone_edit
    assert '@app.post("/zoneplot/edit_bulk")' in gui_server

    # Entity discovery / navigation chunk.
    assert "renderer.domElement.addEventListener('dblclick'" in template
    assert "Double-click to select and frame" in template
    assert 'id="lf-kind"' in template
    assert 'id="lf-reach"' in template
    assert 'id="lf-sort"' in template
    assert 'id="lf-dir"' in template
    assert "function sortedMatches()" in template
    assert "Sort: Rotation" in template
    assert "Instance filter: all zone rows" in template
    assert "first 1000 shown" in template
    assert "grid-template-columns:34px 78px" in template

    # Orientation / snap / clipboard / measurement tools.
    assert 'id="labelHeading"' in template
    assert "Show heading on labels" in template
    assert 'id="faceDrag"' in template
    assert "function rotationTowardPoint(point)" in template
    assert "Math.atan2(-dz,dx)" in template
    assert 'id="snapGrid"' in template
    assert "function verticalSnapY(target)" in template
    assert "Snap Y to navmesh" in template and "Snap Y to visual floor" in template
    assert "let transformClipboard=null;" in template
    assert "Copy pos + rot" in template
    assert "Paste X/Z" in template and "Paste rotation" in template
    assert "let measureMode=false, measureStart=null;" in template
    assert "horizontal ${horizontal.toFixed(2)}" in template
    assert "bearing ${bearing.toFixed(1)}°" in template


    # Snap-to-selected and selected-entity history / restore.
    assert "Snap XYZ to other selected" in template
    assert "Snap Y to other selected" in template
    assert "function otherSelectedEntity()" in template
    assert 'id="ed-history"' in template
    assert "async function loadEntityHistory()" in template
    assert "async function restoreSelectedPrevious()" in template
    assert "fetch(`/zoneplot/history/${e.k}/${e.id}?limit=20`)" in template
    assert "fetch('/zoneplot/restore_entity_previous'" in template
    assert "recordUndo(`restore previous ${e.id}`" in template
    assert "def entity_history(kind, eid, limit=20):" in zone_edit
    assert "def restore_entity_previous(kind, eid):" in zone_edit
    assert "This deliberately does not restore the entire source backup" in zone_edit
    assert '@app.get("/zoneplot/history/{kind}/{eid}")' in gui_server
    assert '@app.post("/zoneplot/restore_entity_previous")' in gui_server


    # Explicit mob roam/spawn-leash radii: source-backed only, never inferred from engine defaults.
    assert "RADIUS_MOB_MODS" in zone_plot
    assert '31: ("roam_radius", "ROAM_DISTANCE")' in zone_plot
    assert '47: ("leash_radius", "SPAWN_LEASH")' in zone_plot
    assert "def _mob_radius_pool_values(cu, pool_ids):" in zone_plot
    assert "def _mob_radius_script_values(root: Path, zone_name: str, mob_name: str):" in zone_plot
    assert '"source": "mob_pool_mods"' in zone_plot
    assert '"source": "mob_script_literal"' in zone_plot
    assert "Nested conditional assignments are deliberately not promoted" in zone_plot
    assert 'id="showMobRadii"' in template
    assert 'id="ed-radius"' in template
    assert "const mobRadiusGroup=new THREE.Group()" in template
    assert "function updateMobRadiusVisuals()" in template
    assert "function radiusText(e)" in template
    assert "No explicit ROAM_DISTANCE or SPAWN_LEASH stored for this mob; engine/default behavior is not visualized." in template

    # Selection defaults back to Move mode and Help documents the editor surface.
    assert "if(typeof setGizmoMode==='function') setGizmoMode('translate');" in template
    assert '<button data-t="help" class="tabb">Help</button>' in template
    assert 'id="tab-help"' in template
    assert "Zone Editor help" in template
    assert "Transform shortcuts" in template
    assert "Client model preview" in template
    assert "Animation &amp; subanimation" in template

    # Model changes are preview/impact gated, backup-backed, and pool-aware for mobs.
    assert "def _flat_look_blob(model_id):" in zone_edit
    assert "def preview_model_change(kind, eid, model_id):" in zone_edit
    assert "def apply_model_change(kind, eid, model_id, comment=\"\"):" in zone_edit
    assert "def sync_model_sql(kind, eid, server=None):" in zone_edit
    assert '"mob_pools": ["poolid"]' in zone_edit
    assert "shared-mob-pool" in zone_edit
    assert "/zoneplot/model/preview" in gui_server
    assert "/zoneplot/model/apply" in gui_server
    assert "/zoneplot/model/sync_sql" in gui_server
    assert 'id="modelImpactBtn"' in template
    assert 'id="modelApplyBtn"' in template
    assert "async function checkModelImpact()" in template
    assert "async function applySelectedModel()" in template
    assert "Selection/candidate changed. Check impact again." in template

    # Animation metadata comes from current bundled LSB sources, with subanimation evidence.
    assert "/zoneplot/animation-meta.json" in gui_server
    assert "loadAnimationMetadata()" in template
    assert "renderAnimationEvidence()" in template
    assert "Transient FOURCC animation reference" in template

    # Nav diagnostics / elevation / persistent door orientation.
    assert 'id="navdiag"' in template
    assert 'id="navdiagOut"' in template
    assert "async function loadSelectedNavDiag()" in template
    assert "selectedNavDiag.placement_valid?0x55dd88:0xff4d4d" in template
    assert '<option value="height">Elevation</option>' in template
    assert "let heightRange={lo:0,hi:0};" in template
    assert "Door/prop facing ticks" in template
    assert "let doorFacingLines=null;" in template
    assert "if(e.k!=='d') continue" in template
    assert "def point_diagnostics(x, y, z, path=None):" in nyzul_plot
    assert "def nav_diagnostics(zid, x, y, z, server=None):" in zone_plot
    assert '@app.get("/zoneplot/{zid}/navdiag.json")' in gui_server

    # Add workflow: clone selected, repeat placement, richer ghost.
    assert 'id="cloneSelectedBtn"' in template
    assert 'id="repeatAdd"' in template
    assert 'id="addGhostInfo"' in template
    assert "const addHeadingLine=new THREE.Line" in template
    assert "const addGhostLabel=new CSS2DObject" in template
    assert "aSel=kind==='m' ? {groupid:e.gid" in template
    assert "Repeated placement active: source/rotation/instance retained" in template
    assert '"gid": int(gid)' in zone_plot

    # Nav diagnostics / elevation / persistent door orientation.
    assert 'id="navdiag"' in template
    assert 'id="navdiagOut"' in template
    assert "async function loadSelectedNavDiag()" in template
    assert "navdiag.json?x=${encodeURIComponent(e.x)}" in template
    assert "placement_valid" in template
    assert "selectedNavDiag.placement_valid?0x55dd88:0xff4d4d" in template
    assert '<option value="height">Elevation</option>' in template
    assert "let heightRange={lo:0,hi:0};" in template
    assert "Door/prop facing ticks" in template
    assert "let doorFacingLines=null;" in template
    assert "if(e.k!=='d') continue" in template
    assert "def point_diagnostics(x, y, z, path=None):" in nyzul_plot
    assert "def nav_diagnostics(zid, x, y, z, server=None):" in zone_plot
    assert '@app.get("/zoneplot/{zid}/navdiag.json")' in gui_server
    print("Zone Plot heading/compass/zoom UI regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
