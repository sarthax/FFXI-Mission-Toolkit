"""Compatibility CLI/import launcher for live SQL validation."""
from __future__ import annotations

import sys

from workbench.validation.live_db import sql_check as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
