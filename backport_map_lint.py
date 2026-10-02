"""Compatibility CLI/import for namespace-map validation."""
from __future__ import annotations
import sys
from workbench.validation.packages import map_lint as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.lint())

sys.modules[__name__] = _canonical
