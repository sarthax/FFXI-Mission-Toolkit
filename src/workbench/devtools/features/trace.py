"""Canonical Development entry point for Feature Trace.

The mature implementation is staged in ``_trace_impl`` during Phase C. Historical import names
are rebound only while that implementation loads so it consumes final Development services and
Core contracts without keeping Development -> product-implementation dependencies.
"""
from __future__ import annotations

import sys

import workbench.core.services as _legacy_services
from workbench.core.contracts import capture_row_locators as _capture_row_locators
from workbench.devtools.features import trace_catalog as _trace_catalog

_ALIASES = {
    "workbench.core.services.feature_trace_catalog": _trace_catalog,
    "workbench.core.services.capture_integrity": _capture_row_locators,
}
_PREVIOUS_MODULES = {name: sys.modules.get(name) for name in _ALIASES}
_PREVIOUS_ATTRS = {
    "feature_trace_catalog": getattr(_legacy_services, "feature_trace_catalog", None),
    "capture_integrity": getattr(_legacy_services, "capture_integrity", None),
}

for _name, _module in _ALIASES.items():
    sys.modules[_name] = _module
setattr(_legacy_services, "feature_trace_catalog", _trace_catalog)
setattr(_legacy_services, "capture_integrity", _capture_row_locators)

try:
    from workbench.devtools.features import _trace_impl as _impl
finally:
    for _name, _previous in _PREVIOUS_MODULES.items():
        if _previous is None:
            sys.modules.pop(_name, None)
        else:
            sys.modules[_name] = _previous
    for _attr, _previous in _PREVIOUS_ATTRS.items():
        if _previous is None:
            try:
                delattr(_legacy_services, _attr)
            except AttributeError:
                pass
        else:
            setattr(_legacy_services, _attr, _previous)

for _export in dir(_impl):
    if not _export.startswith("__"):
        globals()[_export] = getattr(_impl, _export)

__all__ = [name for name in dir(_impl) if not name.startswith("_")]
