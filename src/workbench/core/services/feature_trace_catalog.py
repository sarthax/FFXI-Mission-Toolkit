"""Compatibility import for Development Feature Trace catalog services.

New code must import ``workbench.devtools.features.trace_catalog``. This Core path remains as a
Phase C compatibility shim while Feature Trace, Item Editor, dossier and reference callers migrate.
"""
from workbench.devtools.features.trace_catalog import *  # noqa: F401,F403
