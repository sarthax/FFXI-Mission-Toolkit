from pathlib import Path
import importlib


def test_gm_debug_driver_resolves_settings_defaults():
    canonical = importlib.import_module("workbench.packages.migration.drivers.gm_debug")
    legacy = importlib.import_module("workbench.runtime.legacy_settings")

    backport_root = legacy.get_backport_root()
    expected_pkg_root = (
        backport_root / "mission-packages" / "assault_gm_debug_tools"
        if backport_root is not None
        else None
    )
    assert canonical._default_pkg_root() == expected_pkg_root
    assert canonical._default_dsp_root() == legacy.get_dsp_root()


def test_gm_debug_root_wrapper_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "backport_convert_gm_debug_tools.py").exists()
