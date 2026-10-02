"""Compatibility shim for Development mission event reconciliation."""
from __future__ import annotations

import sys

from workbench.devtools.missions import event_reconcile as _canonical

sys.modules[__name__] = _canonical
