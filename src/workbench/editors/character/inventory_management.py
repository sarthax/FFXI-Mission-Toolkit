"""Guarded offline inventory row management for the Character Editor.

This layer manages existing ``char_inventory`` rows without decoding or rewriting the opaque
``extra`` payload.  DSP, Topaz, and LSB share the verified core row contract.  Operations are
explicitly limited to quantity changes, moves to containers with directly verifiable capacity,
and removals.  Equipped or bazaar-listed rows are protected from destructive/move operations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from typing import Any

from .adapters.inventory import CORE_COLUMNS, inspect_inventory_contract
from .inventory_slots import CAPACITY_COLUMNS, CONTAINERS, inspect_slots
from .item_catalog import ItemCatalogService
from .schema import discover_character_schema
from .session_state import detect_online_state

_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}
_ACTIONS = {"quantity", "move", "remove"}


@dataclass(frozen=True)
class InventoryManagementIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class InventoryManagementPlan:
    char_id: int
    action: str
    source_location: int
    source_slot: int
    source_fingerprint: str | None
    source: dict[str, Any] | None
    item: dict[str, Any] | None
    quantity_after: int | None
    destination_location: int | None
    destination_slot: int | None
    online: bool | None
    adapter_family: str
    issues: list[InventoryManagementIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.source is not None and self.source_fingerprint is not None and not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "action": self.action,
            "source_location": self.source_location,
            "source_slot": self.source_slot,
            "source_fingerprint": self.source_fingerprint,
            "source": self.source,
            "item": self.item,
            "quantity_after": self.quantity_after,
            "destination_location": self.destination_location,
            "destination_name": CONTAINERS.get(self.destination_location) if self.destination_location is not None else None,
            "destination_slot": self.destination_slot,
            "online": self.online,
            "adapter_family": self.adapter_family,
            "issues": [asdict(i) for i in self.issues],
            "ready": self.ready,
        }


def _inventory_row(connection, char_id: int, location: int, slot: int) -> dict[str, Any] | None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT `charid`,`location`,`slot`,`itemId`,`quantity`,`bazaar`,`signature`,`extra` "
            "FROM `char_inventory` WHERE `charid` = %s AND `location` = %s AND `slot` = %s LIMIT 1",
            (int(char_id), int(location), int(slot)),
        )
        row = cursor.fetchone()
        return dict(zip(CORE_COLUMNS, row)) if row else None
    finally:
        cursor.close()


def _fingerprint(row: dict[str, Any]) -> str:
    extra = row.get("extra")
    if isinstance(extra, memoryview):
        extra = extra.tobytes()
    if isinstance(extra, bytearray):
        extra = bytes(extra)
    parts = (
        int(row.get("charid") or 0),
        int(row.get("location") or 0),
        int(row.get("slot") or 0),
        int(row.get("itemId") or 0),
        int(row.get("quantity") or 0),
        int(row.get("bazaar") or 0),
        str(row.get("signature") or ""),
        bytes(extra or b"").hex(),
    )
    return sha256(repr(parts).encode("utf-8")).hexdigest()


def _equipped_refs(connection, schema, char_id: int, location: int, slot: int) -> list[int]:
    table = schema.table("char_equip")
    required = {"charid", "slotid", "equipslotid", "containerid"}
    if table is None or not required.issubset(table.column_names):
        return []
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT `equipslotid` FROM `char_equip` WHERE `charid` = %s AND `containerid` = %s AND `slotid` = %s",
            (int(char_id), int(location), int(slot)),
        )
        return [int(row[0]) for row in (cursor.fetchall() or [])]
    finally:
        cursor.close()


def _item_record(connection, item_id: int) -> dict[str, Any] | None:
    try:
        record = ItemCatalogService(connection).get(int(item_id))
    except Exception:
        return None
    return record.as_dict() if record else None


def _destination_state(connection, char_id: int, location: int, requested_slot: int | None) -> tuple[int | None, list[InventoryManagementIssue]]:
    issues: list[InventoryManagementIssue] = []
    location = int(location)
    if location not in CAPACITY_COLUMNS:
        issues.append(InventoryManagementIssue(
            "destination_not_safe",
            f"{CONTAINERS.get(location, f'Container {location}')} does not expose directly verifiable char_storage capacity.",
        ))
        return None, issues
    try:
        state = inspect_slots(connection, char_id, location)
    except Exception as exc:
        issues.append(InventoryManagementIssue("destination_unavailable", f"Destination container could not be verified: {exc}"))
        return None, issues
    if state.capacity <= 0:
        issues.append(InventoryManagementIssue("destination_locked", f"{state.name} capacity is zero."))
        return None, issues
    if requested_slot is None:
        if state.first_free_slot is None:
            issues.append(InventoryManagementIssue("destination_full", f"{state.name} has no free slot."))
        return state.first_free_slot, issues
    slot = int(requested_slot)
    if slot < 1 or slot > state.capacity:
        issues.append(InventoryManagementIssue("destination_slot_invalid", f"Destination slot must be between 1 and {state.capacity}."))
        return None, issues
    if slot in set(state.occupied_slots):
        issues.append(InventoryManagementIssue("destination_occupied", f"Destination slot {slot} is already occupied."))
        return None, issues
    return slot, issues


def build_inventory_management_plan(
    connection,
    *,
    char_id: int,
    source_location: int,
    source_slot: int,
    action: str,
    quantity: int | None = None,
    destination_location: int | None = None,
    destination_slot: int | None = None,
    adapter_family: str = "unknown",
) -> InventoryManagementPlan:
    char_id = int(char_id)
    source_location = int(source_location)
    source_slot = int(source_slot)
    action = str(action or "").strip().lower()
    family = str(adapter_family or "unknown").strip().lower()
    issues: list[InventoryManagementIssue] = []

    if char_id <= 0:
        raise ValueError("char_id must be positive")
    if source_location < 0 or source_slot <= 0:
        raise ValueError("source_location must be non-negative and source_slot must be positive")
    if action not in _ACTIONS:
        issues.append(InventoryManagementIssue("action_invalid", "action must be quantity, move, or remove"))
    if family not in _VERIFIED_FAMILIES:
        issues.append(InventoryManagementIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for inventory writes."))

    schema = discover_character_schema(connection)
    contract = inspect_inventory_contract(schema, family)
    if not contract.basic_insert_verified:
        issues.append(InventoryManagementIssue("inventory_schema_drift", "Connected char_inventory schema does not match the verified core contract."))

    state = detect_online_state(connection, schema, char_id)
    if state.online is True:
        issues.append(InventoryManagementIssue("character_online", "Character is online; direct inventory writes are blocked."))
    elif state.online is None:
        issues.append(InventoryManagementIssue("online_state_unknown", "Character online state could not be verified."))

    source = _inventory_row(connection, char_id, source_location, source_slot) if contract.basic_insert_verified else None
    source_fingerprint = _fingerprint(source) if source else None
    item = _item_record(connection, int(source.get("itemId") or 0)) if source else None
    if source is None:
        issues.append(InventoryManagementIssue("source_missing", "No inventory row exists at the requested source location/slot."))
    elif item is None:
        issues.append(InventoryManagementIssue("item_unknown", f"Item ID {source.get('itemId')} is not present in the connected item catalog."))

    equipped = _equipped_refs(connection, schema, char_id, source_location, source_slot) if source else []
    if source and int(source.get("bazaar") or 0) != 0:
        issues.append(InventoryManagementIssue("bazaar_listed", "Bazaar-listed inventory rows are protected from direct administration changes."))
    if action in {"move", "remove"} and equipped:
        issues.append(InventoryManagementIssue("item_equipped", f"Item is referenced by equipment slot(s) {', '.join(map(str, equipped))}; unequip it before moving/removing."))
    if source_location == 3:
        issues.append(InventoryManagementIssue("temporary_items_runtime", "Temporary Items are runtime-managed and are not writable through direct inventory administration."))

    quantity_after: int | None = None
    destination_location_out: int | None = None
    destination_slot_out: int | None = None

    if action == "quantity" and source is not None:
        if quantity is None:
            issues.append(InventoryManagementIssue("quantity_required", "A replacement quantity is required."))
        else:
            quantity_after = int(quantity)
            if quantity_after <= 0:
                issues.append(InventoryManagementIssue("quantity_invalid", "Quantity must be positive; use Remove to delete the row."))
            elif item is not None and quantity_after > int(item.get("stack_size") or 1):
                issues.append(InventoryManagementIssue("stack_limit_exceeded", f"Quantity {quantity_after} exceeds stack size {item.get('stack_size')}."))
            elif quantity_after == int(source.get("quantity") or 0):
                issues.append(InventoryManagementIssue("no_change", "Requested quantity matches the current quantity."))

    if action == "move" and source is not None:
        if destination_location is None:
            issues.append(InventoryManagementIssue("destination_required", "A destination container is required."))
        else:
            destination_location_out = int(destination_location)
            destination_slot_out, destination_issues = _destination_state(connection, char_id, destination_location_out, destination_slot)
            issues.extend(destination_issues)
            if destination_location_out == source_location and destination_slot_out == source_slot:
                issues.append(InventoryManagementIssue("no_change", "Destination is the current inventory location and slot."))

    return InventoryManagementPlan(
        char_id=char_id,
        action=action,
        source_location=source_location,
        source_slot=source_slot,
        source_fingerprint=source_fingerprint,
        source=source,
        item=item,
        quantity_after=quantity_after,
        destination_location=destination_location_out,
        destination_slot=destination_slot_out,
        online=state.online,
        adapter_family=family,
        issues=issues,
    )


def apply_inventory_management(connection, plan: InventoryManagementPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply inventory changes")
    if not plan.ready or plan.source is None or plan.source_fingerprint is None:
        raise RuntimeError("Inventory management plan is not write-ready")

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
        if detect_online_state(connection, schema, plan.char_id).online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")

        source_now = _inventory_row(connection, plan.char_id, plan.source_location, plan.source_slot)
        if source_now is None or _fingerprint(source_now) != plan.source_fingerprint:
            raise RuntimeError("Inventory row changed since preview; preview the operation again")
        if int(source_now.get("bazaar") or 0) != 0:
            raise RuntimeError("Inventory row became bazaar-listed since preview")
        if plan.source_location == 3:
            raise RuntimeError("Temporary Items are runtime-managed")

        if plan.action in {"move", "remove"} and _equipped_refs(connection, schema, plan.char_id, plan.source_location, plan.source_slot):
            raise RuntimeError("Inventory row is equipped; unequip it before moving/removing")

        if plan.action == "quantity":
            if plan.quantity_after is None:
                raise RuntimeError("Quantity plan has no target quantity")
            item = _item_record(connection, int(source_now.get("itemId") or 0))
            if item is None or plan.quantity_after < 1 or plan.quantity_after > int(item.get("stack_size") or 1):
                raise RuntimeError("Item catalog or stack limit changed since preview")
        elif plan.action == "move":
            if plan.destination_location is None or plan.destination_slot is None:
                raise RuntimeError("Move plan has no verified destination")
            destination_slot, destination_issues = _destination_state(
                connection, plan.char_id, plan.destination_location, plan.destination_slot
            )
            if destination_issues or destination_slot != plan.destination_slot:
                raise RuntimeError("Destination changed since preview; preview the move again")
        elif plan.action != "remove":
            raise RuntimeError("Unsupported inventory operation")

        cursor = connection.cursor()
        try:
            if plan.action == "quantity":
                cursor.execute(
                    "UPDATE `char_inventory` SET `quantity` = %s WHERE `charid` = %s AND `location` = %s AND `slot` = %s",
                    (plan.quantity_after, plan.char_id, plan.source_location, plan.source_slot),
                )
            elif plan.action == "move":
                cursor.execute(
                    "UPDATE `char_inventory` SET `location` = %s, `slot` = %s WHERE `charid` = %s AND `location` = %s AND `slot` = %s",
                    (plan.destination_location, plan.destination_slot, plan.char_id, plan.source_location, plan.source_slot),
                )
            else:
                cursor.execute(
                    "DELETE FROM `char_inventory` WHERE `charid` = %s AND `location` = %s AND `slot` = %s LIMIT 1",
                    (plan.char_id, plan.source_location, plan.source_slot),
                )
            if getattr(cursor, "rowcount", 1) != 1:
                raise RuntimeError("Inventory operation did not change exactly one row")
        finally:
            cursor.close()

        connection.commit()
        return {
            "status": "committed",
            "char_id": plan.char_id,
            "action": plan.action,
            "item_id": int(plan.source.get("itemId") or 0),
            "source_location": plan.source_location,
            "source_slot": plan.source_slot,
            "quantity_after": plan.quantity_after,
            "destination_location": plan.destination_location,
            "destination_slot": plan.destination_slot,
        }
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
