"""Canonical Development event/CSID explorer adapter.

The mature Event Explorer implementation is preserved byte-for-byte in
``_explore_event_impl.py``. Its repository paths and mission-export subprocess behavior are
intentionally rooted at the historical repository location, so execute the preserved source with
the historical virtual root filename and then pin those path globals to the canonical runtime path service.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from workbench.runtime.paths import DATABASE_PATH, REPO_ROOT, VENDOR_ROOT, repo_path

_IMPL_PATH = Path(__file__).with_name("_explore_event_impl.py")
_LEGACY_FILE = REPO_ROOT / "explore_event.py"


def _load_impl() -> ModuleType:
    impl_name = f"{__name__}._impl"
    spec = importlib.util.spec_from_file_location(impl_name, _IMPL_PATH)
    if spec is None:
        raise ImportError(f"Unable to create event-explorer implementation spec for {_IMPL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[impl_name] = module
    try:
        module.__file__ = str(_LEGACY_FILE)
        source = _IMPL_PATH.read_text(encoding="utf-8")
        exec(compile(source, str(_IMPL_PATH), "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(impl_name, None)
        raise

    module.TOOLS_ROOT = REPO_ROOT
    module.DB_PATH = DATABASE_PATH
    module.MISSION_REPORTS = repo_path("mission_reports")
    module.XI_EVENTS_BRIDGE = VENDOR_ROOT / "xi-events-py" / "decompile_from_mission_toolkit.py"
    module.__file__ = str(_LEGACY_FILE)
    module.__package__ = __package__
    return module


_impl = _load_impl()

if __name__ == "__main__":
    raise SystemExit(_impl.main())

sys.modules[__name__] = _impl
