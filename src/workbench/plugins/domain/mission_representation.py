"""Compatibility shim for Development mission representation planning."""
from __future__ import annotations

import sys

from workbench.devtools.missions import mission_representation as _canonical

sys.modules[__name__] = _canonical
