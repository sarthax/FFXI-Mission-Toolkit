"""Server-lineage adapters and schema references for Character Editor."""

from .catalog import LineageReference, compare_schema, get_reference
from .inventory import CORE_COLUMNS, InventoryContract, build_basic_insert_plan, inspect_inventory_contract
from .registry import AdapterFingerprint, detect_adapter

__all__ = [
    "AdapterFingerprint",
    "CORE_COLUMNS",
    "InventoryContract",
    "LineageReference",
    "build_basic_insert_plan",
    "compare_schema",
    "detect_adapter",
    "get_reference",
    "inspect_inventory_contract",
]
