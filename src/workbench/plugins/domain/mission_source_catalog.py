"""Compatibility bridge to Development mission source catalog."""
from __future__ import annotations

import sys

from workbench.devtools.missions import mission_source_catalog as _canonical

sys.modules[__name__] = _canonical
