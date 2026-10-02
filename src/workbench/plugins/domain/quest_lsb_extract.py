"""Compatibility bridge to Development quest extraction."""
from __future__ import annotations

import sys

from workbench.devtools.missions import quest_lsb_extract as _canonical

sys.modules[__name__] = _canonical
