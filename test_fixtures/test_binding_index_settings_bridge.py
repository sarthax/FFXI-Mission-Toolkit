from pathlib import Path

from workbench.runtime import legacy_settings
from workbench.validation.packages import binding_index


def test_binding_index_uses_package_safe_settings_bridge():
    assert binding_index.get_topaz_root is legacy_settings.get_topaz_root
    assert binding_index.get_dsp_root is legacy_settings.get_dsp_root


def test_binding_index_has_no_direct_root_settings_import():
    source = Path("src/workbench/validation/packages/binding_index.py").read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime.legacy_settings import get_dsp_root, get_topaz_root" in source
