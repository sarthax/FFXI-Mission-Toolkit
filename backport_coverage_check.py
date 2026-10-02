"""Compatibility CLI/import for package coverage validation."""
from __future__ import annotations
import sys
from workbench.validation.packages import coverage as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
