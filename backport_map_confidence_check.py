"""Compatibility CLI/import for namespace-map confidence validation."""
from __future__ import annotations
import sys
from workbench.validation.packages import map_confidence as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
