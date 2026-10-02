"""Canonical Topaz -> legacy DSP Lua conversion surface."""
from __future__ import annotations

import sys

from workbench.runtime.paths import DATA_ROOT
from . import _lua_convert_impl as _impl

# The mature converter historically resolved the namespace map beside the root
# script. Keep the implementation blob unchanged and bind that repository-owned
# data dependency through the canonical runtime path service instead.
_impl.MAP_PATH = DATA_ROOT / "dsp_namespace_map.json"

sys.modules[__name__] = _impl
