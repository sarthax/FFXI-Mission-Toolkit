"""Compatibility bridge to the existing mission state-machine service."""
from __future__ import annotations

import sys

from workbench.plugins.domain import mission_state_machine as _canonical_dependency

sys.modules[__name__] = _canonical_dependency
