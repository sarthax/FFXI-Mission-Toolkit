"""FFXI server-source adapter contracts and built-in profiles."""
from .base import AdapterProbe, SchemaProfile, ServerAdapter, TableShape
from .profile_adapters import DSPAdapter, LSBAdapter, TopazAdapter, adapter_for
from .profiles import DSP, LSB, TOPAZ

__all__ = [
    "AdapterProbe", "SchemaProfile", "ServerAdapter", "TableShape",
    "DSPAdapter", "LSBAdapter", "TopazAdapter", "adapter_for",
    "DSP", "LSB", "TOPAZ",
]
