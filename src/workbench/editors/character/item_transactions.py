"""Guarded direct-DB item injection for Character Editor.

Writes are intentionally limited to offline characters, server-known items, directly sized
persistent containers, a free slot, quantity within stack size, no Rare duplicate, and no custom
extra payload. Specialized extra-data initialization remains codec-gated. Storage capacity is
furnishing-derived and Temporary Items are runtime-managed, so neither is a direct destination.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .adapters.inventory import inspect_inventory_contract
from .audit import attach_committed_audit
from .inventory_slots import CAPACITY_COLUMNS, CONTAINERS, inspect_slots
from .item_catalog import ItemCatalogRecord, ItemCatalogService
from .schema import discover_character_schema
from .session_state import detect_online_state

ZERO_EXTRA = bytes(24)


@dataclass(frozen=True)
class TransactionIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class ItemInjectionPlan:
    char_id: int
    item: ItemCatalogRecord | None
    quantity: int
    location: int
    slot: int | None
    online: bool | None
    adapter_family: str
    issues: list[TransactionIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.item is not None and self.slot is not None and not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "item": self.item.as_dict() if self.item else None,
            "quantity": self.quantity,
            "location": self.location,
            "location_name": CONTAINERS.get(self.location, f"Container {self.location}"),
            "slot": self.slot,
            "online": self.online,
            "adapter_family": self.adapter_family,
            "issues": [asdict(i) for i in self.issues],
            "ready": self.ready,
        }


def _rare_duplicate(connection, char_id: int, item_id: int) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM `char_inventory` WHERE `charid` = %s AND `itemId` = %s LIMIT 1",
            (int(char_id), int(item_id)),
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def build_item_injection_plan(
    connection,
    *,
    char_id: int,
    item_id: int,
    quantity: int = 1,
    location: int = 0,
    adapter_family: str = "unknown",
    client_snapshot_id: str | None = None,
) -> ItemInjectionPlan:
    char_id = int(char_id)
    item_id = int(item_id)
    quantity = int(quantity)
    location = int(location)
    family = str(adapter_family or "unknown")
    issues: list[TransactionIssue] = []

    if char_id <= 0:
        raise ValueError("char_id must be positive")
    if item_id <= 0:
        raise ValueError("item_id must be positive")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if family not in {"dsp", "topaz", "lsb"}:
        issues.append(TransactionIssue("adapter_unverified", "DSP/Topaz/LSB adapter identity is required for writes."))

    schema = discover_character_schema(connection)
    contract = inspect_inventory_contract(schema, family)
    if not contract.basic_insert_verified:
        issues.append(TransactionIssue(
            "inventory_schema_drift",
            "Connected char_inventory schema does not match the verified core DSP/Topaz/LSB contract.",
        ))

    online_state = detect_online_state(connection, schema, char_id)
    online = online_state.online
    if online is True:
        issues.append(TransactionIssue("character_online", "Character is online; direct inventory writes are blocked."))
    elif online is None:
        issues.append(TransactionIssue("online_state_unknown", "Character online state could not be verified."))

    if location not in CAPACITY_COLUMNS:
        issues.append(TransactionIssue(
            "container_not_enabled",
            f"{CONTAINERS.get(location, f'Container {location}')} is not a directly sized persistent container and is not enabled for direct injection.",
        ))

    item = None
    try:
        item = ItemCatalogService(connection, client_snapshot_id=client_snapshot_id).get(item_id)
    except Exception as exc:
        issues.append(TransactionIssue("item_catalog_unavailable", f"Item catalog could not be verified: {exc}"))

    if item is None:
        issues.append(TransactionIssue("item_unknown", "Item ID is not present in the connected server item catalog."))
    else:
        if quantity > item.stack_size:
            issues.append(TransactionIssue(
                "stack_limit_exceeded",
                f"Requested quantity {quantity} exceeds stack size {item.stack_size}.",
            ))
        if item.rare and _rare_duplicate(connection, char_id, item.item_id):
            issues.append(TransactionIssue("rare_duplicate", "Character already owns this Rare item."))
        if item.exclusive:
            issues.append(TransactionIssue(
                "exclusive_item",
                "Item is Exclusive. This does not block ownership but is recorded for administrator review.",
                False,
            ))

    slot = None
    if location in CAPACITY_COLUMNS:
        try:
            state = inspect_slots(connection, char_id, location)
            slot = state.first_free_slot
            if state.capacity <= 0:
                issues.append(TransactionIssue("container_locked", f"{state.name} capacity is zero."))
            elif slot is None:
                issues.append(TransactionIssue("container_full", f"{state.name} has no free slot."))
        except Exception as exc:
            issues.append(TransactionIssue("slot_discovery_failed", f"Could not resolve a safe destination slot: {exc}"))

    return ItemInjectionPlan(
        char_id=char_id,
        item=item,
        quantity=quantity,
        location=location,
        slot=slot,
        online=online,
        adapter_family=family,
        issues=issues,
    )


def apply_item_injection(connection, plan: ItemInjectionPlan, *, approved: bool = False) -> dict[str, Any]:
    """Apply a previously built plan after re-validating safety inside a transaction."""
    if not approved:
        raise PermissionError("Explicit approval is required to apply an item injection")
    if not plan.ready or plan.item is None or plan.slot is None:
        raise RuntimeError("Item injection plan is not write-ready")

    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cursor = connection.cursor()
            try:
                cursor.execute("START TRANSACTION")
            finally:
                cursor.close()

        schema = discover_character_schema(connection)
        contract = inspect_inventory_contract(schema, plan.adapter_family)
        if not contract.basic_insert_verified:
            raise RuntimeError("Inventory schema changed since preview")
        state = detect_online_state(connection, schema, plan.char_id)
        if state.online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        if plan.location not in CAPACITY_COLUMNS:
            raise RuntimeError("Destination container is no longer write-enabled")
        slots = inspect_slots(connection, plan.char_id, plan.location)
        if plan.slot != slots.first_free_slot:
            raise RuntimeError("Inventory changed since preview; rebuild the transaction plan")
        if plan.item.rare and _rare_duplicate(connection, plan.char_id, plan.item.item_id):
            raise RuntimeError("Rare-item ownership changed since preview")

        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO `char_inventory` "
                "(`charid`,`location`,`slot`,`itemId`,`quantity`,`bazaar`,`signature`,`extra`) "
                "VALUES (%s,%s,%s,%s,%s,0,'',%s)",
                (
                    plan.char_id,
                    plan.location,
                    plan.slot,
                    plan.item.item_id,
                    plan.quantity,
                    ZERO_EXTRA,
                ),
            )
        finally:
            cursor.close()
        connection.commit()
        inserted = {
            "charid": plan.char_id,
            "location": plan.location,
            "slot": plan.slot,
            "itemId": plan.item.item_id,
            "quantity": plan.quantity,
            "bazaar": 0,
            "signature": "",
            "extra": ZERO_EXTRA,
        }
        result = {
            "status": "committed",
            "char_id": plan.char_id,
            "item_id": plan.item.item_id,
            "quantity": plan.quantity,
            "location": plan.location,
            "location_name": CONTAINERS.get(plan.location, f"Container {plan.location}"),
            "slot": plan.slot,
        }
        return attach_committed_audit(
            result,
            operation="inventory.add",
            char_id=plan.char_id,
            adapter_family=plan.adapter_family,
            target={"table": "char_inventory", "location": plan.location, "slot": plan.slot, "item_id": plan.item.item_id},
            before=None,
            after=inserted,
            metadata={"item": plan.item.as_dict()},
            undo_supported=True,
        )
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
