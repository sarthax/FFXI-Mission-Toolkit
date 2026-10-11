from pathlib import Path


VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"


def test_zone_instance_transform_audit_preserves_evidence_and_fallback():
    source = VIEWER.read_text(encoding="utf-8")
    assert "inst.transform.length !== 16" in source
    assert "Array.from(inst.transform).every(Number.isFinite)" in source
    assert "Math.abs(determinant) < 1e-10" in source
    assert "transformAudit.invalidTransform++" in source
    assert "transformAudit.mirrored++" in source
    assert "group.userData.transformAudit = transformAudit" in source
    assert "if (!audit.accepted) throw new Error('No valid zone instance transforms')" in source
    assert "loadObjFallback();" in source
