"""Validated inventory table contract for DSP, Topaz, and LandSandBoat.

The historical/current reference schemas share the same core char_inventory row shape.
This adapter still validates the connected live schema before offering an insert plan so custom
fork drift is explicit.  The `extra` blob remains opaque until a lineage-specific codec is added.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

CORE_COLUMNS = (
    "charid",
    "location",
    "slot",
    "itemId",
    "quantity",
    "bazaar",
    "signature",
    "extra",
)


@dataclass(frozen=True)
class InventoryContract:
    family: str
    table: str
    valid: bool
    present_columns: tuple[str, ...]
    missing_columns: tuple[str, ...]
    extra_columns: tuple[str, ...]
    extra_codec_verified: bool = False

    @property
    def basic_insert_verified(self) -> bool:
        return self.valid and not self.missing_columns

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["basic_insert_verified"] = self.basic_insert_verified
        return out


def inspect_inventory_contract(schema, family: str) -> InventoryContract:
    table = schema.table("char_inventory") if hasattr(schema, "table") else None
    if table is None:
        return InventoryContract(
            family=str(family or "unknown"),
            table="char_inventory",
            valid=False,
            present_columns=(),
            missing_columns=CORE_COLUMNS,
            extra_columns=(),
        )

    present = tuple(table.column_names)
    present_set = set(present)
    missing = tuple(c for c in CORE_COLUMNS if c not in present_set)
    extra = tuple(c for c in present if c not in CORE_COLUMNS)
    return InventoryContract(
        family=str(family or "unknown"),
        table="char_inventory",
        valid=not missing,
        present_columns=present,
        missing_columns=missing,
        extra_columns=extra,
    )


def build_basic_insert_plan(
    contract: InventoryContract,
    *,
    char_id: int,
    item_id: int,
    location: int,
    slot: int,
    quantity: int,
    signature: str = "",
    bazaar: int = 0,
    extra: bytes | None = None,
) -> dict[str, Any]:
    """Return a parameterized SQL preview. No SQL is executed here."""
    if not contract.basic_insert_verified:
        raise RuntimeError("Connected char_inventory schema does not match the verified core contract")
    if extra not in (None, b"") and not contract.extra_codec_verified:
        raise RuntimeError("Inventory extra data requires a verified lineage-specific codec")
    if int(char_id) <= 0 or int(item_id) <= 0:
        raise ValueError("char_id and item_id must be positive")
    if int(location) < 0 or int(slot) < 0 or int(quantity) <= 0:
        raise ValueError("location/slot must be non-negative and quantity must be positive")

    columns = ("charid", "location", "slot", "itemId", "quantity", "bazaar", "signature", "extra")
    sql = (
        "INSERT INTO `char_inventory` (" + ", ".join(f"`{c}`" for c in columns) + ") "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
    )
    params = (
        int(char_id), int(location), int(slot), int(item_id), int(quantity), int(bazaar),
        str(signature or "")[:20], None if extra in (None, b"") else bytes(extra),
    )
    return {"sql": sql, "params": params, "table": "char_inventory", "operation": "insert"}
