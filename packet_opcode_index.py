#!/usr/bin/env python3
"""Compatibility entry point for the canonical packet opcode index."""
from __future__ import annotations

import sys
from workbench.packets import opcode_index as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
