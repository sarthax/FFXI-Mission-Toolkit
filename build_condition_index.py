#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for Development build-condition indexing."""
import sys

from workbench.devtools.server import condition_index as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
