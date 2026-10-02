"""Compatibility CLI/import wrapper for package-owned GM debug conversion driver."""
from __future__ import annotations

import sys
import settings as _settings
from workbench.packages.migration.drivers import gm_debug as _canonical

_backport_root = _settings.get_backport_root()
_canonical.PKG_ROOT = (_backport_root / "mission-packages" / "assault_gm_debug_tools") if _backport_root is not None else None
_canonical.DSP_ROOT = _settings.get_dsp_root()

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
