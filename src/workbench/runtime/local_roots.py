"""Locate machine-specific checkouts without hard-coding a personal path.

Resolution order for the DSP checkout: ``MISSION_TOOLKIT_DSP_ROOT`` (or ``DSP_ROOT``)
environment variable, then the ``dsp_server_path`` setting. Returns ``None`` when unset;
callers must treat that as "not configured" rather than guessing a location.
"""
from __future__ import annotations

import os
from pathlib import Path


def env_path(*names: str) -> Path | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return Path(value)
    return None


def dsp_root() -> Path | None:
    found = env_path("MISSION_TOOLKIT_DSP_ROOT", "DSP_ROOT")
    if found is not None:
        return found
    try:
        from workbench.runtime.settings_store import get_dsp_root
        return get_dsp_root()
    except Exception:
        return None
