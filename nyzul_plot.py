"""Compatibility alias for the packaged Nyzul domain plot backend.

Canonical implementation: ``workbench.devtools.domains.nyzul_plot``.
"""
from __future__ import annotations

import sys

from workbench.devtools.domains import nyzul_plot as _canonical

sys.modules[__name__] = _canonical
