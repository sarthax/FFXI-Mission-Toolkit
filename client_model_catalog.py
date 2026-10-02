"""Compatibility import alias for the packaged Client model catalog."""
from __future__ import annotations

import sys

from workbench.client.models import catalog as _canonical

sys.modules[__name__] = _canonical
