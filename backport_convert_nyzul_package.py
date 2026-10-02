"""Compatibility CLI/import wrapper for package-owned Nyzul conversion driver."""
from __future__ import annotations

import sys
import settings as _settings
from workbench.packages.migration.drivers import nyzul as _canonical

_backport_root = _settings.get_backport_root()
_canonical.PKG_ROOT = (_backport_root / "mission-packages" / "nyzul_isle_investigation") if _backport_root is not None else None

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
