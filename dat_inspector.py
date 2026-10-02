"""Compatibility import for the canonical Client DAT inspector."""
from __future__ import annotations

import sys
from workbench.client.dat import inspector as _canonical

sys.modules[__name__] = _canonical
