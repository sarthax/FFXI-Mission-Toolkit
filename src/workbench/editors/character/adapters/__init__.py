"""Server-lineage adapters and schema references for Character Editor."""

from .catalog import LineageReference, compare_schema, get_reference
from .registry import AdapterFingerprint, detect_adapter

__all__ = [
    "AdapterFingerprint",
    "LineageReference",
    "compare_schema",
    "detect_adapter",
    "get_reference",
]
