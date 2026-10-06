"""Canonical Development Entity Profile API.

The mature Entity Profile implementation lives in _profile_impl and now imports all
dependencies through canonical workbench package paths. This module preserves the public
Entity Profile API while pinning repository-state/runtime values that historically came from
root-level compatibility modules.
"""
from __future__ import annotations

from workbench.client.models import look_decode as _look_decode
from workbench.devtools.entities import _profile_impl as _impl
from workbench.devtools.entities import lookup as _lookup
from workbench.devtools.entities.profile_graph import import_entity_profile_provenance as _graph_import
from workbench.runtime import legacy_settings as _settings
from workbench.runtime.paths import DATABASE_PATH

# Pin the mature implementation to canonical component dependencies and repository state paths.
_impl.lookup_entity = _lookup
_impl.mob_look_decode = _look_decode
_impl.settings = _settings
_impl.import_entity_profile_provenance = _graph_import
_impl.DB_PATH = DATABASE_PATH
_impl.TOPAZ_ROOT = _settings.get_active_server_root()

# Re-export the complete implementation surface, including internal helpers used by older
# package callers. Dunder metadata remains owned by this canonical module.
for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

# Ensure canonical path values cannot be overwritten by implementation constants above.
DB_PATH = DATABASE_PATH
TOPAZ_ROOT = _impl.TOPAZ_ROOT


def main():
    """Run the preserved Entity Profile CLI through the canonical Development module."""
    return _impl.main()
