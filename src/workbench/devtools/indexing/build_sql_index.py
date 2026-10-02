"""Canonical Development SQL indexer adapter.

The mature SQL parser/indexer implementation is preserved byte-for-byte in
``_build_sql_index_impl.py``.  This adapter supplies package-safe settings and pins every
repository-owned runtime path back to the historical repository locations before exposing the
implementation as the canonical module.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from types import ModuleType

from workbench.runtime.legacy_settings import get_topaz_root
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT, repo_path

_IMPL_PATH = Path(__file__).with_name("_build_sql_index_impl.py")


def _settings_proxy() -> ModuleType:
    proxy = ModuleType("_build_sql_index_settings_proxy")
    proxy.get_topaz_root = get_topaz_root
    return proxy


def _load_impl() -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{__name__}._impl", _IMPL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load SQL-index implementation from {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)

    old_settings = sys.modules.get("settings")
    sys.modules["settings"] = _settings_proxy()
    try:
        spec.loader.exec_module(module)
    finally:
        if old_settings is None:
            sys.modules.pop("settings", None)
        else:
            sys.modules["settings"] = old_settings

    # Preserve every historical repository-owned path after the physical implementation moves.
    module.TOOLS_ROOT = REPO_ROOT
    module.TOPAZ_ROOT = get_topaz_root()
    module.DB_PATH = DATABASE_PATH
    module.WORKBENCH_DB = repo_path("workbench.db")
    module.LSB_ROOT = repo_path("LandSandBoat")
    module.SQL_DIR = module.LSB_ROOT / "sql"
    module._CLEAN_CACHE_DIR = repo_path("mission_reports", "_sql_clean")
    module.__package__ = __package__
    module.__doc__ = __doc__
    return module


_impl = _load_impl()


def _run_cli() -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        sys.stdout = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")
    _impl.main()


if __name__ == "__main__":
    _run_cli()
else:
    sys.modules[__name__] = _impl
