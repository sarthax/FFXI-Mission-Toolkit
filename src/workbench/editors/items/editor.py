"""Canonical Item Editor adapter.

The mature root ``item_edit.py`` implementation is preserved byte-for-byte in
``_editor_impl.py``. It historically derives its journal/backup paths from
``Path(__file__).parent`` and imports the root compatibility names ``item_dat_tools`` and
``zone_plot``. Execute it with the historical root filename while supplying the canonical
packaged dependencies so relocation does not alter write, backup, or journal behavior.

Generic live-server access is routed through the active-environment Zone Plot adapter so Item
Editor follows the same named Live/Test/Dev/Backup profile as Character Editor and Server tools.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from workbench.devtools.spatial import active_zone_plot as _zone_plot
from workbench.editors.items import dat_tools as _dat_tools
from workbench.runtime.paths import REPO_ROOT

_IMPL_PATH = Path(__file__).with_name("_editor_impl.py")
_LEGACY_FILE = REPO_ROOT / "item_edit.py"


def _load_impl() -> ModuleType:
    impl_name = f"{__name__}._impl"
    spec = importlib.util.spec_from_file_location(impl_name, _IMPL_PATH)
    if spec is None:
        raise ImportError(f"Unable to create Item Editor implementation spec for {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[impl_name] = module

    previous_dat = sys.modules.get("item_dat_tools")
    previous_zone_plot = sys.modules.get("zone_plot")
    sys.modules["item_dat_tools"] = _dat_tools
    sys.modules["zone_plot"] = _zone_plot
    try:
        module.__file__ = str(_LEGACY_FILE)
        source = _IMPL_PATH.read_text(encoding="utf-8")
        exec(compile(source, str(_IMPL_PATH), "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(impl_name, None)
        raise
    finally:
        if previous_dat is None:
            sys.modules.pop("item_dat_tools", None)
        else:
            sys.modules["item_dat_tools"] = previous_dat
        if previous_zone_plot is None:
            sys.modules.pop("zone_plot", None)
        else:
            sys.modules["zone_plot"] = previous_zone_plot

    module.dat = _dat_tools
    module.zone_plot = _zone_plot
    module.__file__ = str(_LEGACY_FILE)
    module.__package__ = __package__
    return module


_impl = _load_impl()

if __name__ == "__main__":
    main = getattr(_impl, "main", None)
    if main is None:
        raise SystemExit("item_edit is a library module and has no CLI entry point")
    raise SystemExit(main())

sys.modules[__name__] = _impl
