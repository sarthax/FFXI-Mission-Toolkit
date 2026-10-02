#!/usr/bin/env python3
"""Compatibility CLI/import for Packages-owned backport orchestration."""
from __future__ import annotations

import sys

from workbench.packages.migration import orchestrator as _canonical

if __name__ == "__main__":
    import settings as _settings

    _canonical.main(
        default_dsp_root=_settings.get_dsp_root(),
        default_db_path=_settings.DB_PATH,
    )
else:
    sys.modules[__name__] = _canonical
