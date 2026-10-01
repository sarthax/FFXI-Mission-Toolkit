#!/usr/bin/env python3
"""Compatibility launcher for the canonical runtime addon-tools service."""
from __future__ import annotations

import sys
from workbench.runtime import addon_tools as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
