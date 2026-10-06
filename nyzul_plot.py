"""Compatibility alias for the packaged Nyzul domain plot backend."""
from __future__ import annotations

import sys

from workbench.devtools.domains import _nyzul_profile_bridge  # noqa: F401
from workbench.devtools.domains import nyzul_plot as _canonical

sys.modules[__name__] = _canonical
