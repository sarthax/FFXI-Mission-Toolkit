"""Canonical Topaz -> legacy DSP SQL conversion surface."""
from __future__ import annotations

import sys

from workbench.runtime.paths import DATA_ROOT
from . import _sql_convert_impl as _impl

# Keep the mature implementation blob unchanged while resolving its repository-owned
# schema map through the canonical runtime path service.
_impl.MAP_PATH = DATA_ROOT / "dsp_sql_schema_map.json"

sys.modules[__name__] = _impl
