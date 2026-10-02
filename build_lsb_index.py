#!/usr/bin/env python3
"""Compatibility CLI/import for the canonical Development LSB indexer."""
from __future__ import annotations

import sys

from workbench.devtools.indexing import build_lsb_index as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
