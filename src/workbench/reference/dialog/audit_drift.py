"""Compatibility import alias for the canonical Devtools dialog audit."""
from __future__ import annotations

import sys
from workbench.devtools.reference.dialog import audit_drift as _canonical

sys.modules[__name__] = _canonical
