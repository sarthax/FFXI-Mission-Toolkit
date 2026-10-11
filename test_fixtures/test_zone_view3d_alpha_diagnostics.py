from pathlib import Path
from jinja2 import Environment

VIEWER = Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html"

def test_alpha_diagnostic_mode_is_reversible_and_non_destructive():
    text = VIEWER.read_text(encoding="utf-8")
    Environment().parse(text)
    assert 'id="zone3d-force-opaque"' in text
    assert 'id="zone3d-material-select"' in text
    assert 'id="zone3d-material-details"' in text
    assert "function applyAlphaDiagnosticMode()" in text
    assert "original.alphaTest" in text
    assert "original.transparent" in text
    assert "original.depthWrite" in text
    assert "original.opacity" in text
    assert "material.needsUpdate = true" in text
    assert "texture_name: prefab.textureName" in text
    assert "opaque_pixels: opaquePixels" in text
    assert "zero_alpha_pixels: zeroAlphaPixels" in text
    assert "partial_alpha_pixels: partialAlphaPixels" in text
    assert "registerAlphaMaterial(mat, prefab, prefabIdx" in text
