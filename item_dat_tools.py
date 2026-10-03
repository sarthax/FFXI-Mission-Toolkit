"""Compatibility import alias for packaged Item DAT tooling."""
from __future__ import annotations

import sys

from workbench.editors.items import dat_tools as _canonical

sys.modules[__name__] = _canonical
