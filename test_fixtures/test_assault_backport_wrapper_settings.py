from pathlib import Path
import importlib


def test_assault_driver_resolves_settings_defaults():
    canonical = importlib.import_module("workbench.packages.migration.drivers.assault_batch")
    legacy = importlib.import_module("workbench.runtime.legacy_settings")

    backport_root = legacy.get_backport_root()
    expected_pkg_root = (backport_root / "mission-packages") if backport_root is not None else None
    assert canonical._default_package_root_base() == expected_pkg_root
    assert canonical._default_dsp_root() == legacy.get_dsp_root()


def test_assault_root_wrapper_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "backport_convert_7_packages.py").exists()
