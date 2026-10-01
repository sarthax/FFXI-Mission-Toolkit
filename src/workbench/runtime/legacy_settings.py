"""Transitional package-safe access to the legacy root ``settings.py`` module.

This bridge exists only while settings/configuration is being moved into the src layout.
Package code should import the specific functions it needs from here instead of relying on the
repository root being on ``sys.path``.
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from types import ModuleType

from workbench.runtime.paths import REPO_ROOT


@lru_cache(maxsize=1)
def _module() -> ModuleType:
    path = REPO_ROOT / "settings.py"
    spec = importlib.util.spec_from_file_location("_mission_toolkit_legacy_settings", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy settings module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_active_server_root():
    return _module().get_active_server_root()


def get_active_sql_prefix():
    return _module().get_active_sql_prefix()


def get_topaz_root():
    return _module().get_topaz_root()


def get_ffxi_install():
    return _module().get_ffxi_install()
