#!/usr/bin/env python3
"""Compatibility import alias for the packaged Zone Plot backend."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import zone_plot as _canonical

sys.modules[__name__] = _canonical
