"""Compatibility shim for Development mission LSB extraction."""
from __future__ import annotations

import sys

from workbench.devtools.missions import mission_lsb_extract as _canonical

sys.modules[__name__] = _canonical
