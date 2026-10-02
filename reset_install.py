#!/usr/bin/env python3
"""Compatibility launcher/import alias for the bootstrap reset-install utility."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_IMPL = Path(__file__).resolve().parent / "scripts" / "bootstrap" / "reset_install.py"
_SPEC = importlib.util.spec_from_file_location("mission_toolkit_bootstrap_reset_install", _IMPL)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Could not load bootstrap reset utility from {_IMPL}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

if __name__ == "__main__":
    raise SystemExit(_MODULE.main())

sys.modules[__name__] = _MODULE
