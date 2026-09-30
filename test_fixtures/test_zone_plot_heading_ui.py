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

    print("Zone Plot heading/compass/zoom UI regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
