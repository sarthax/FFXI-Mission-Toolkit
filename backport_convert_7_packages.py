"""Compatibility CLI/import wrapper for package-owned Assault conversion driver."""
from __future__ import annotations

import sys
from workbench.runtime import legacy_settings as _settings
from workbench.packages.migration.drivers import assault_batch as _canonical

_backport_root = _settings.get_backport_root()
_canonical.PKG_ROOT_BASE = (_backport_root / "mission-packages") if _backport_root is not None else None
_canonical.DSP_ROOT = _settings.get_dsp_root()

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
