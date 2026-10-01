#!/usr/bin/env python3
"""Compatibility launcher for the canonical Capture video/OCR service."""
from __future__ import annotations

import sys

from workbench.captures.video import ocr as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
