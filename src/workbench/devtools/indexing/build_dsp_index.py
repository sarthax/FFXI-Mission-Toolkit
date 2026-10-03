"""Canonical Development DSP indexer adapter.

The mature DSP indexing implementation is preserved byte-for-byte in
``_build_dsp_index_impl.py``. This adapter supplies canonical indexing foundations and package-safe
settings under their historical absolute import names, then pins repository-owned paths to their
legacy locations before exposing the implementation as the canonical module.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from workbench.devtools.indexing import build_database as _build_database
from workbench.devtools.indexing import build_sql_index as _build_sql_index
from workbench.runtime import legacy_settings as _settings
from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT, repo_path

_IMPL_PATH = Path(__file__).with_name("_build_dsp_index_impl.py")


def _load_impl() -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{__name__}._impl", _IMPL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load DSP-index implementation from {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)

    aliases = {
        "build_database": _build_database,
        "build_sql_index": _build_sql_index,
        "settings": _settings,
    }
    sentinel = object()
    previous = {name: sys.modules.get(name, sentinel) for name in aliases}
    try:
        sys.modules.update(aliases)
        spec.loader.exec_module(module)
    finally:
        for name, prior in previous.items():
            if prior is sentinel:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior

    module.TOOLS_ROOT = REPO_ROOT
    module.TOPAZ_ROOT = _settings.get_topaz_root()
    module.DB_PATH = DATABASE_PATH
    module.WORKBENCH_DB = repo_path("workbench.db")
    module.DSP_ROOT = _settings.get_dsp_root()
    module.DSP_SQL_DIR = (module.DSP_ROOT / "sql") if module.DSP_ROOT else None
    module.DSP_SCRIPTS_DIR = (module.DSP_ROOT / "scripts" / "zones") if module.DSP_ROOT else None
    module.DSP_STATUS_EFFECT_H = (module.DSP_ROOT / "src" / "map" / "status_effect.h") if module.DSP_ROOT else None
    module.TOPAZ_SCRIPTS_DIR = module.TOPAZ_ROOT / "scripts" / "zones"
    module.TOPAZ_STATUS_EFFECT_H = module.TOPAZ_ROOT / "src" / "map" / "status_effect.h"
    module.build_database = _build_database
    module.sqlidx = _build_sql_index
    module.normalize = _build_database.normalize
    module.parse_table_file = _build_sql_index.parse_table_file
    module.unquote = _build_sql_index.unquote
    module.__package__ = __package__
    module.__doc__ = __doc__
    return module


_impl = _load_impl()

if __name__ == "__main__":
    _impl.main()
else:
    sys.modules[__name__] = _impl
