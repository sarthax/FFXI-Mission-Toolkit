#!/usr/bin/env python3
"""Compatibility launcher for packaged mob position recovery tooling."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import pull_mob_positions as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
