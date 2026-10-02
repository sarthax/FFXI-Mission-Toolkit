#!/usr/bin/env python3
"""Compatibility launcher/import alias for the packaged dialog index builder."""
from __future__ import annotations

import io
import sys

from workbench.devtools.reference.dialog import build_index as _canonical

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
