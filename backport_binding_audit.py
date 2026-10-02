#!/usr/bin/env python3
"""Compatibility launcher/import for Validation-owned package binding audit."""
from __future__ import annotations

import sys
from workbench.validation.packages import binding_audit as _canonical

if __name__ == "__main__":
    _canonical.main()
else:
    sys.modules[__name__] = _canonical
