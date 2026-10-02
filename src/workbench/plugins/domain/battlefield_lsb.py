"""Compatibility shim for Development-owned LSB battlefield extraction."""
from __future__ import annotations

import sys

from workbench.devtools.battlefields import lsb as _canonical

sys.modules[__name__] = _canonical
