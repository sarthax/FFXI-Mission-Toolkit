#!/usr/bin/env python3
"""Compatibility CLI/import for Packages-owned backport orchestration."""
from __future__ import annotations

import sys

from workbench.packages.migration import orchestrator as _canonical

if __name__ == "__main__":
    from workbench.runtime.legacy_settings import get_dsp_root
    from workbench.runtime.paths import DATABASE_PATH

    _canonical.main(
        default_dsp_root=get_dsp_root(),
        default_db_path=DATABASE_PATH,
    )
else:
    sys.modules[__name__] = _canonical
