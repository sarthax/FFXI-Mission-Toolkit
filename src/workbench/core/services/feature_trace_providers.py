"""Compatibility import for Development Feature Trace provider registry.

New code must import ``workbench.devtools.features.trace_providers``. This Core path remains as a
Phase C compatibility shim while Feature Trace and reference callers migrate.
"""
from workbench.devtools.features.trace_providers import *  # noqa: F401,F403
