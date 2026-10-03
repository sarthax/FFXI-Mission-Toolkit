#!/usr/bin/env python3
"""Compatibility CLI/import alias for the packaged event/CSID explorer."""
from __future__ import annotations

import sys

from workbench.devtools.server import explore_event as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
