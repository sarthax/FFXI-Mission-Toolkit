"""Canonical Item DAT tooling adapter.

The mature Item DAT reader/writer implementation is preserved byte-for-byte in
``_dat_tools_impl.py``. It historically derives its backup directory from
``Path(__file__).parent`` and imports the repository-root ``settings`` module, so this
adapter executes it with the legacy root filename and a package-safe legacy-settings alias.
That preserves all existing DAT locations, backup behavior, and settings semantics while
removing the implementation from repository root.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from workbench.runtime import legacy_settings as _legacy_settings
from workbench.runtime.paths import REPO_ROOT

_IMPL_PATH = Path(__file__).with_name("_dat_tools_impl.py")
_LEGACY_FILE = REPO_ROOT / "item_dat_tools.py"
_LEGACY_SETTINGS_MODULE = _legacy_settings._module()


def _load_impl() -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{__name__}._impl", _IMPL_PATH)
    if spec is None:
        raise ImportError(f"Unable to create Item DAT implementation spec for {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)

    previous_settings = sys.modules.get("settings")
    sys.modules["settings"] = _LEGACY_SETTINGS_MODULE
    try:
        module.__file__ = str(_LEGACY_FILE)
        source = _IMPL_PATH.read_text(encoding="utf-8")
        exec(compile(source, str(_IMPL_PATH), "exec"), module.__dict__)
    finally:
        if previous_settings is None:
            sys.modules.pop("settings", None)
        else:
            sys.modules["settings"] = previous_settings

    # Keep the original global module identity/semantics explicitly pinned.
    module.settings_mod = _LEGACY_SETTINGS_MODULE
    module.__file__ = str(_LEGACY_FILE)
    module.__package__ = __package__
    return module


_impl = _load_impl()

if __name__ == "__main__":
    main = getattr(_impl, "main", None)
    if main is None:
        raise SystemExit("item_dat_tools is a library module and has no CLI entry point")
    raise SystemExit(main())

sys.modules[__name__] = _impl
