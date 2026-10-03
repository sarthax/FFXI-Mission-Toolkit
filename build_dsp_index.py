#!/usr/bin/env python3
"""Compatibility CLI/import alias for the packaged DSP indexer."""
from __future__ import annotations

import sys

from workbench.devtools.indexing import build_dsp_index as _canonical

if __name__ == "__main__":
    raise SystemExit(_canonical.main())

sys.modules[__name__] = _canonical
