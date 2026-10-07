from pathlib import Path
import importlib


def test_nyzul_driver_resolves_settings_default():
    canonical = importlib.import_module("workbench.packages.migration.drivers.nyzul")
    legacy = importlib.import_module("workbench.runtime.legacy_settings")

    backport_root = legacy.get_backport_root()
    expected_pkg_root = (
        backport_root / "mission-packages" / "nyzul_isle_investigation"
        if backport_root is not None
        else None
    )
    assert canonical._default_pkg_root() == expected_pkg_root


def test_nyzul_root_wrapper_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "backport_convert_nyzul_package.py").exists()
