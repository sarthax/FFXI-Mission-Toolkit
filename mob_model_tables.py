"""Compatibility import for Client Shared family model tables.

Canonical implementation: ``workbench.client.models.mob_model_tables``.
"""
from __future__ import annotations
import sys
from workbench.client.models import mob_model_tables as _canonical

sys.modules[__name__] = _canonical
