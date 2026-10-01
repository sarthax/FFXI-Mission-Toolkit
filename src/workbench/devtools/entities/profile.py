"""Canonical Development Entity Profile API.

The mature Entity Profile implementation predates the src-layout and historically imported
repository-root modules by filename.  During Phase C its implementation body lives beside this
module in ``_profile_impl`` while this entry point binds those legacy absolute import names to
their canonical component modules for import, then restores ``sys.modules`` immediately.

This keeps the migration behavior-preserving: evidence/provenance/profile assembly is unchanged,
while callers can now import ``workbench.devtools.entities.profile`` from an editable install
without depending on the repository root being on ``sys.path``.  The compatibility layer can be
removed after the implementation body's imports are rewritten in a later cleanup slice.
"""
from __future__ import annotations

import sys

from workbench.client.models import look_decode as _look_decode
from workbench.devtools.entities import lookup as _lookup
from workbench.devtools.entities.profile_graph import import_entity_profile_provenance as _graph_import
from workbench.runtime import legacy_settings as _settings
from workbench.runtime.paths import DATABASE_PATH

_SENTINEL = object()
_ALIASES = {
    "lookup_entity": _lookup,
    "mob_look_decode": _look_decode,
    "settings": _settings,
}
_previous = {name: sys.modules.get(name, _SENTINEL) for name in _ALIASES}
try:
    sys.modules.update(_ALIASES)
    from workbench.devtools.entities import _profile_impl as _impl
finally:
    for _name, _module in _previous.items():
        if _module is _SENTINEL:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _module

# Pin the moved implementation to canonical component dependencies and repository state paths.
# Function globals live on _profile_impl, so these assignments affect every existing function
# without rewriting the mature profile/evidence logic in this structural migration.
_impl.lookup_entity = _lookup
_impl.mob_look_decode = _look_decode
_impl.settings = _settings
_impl.import_entity_profile_provenance = _graph_import
_impl.DB_PATH = DATABASE_PATH
_impl.TOPAZ_ROOT = _settings.get_topaz_root()

# Re-export the complete legacy module surface, including internal helpers used by older callers.
# Dunder metadata remains owned by this canonical module.
for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

# Ensure the canonical path values cannot be overwritten by a copied legacy constant above.
DB_PATH = DATABASE_PATH
TOPAZ_ROOT = _impl.TOPAZ_ROOT


def main():
    """Run the preserved Entity Profile CLI through the canonical Development module."""
    return _impl.main()
