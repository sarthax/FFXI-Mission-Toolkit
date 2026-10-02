"""Compatibility import for the packaged Topaz -> DSP Lua converter."""
from __future__ import annotations
import sys
from workbench.packages.migration import lua_convert as _canonical
sys.modules[__name__] = _canonical
