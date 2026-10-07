"""Canonical package entry point for the Mission Toolkit developer CLI.

The mature implementation is retained in ``_mission_toolkit_impl.py``. This wrapper preserves its
historical filename/resource assumptions while binding its historical ``settings`` import to the
package runtime bridge, where the named active server environment is now authoritative.
"""
from __future__ import annotations

from pathlib import Path
import sys

from workbench.runtime import legacy_settings as _settings
from workbench.runtime.paths import REPO_ROOT

_IMPLEMENTATION_FILE = Path(__file__).with_name("_mission_toolkit_impl.py")
_LEGACY_FILE = REPO_ROOT / "mission_toolkit.py"
_SENTINEL = object()
_previous_settings = sys.modules.get("settings", _SENTINEL)

_namespace = {
    "__name__": __name__,
    "__file__": str(_LEGACY_FILE),
    "__package__": __package__,
    "__builtins__": __builtins__,
}
try:
    sys.modules["settings"] = _settings
    exec(
        compile(_IMPLEMENTATION_FILE.read_text(encoding="utf-8"), str(_LEGACY_FILE), "exec"),
        _namespace,
    )
finally:
    if _previous_settings is _SENTINEL:
        sys.modules.pop("settings", None)
    else:
        sys.modules["settings"] = _previous_settings

# The retained implementation still calls its generic administered-server root ``TOPAZ_ROOT``.
# Keep that symbol for compatibility, but bind it to the selected named environment.
_namespace["settings"] = _settings
_namespace["TOPAZ_ROOT"] = _settings.get_active_server_root()

for _name, _value in _namespace.items():
    if _name not in {"__name__", "__file__", "__package__", "__builtins__"}:
        globals()[_name] = _value

LEGACY_FILE = _LEGACY_FILE
IMPLEMENTATION_FILE = _IMPLEMENTATION_FILE
