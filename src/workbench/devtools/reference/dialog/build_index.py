"""Canonical Development/reference adapter for the mature dialog index builder.

The implementation is staged unchanged in ``_build_index_impl.py`` so the existing indexing,
FTS, audit, and CLI behavior stays intact.  This adapter supplies package-safe repository,
settings, database, and DAT-extractor dependencies before exposing that implementation as the
canonical module.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from types import ModuleType

from workbench.client.dat import extractor_bin
from workbench.runtime.legacy_settings import get_active_server_root
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT

_IMPL_PATH = Path(__file__).with_name("_build_index_impl.py")


def _settings_proxy() -> ModuleType:
    proxy = ModuleType("_dialog_index_settings_proxy")
    proxy.get_active_server_root = get_active_server_root
    return proxy


def _load_impl() -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{__name__}._impl", _IMPL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load dialog-index implementation from {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)

    old_settings = sys.modules.get("settings")
    old_extractor = sys.modules.get("dat_extractor_bin")
    sys.modules["settings"] = _settings_proxy()
    sys.modules["dat_extractor_bin"] = extractor_bin
    try:
        spec.loader.exec_module(module)
    finally:
        if old_settings is None:
            sys.modules.pop("settings", None)
        else:
            sys.modules["settings"] = old_settings
        if old_extractor is None:
            sys.modules.pop("dat_extractor_bin", None)
        else:
            sys.modules["dat_extractor_bin"] = old_extractor

    # Preserve historical runtime locations after moving the physical implementation under src.
    module.TOOLS_ROOT = REPO_ROOT
    module.TOPAZ_ROOT = get_active_server_root()
    module.DB_PATH = DATABASE_PATH
    module.DAT_EXTRACTOR_EXE = extractor_bin.EXE
    module.__package__ = __package__
    module.__doc__ = __doc__
    return module


_impl = _load_impl()


def _run_cli() -> int:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        sys.stdout = io.TextIOWrapper(stream, encoding="utf-8", errors="replace")
    result = _impl.main()
    return int(result or 0)


if __name__ == "__main__":
    raise SystemExit(_run_cli())
else:
    sys.modules[__name__] = _impl
