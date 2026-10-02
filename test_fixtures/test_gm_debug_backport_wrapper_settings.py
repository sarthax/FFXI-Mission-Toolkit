from pathlib import Path
import importlib


def test_gm_debug_wrapper_aliases_canonical_driver_and_seeds_defaults():
    root = importlib.import_module("backport_convert_gm_debug_tools")
    canonical = importlib.import_module("workbench.packages.migration.drivers.gm_debug")
    legacy = importlib.import_module("workbench.runtime.legacy_settings")

    assert root is canonical
    backport_root = legacy.get_backport_root()
    expected_pkg_root = (
        backport_root / "mission-packages" / "assault_gm_debug_tools"
        if backport_root is not None
        else None
    )
    assert canonical.PKG_ROOT == expected_pkg_root
    assert canonical.DSP_ROOT == legacy.get_dsp_root()


def test_gm_debug_wrapper_has_no_direct_root_settings_import():
    source = Path("backport_convert_gm_debug_tools.py").read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime import legacy_settings as _settings" in source
