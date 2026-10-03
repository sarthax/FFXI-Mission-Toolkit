"""Canonical Zone Editor adapter.

The mature root ``zone_edit.py`` implementation is preserved byte-for-byte in
``_editor_impl.py``. It historically derives backup/journal paths from
``Path(__file__).parent`` and imports several repository-root compatibility names. Execute it
with the historical root filename while supplying canonical packaged dependencies so the move
does not alter server selection, SQL sync, model resolution, or write/backup behavior.

Live/admin server selection now resolves through the named active environment.  The mature
implementation's historical ``_sql_dir`` helper is overridden below so checked-in SQL sync uses
the exact same environment root as the live DB instead of assuming every non-DSP target is Topaz.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from workbench.client.models import look_decode as _look_decode
from workbench.client.models import resolver as _model_resolver
from workbench.devtools.spatial import active_zone_plot as _zone_plot
from workbench.runtime import legacy_settings as _legacy_settings
from workbench.runtime.paths import REPO_ROOT

_IMPL_PATH = Path(__file__).with_name("_editor_impl.py")
_LEGACY_FILE = REPO_ROOT / "zone_edit.py"


def _load_impl() -> ModuleType:
    impl_name = f"{__name__}._impl"
    spec = importlib.util.spec_from_file_location(impl_name, _IMPL_PATH)
    if spec is None:
        raise ImportError(f"Unable to create Zone Editor implementation spec for {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[impl_name] = module

    aliases = {
        "settings": _legacy_settings,
        "zone_plot": _zone_plot,
        "client_model_resolver": _model_resolver,
        "mob_look_decode": _look_decode,
    }
    previous = {name: sys.modules.get(name) for name in aliases}
    sys.modules.update(aliases)
    try:
        module.__file__ = str(_LEGACY_FILE)
        source = _IMPL_PATH.read_text(encoding="utf-8")
        exec(compile(source, str(_IMPL_PATH), "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(impl_name, None)
        raise
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old

    module.settings = _legacy_settings
    module.zone_plot = _zone_plot
    module.client_model_resolver = _model_resolver
    module.mob_look_decode = _look_decode

    def _active_sql_dir(server=None) -> Path:
        root = _zone_plot._server_root(server)
        sql_dir = root / "sql"
        if not sql_dir.is_dir():
            raise ValueError(f"Active server environment has no sql directory: {sql_dir}")
        return sql_dir

    module._sql_dir = _active_sql_dir
    module.__file__ = str(_LEGACY_FILE)
    module.__package__ = __package__
    return module


_impl = _load_impl()

if __name__ == "__main__":
    main = getattr(_impl, "main", None)
    if main is None:
        raise SystemExit("zone_edit is a library module and has no CLI entry point")
    raise SystemExit(main())

sys.modules[__name__] = _impl
