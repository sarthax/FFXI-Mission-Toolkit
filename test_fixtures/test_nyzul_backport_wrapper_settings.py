from pathlib import Path
import importlib


def test_nyzul_wrapper_aliases_canonical_driver_and_seeds_package_root():
    root = importlib.import_module("backport_convert_nyzul_package")
    canonical = importlib.import_module("workbench.packages.migration.drivers.nyzul")
    legacy = importlib.import_module("workbench.runtime.legacy_settings")

    assert root is canonical
    backport_root = legacy.get_backport_root()
    expected_pkg_root = (
        backport_root / "mission-packages" / "nyzul_isle_investigation"
        if backport_root is not None
        else None
    )
    assert canonical.PKG_ROOT == expected_pkg_root


def test_nyzul_wrapper_has_no_direct_root_settings_import():
    source = Path("backport_convert_nyzul_package.py").read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime import legacy_settings as _settings" in source
