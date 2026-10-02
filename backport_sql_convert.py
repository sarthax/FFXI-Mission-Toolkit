"""Compatibility shim for Packages-owned legacy DSP SQL conversion."""
from __future__ import annotations

import sys

from workbench.packages.migration import sql_convert as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
