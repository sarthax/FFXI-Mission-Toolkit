#!/usr/bin/env python3
"""Compatibility launcher/import alias for the packaged plot descriptor builder."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import build_plot_descriptors as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
