#!/usr/bin/env python3
"""Compatibility launcher for packaged zone door/object prop repair tooling."""
from __future__ import annotations

import sys

from workbench.devtools.spatial import fix_zone_door_props as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
