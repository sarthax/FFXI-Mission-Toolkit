from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_zone_material_audit_rejects_bad_rgba_without_guessing_formats():
    source = VIEWER.read_text(encoding="utf-8")
    for field in ("skySkipped", "water", "alphaBlend", "textured", "missingTexture", "invalidTexture"):
        assert field + ":" in source
    assert "tex.rgba.length !== tex.width * tex.height * 4" in source
    assert "Number.isInteger(tex.width)" in source
    assert "Number.isInteger(tex.height)" in source
    assert "group.userData.materialAudit = materialAudit" in source
    assert "console.info('[ZoneViewer] zone material audit:'" in source
    assert "falling back to untextured surfaces" in source
