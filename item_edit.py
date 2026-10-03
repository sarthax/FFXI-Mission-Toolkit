"""Compatibility import alias for the packaged Item Editor backend."""
from __future__ import annotations

import sys

from workbench.editors.items import editor as _canonical

sys.modules[__name__] = _canonical
