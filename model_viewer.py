"""Compatibility import alias for the packaged Client model viewer backend."""
from __future__ import annotations

import sys

from workbench.client.models import viewer as _canonical

sys.modules[__name__] = _canonical
