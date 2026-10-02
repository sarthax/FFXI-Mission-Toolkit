#!/usr/bin/env python3
"""Compatibility launcher for package Lua sanity validation."""
from __future__ import annotations

import sys
from workbench.validation.packages import lua_sanity as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
