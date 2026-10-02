from pathlib import Path

from workbench.runtime import legacy_settings
from workbench.validation.packages import map_confidence


def test_map_confidence_uses_package_safe_topaz_bridge():
    assert map_confidence.get_topaz_root is legacy_settings.get_topaz_root


def test_map_confidence_preserves_configured_dsp_existence_filter(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    monkeypatch.setattr(map_confidence, "_configured_dsp_root", lambda: missing)
    assert map_confidence.get_dsp_root() is None

    existing = tmp_path / "dsp"
    existing.mkdir()
    monkeypatch.setattr(map_confidence, "_configured_dsp_root", lambda: existing)
    assert map_confidence.get_dsp_root() == existing


def test_map_confidence_has_no_direct_root_settings_import():
    source = Path("src/workbench/validation/packages/map_confidence.py").read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime.legacy_settings import get_dsp_root as _configured_dsp_root, get_topaz_root" in source
