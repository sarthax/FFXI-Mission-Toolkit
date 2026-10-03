"""Compatibility import alias for the packaged Zone Editor backend."""
from __future__ import annotations

import sys

from workbench.editors.zone import editor as _canonical

sys.modules[__name__] = _canonical
