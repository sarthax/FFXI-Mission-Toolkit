"""Canonical Development database indexer adapter.

The mature database/index implementation is preserved byte-for-byte in
``_build_database_impl.py``. This adapter executes it with the historical repository-root
``__file__`` value so all existing path initialization and import-time opcode-table loading keep
their original semantics, while root-only helper imports are supplied through canonical package
modules.
"""
from __future__ import annotations

import importlib.util
import sys
from functools import wraps
from pathlib import Path
from types import ModuleType

from workbench.client.dat import extractor_bin
from workbench.runtime import legacy_settings as _legacy_settings
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT, VENDOR_ROOT, repo_path

_IMPL_PATH = Path(__file__).with_name("_build_database_impl.py")
_LEGACY_SETTINGS_MODULE = _legacy_settings._module()


def _load_impl() -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{__name__}._impl", _IMPL_PATH)
    if spec is None:
        raise ImportError(f"Unable to create database-index implementation spec for {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)

    old_settings = sys.modules.get("settings")
    old_extractor = sys.modules.get("dat_extractor_bin")
    sys.modules["settings"] = _LEGACY_SETTINGS_MODULE
    sys.modules["dat_extractor_bin"] = extractor_bin
    try:
        # The implementation derives repository/vendor paths from __file__ at import time and
        # immediately reads the XiEvents opcode table. Preserve that historical root identity
        # while compiling from the physically moved source file.
        module.__file__ = str(REPO_ROOT / "build_database.py")
        source = _IMPL_PATH.read_text(encoding="utf-8")
        exec(compile(source, str(_IMPL_PATH), "exec"), module.__dict__)
    finally:
        if old_settings is None:
            sys.modules.pop("settings", None)
        else:
            sys.modules["settings"] = old_settings
        if old_extractor is None:
            sys.modules.pop("dat_extractor_bin", None)
        else:
            sys.modules["dat_extractor_bin"] = old_extractor

    # Pin moved implementation globals to their canonical repository locations explicitly.
    module.TOOLS_ROOT = REPO_ROOT
    module.TOPAZ_ROOT = _legacy_settings.get_topaz_root()
    module.LSB_ROOT = repo_path("LandSandBoat")
    module.DB_PATH = DATABASE_PATH
    module.DEFAULT_FFXI_PATH = (
        _legacy_settings.get_ffxi_install()
        or "C:/ValhallaXI/SquareEnix/FINAL FANTASY XI"
    )
    module.XI_TINKERER_EXE = VENDOR_ROOT / "xi-tinkerer/target/release/xi-tinkerer-cli.exe"
    module.DAT_EXTRACTOR_EXE = extractor_bin.EXE
    module.ALTANA_ZONES_CSV = VENDOR_ROOT / "ffxi/reference/AltanaViewer_zones.csv"
    module.FFXI_RESOURCES_DIST = repo_path("FFXI-Resources-dist")
    module.DB_BACKUPS_DIR = repo_path("db_backups")
    module.__package__ = __package__
    module.__doc__ = __doc__

    # backup_database_file intentionally re-imports settings on every call so retention changes
    # apply immediately. Supply the same explicitly loaded legacy settings module only for that
    # call instead of leaving a root-name alias in sys.modules globally.
    original_backup = module.backup_database_file

    @wraps(original_backup)
    def package_safe_backup_database_file(*args, **kwargs):
        previous = sys.modules.get("settings")
        sys.modules["settings"] = _LEGACY_SETTINGS_MODULE
        try:
            return original_backup(*args, **kwargs)
        finally:
            if previous is None:
                sys.modules.pop("settings", None)
            else:
                sys.modules["settings"] = previous

    module.backup_database_file = package_safe_backup_database_file
    return module


_impl = _load_impl()

if __name__ == "__main__":
    _impl.main()
else:
    sys.modules[__name__] = _impl
