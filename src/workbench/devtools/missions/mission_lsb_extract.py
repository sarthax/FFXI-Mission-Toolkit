"""Compatibility bridge to the existing mission LSB extraction service."""
from __future__ import annotations

import sys

from workbench.plugins.domain import mission_lsb_extract as _canonical_dependency

sys.modules[__name__] = _canonical_dependency
