#!/usr/bin/env python3
"""Compatibility import alias for the active-environment Zone Plot backend."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import active_zone_plot as _canonical

sys.modules[__name__] = _canonical
