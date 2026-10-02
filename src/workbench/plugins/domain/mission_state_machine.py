"""Compatibility shim for Development mission state-machine modeling."""
from __future__ import annotations

import sys

from workbench.devtools.missions import mission_state_machine as _canonical

sys.modules[__name__] = _canonical
