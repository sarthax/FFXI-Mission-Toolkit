"""Canonical read-only live SQL validation surface."""
from __future__ import annotations

import sys

from workbench.packages.migration import sql_convert as _sql_convert

# The mature checker historically imported the root converter name. Bind that
# dependency to the canonical Packages implementation before loading the
# preserved implementation blob so editable installs never require repo root.
sys.modules["backport_sql_convert"] = _sql_convert

from . import _sql_check_impl as _impl

_impl.bsc = _sql_convert
sys.modules[__name__] = _impl
