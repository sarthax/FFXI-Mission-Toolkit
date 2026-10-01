"""Compatibility import for the Development Feature Checker service.

Feature Checker is product Development tooling, not a Core contract. New code must import
``workbench.devtools.features.checker``. This shim remains during Phase C while callers migrate.
"""
from workbench.devtools.features.checker import *  # noqa: F401,F403
