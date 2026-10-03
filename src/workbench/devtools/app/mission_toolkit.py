"""Canonical package entry point for the legacy Mission Toolkit developer CLI.

The mature implementation is retained byte-for-byte in ``_mission_toolkit_impl.py``.
It historically derives repository resources from ``Path(__file__).parent`` at import time,
so execute it with the legacy root filename until those paths are individually moved onto the
runtime path service. This preserves behavior while removing the implementation from repository
root.
"""
from __future__ import annotations

from pathlib import Path

from workbench.runtime.paths import REPO_ROOT

_IMPLEMENTATION_FILE = Path(__file__).with_name("_mission_toolkit_impl.py")
_LEGACY_FILE = REPO_ROOT / "mission_toolkit.py"

_namespace = {
    "__name__": __name__,
    "__file__": str(_LEGACY_FILE),
    "__package__": __package__,
    "__builtins__": __builtins__,
}
exec(
    compile(_IMPLEMENTATION_FILE.read_text(encoding="utf-8"), str(_LEGACY_FILE), "exec"),
    _namespace,
)

for _name, _value in _namespace.items():
    if _name not in {"__name__", "__file__", "__package__", "__builtins__"}:
        globals()[_name] = _value

LEGACY_FILE = _LEGACY_FILE
IMPLEMENTATION_FILE = _IMPLEMENTATION_FILE
