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

    print("Zone Plot heading/compass/zoom UI regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
