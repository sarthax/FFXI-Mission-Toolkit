"""Compatibility shim for Development mission feature closure."""
from __future__ import annotations

import sys

from workbench.devtools.missions import mission_feature_closure as _canonical

sys.modules[__name__] = _canonical
