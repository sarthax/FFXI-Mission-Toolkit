#!/usr/bin/env python3
"""Compatibility CLI/import launcher for Development C++ API analysis."""
from __future__ import annotations

import sys
from workbench.devtools.server import cpp_api_index as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
