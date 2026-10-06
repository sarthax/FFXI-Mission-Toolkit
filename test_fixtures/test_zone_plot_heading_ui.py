#!/usr/bin/env python3
"""Static regression for Zone Editor heading/compass/zoom UI contracts."""
from pathlib import Path


def main():
    template = (
        Path(__file__).resolve().parents[1]
        / "gui"
        / "templates"
        / "zone_plot2.html"
    ).read_text(encoding="utf-8")

    assert "0=East; values increase counter-clockwise (64=N, 128=W, 192=S)" in template
    assert "ROT_DIRS" in template and "'E'" in template and "'NE'" in template and "'N'" in template and "'NW'" in template
    assert "const bearing=(90+ffxiDeg)%360;" in template
    assert "const headingArrow=new THREE.ArrowHelper" in template
    assert "updateHeadingArrow();" in template
    assert "rotText(e.r)" in template
    assert 'id="er-dir"' in template
    assert 'id="map-compass"' in template
    assert 'id="compass-rose"' in template
    assert "add(new THREE.Vector3(0,0,-25)).project(camera)" in template
    assert "controls.zoomSpeed=(1.4+2.6*far)*mult;" in template
    assert "controls.minDistance=0.05;" in template
    assert "renderer.domElement.addEventListener('wheel', ev=>{ ev.preventDefault(); updateZoomSpeed(" in template

    assert "const undoStack=[], redoStack=[];" in template
    assert "pre_restore_backup" in template
    for marker in (
        "recordUndo(`move/rotate ${e.id}`,j.backup",
        "recordUndo(`animation ${e.id}`,j.backup",
        "recordUndo(`delete ${e.id}`,j.backup",
        "recordUndo(`add ${j.id}`,j.backup",
        "recordUndo(`dropid ${dropsState.mobid}`,j.backup",
        "recordUndo(`drop row ${dropsState.dropid}/${item_id}`,j.backup",
        "recordUndo(`delete drop ${dropsState.dropid}/${origItem}`,j.backup",
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

    assert "const multiSelected=new Set();" in template
    assert 'id="bulk-panel"' in template
    assert "Ctrl/Cmd-click dots or list rows to add/remove" in template
    assert "Multi-select defaults to moving the group while preserving relative spacing" in template
    assert 'id="bulk-anchor"' in template
    assert 'id="bulk-move-preview"' in template
    assert 'id="bulk-pick"' in template
    assert "function bulkAnchor(source=null)" in template
    assert "function previewBulkMoveTo(x,y,z,source='coordinates')" in template
    assert "bulkPickMode && multiSelected.size>=2" in template
    assert "previewBulkMoveTo(+transformProxy.position.x" in template
    assert "Nudge / Offset" in template
    assert "async function saveBulkTransform()" in template
    assert "fetch('/zoneplot/edit_bulk'" in template
    assert "recordUndo(`bulk transform ${j.count} entities`" in template
    assert 'id="bulk-sync"' in template
    assert "markSqlSynced(e.k,e.id)" in template

    root = Path(__file__).resolve().parents[1]
    zone_edit = (root / "src" / "workbench" / "editors" / "zone" / "_editor_impl.py").read_text(encoding="utf-8")
    gui_server = (root / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
    nyzul_plot = (root / "src" / "workbench" / "devtools" / "domains" / "nyzul_plot.py").read_text(encoding="utf-8")
    zone_plot = (root / "src" / "workbench" / "devtools" / "spatial" / "zone_plot.py").read_text(encoding="utf-8")
    assert "def update_positions_bulk(rows, comment=" in zone_edit
    assert "bulk transform is limited to 256 entities per action" in zone_edit
    assert "bulk transform must stay within one zone" in zone_edit
    assert "_save_backup(f\"bulk transform {len(normalized)} entities\"" in zone_edit
    assert '@app.post("/zoneplot/edit_bulk")' in gui_server

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
    assert "grid-template-columns:30px 60px minmax(90px,1fr) 44px" in template

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
    assert '"shared_owner": "mob_pools" if shared_model else None' in zone_edit
    assert 'owner_table = source.get("shared_owner") or table' in zone_edit
    assert "familyid" in zone_edit and "combat/species behavior are unchanged" in zone_edit
    assert '@app.get("/zoneplot/history/{kind}/{eid}")' in gui_server
    assert '@app.post("/zoneplot/restore_entity_previous")' in gui_server

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
    assert "No explicit ROAM_DISTANCE or SPAWN_LEASH stored for this mob." in template

    assert "if(typeof setGizmoMode==='function') setGizmoMode('translate');" in template
    assert 'id="zhelpBtn"' in template
    assert 'id="tab-help"' in template
    assert "Zone Editor help" in template
    assert "Transform shortcuts" in template
    assert "Client model preview" in template
    assert "Animation, model preview, NPC rows" in template

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

    assert "/zoneplot/animation-meta.json" in gui_server
    assert "loadAnimationMetadata()" in template
    assert "renderAnimationEvidence()" in template
    assert "Transient FOURCC animation reference" in template

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

    assert 'id="cloneSelectedBtn"' in template
    assert 'id="repeatAdd"' in template
    assert 'id="addGhostInfo"' in template
    assert "const addHeadingLine=new THREE.Line" in template
    assert "const addGhostLabel=new CSS2DObject" in template
    assert "aSel=kind==='m' ? {groupid:e.gid" in template
    assert "Repeated placement active: source/rotation/instance retained" in template
    assert '"gid": int(gid)' in zone_plot

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
