"""Preview-only Character Editor actions.

The GUI can invoke these contracts from either a character-centric or catalog-centric flow.
No SQL mutation is performed here.  Adapters must later turn a validated preview into a
transaction after lineage-specific write semantics are verified.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AddItemRequest:
    char_id: int
    item_id: int
    quantity: int = 1
    container: int | str | None = None
    slot: int | None = None
    extra: bytes | str | None = None
    source: str = "character_inventory"


@dataclass(frozen=True)
class ActionWarning:
    code: str
    message: str
    blocking: bool = False


@dataclass
class ActionPreview:
    action: str
    adapter: str
    char_id: int
    payload: dict[str, Any]
    warnings: list[ActionWarning] = field(default_factory=list)
    write_ready: bool = False

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["warnings"] = [asdict(w) for w in self.warnings]
        return out


def normalize_add_item_request(request: AddItemRequest) -> AddItemRequest:
    char_id = int(request.char_id)
    item_id = int(request.item_id)
    quantity = int(request.quantity)
    slot = None if request.slot is None else int(request.slot)
    if char_id <= 0:
        raise ValueError("char_id must be positive")
    if item_id <= 0:
        raise ValueError("item_id must be positive")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if slot is not None and slot < 0:
        raise ValueError("slot cannot be negative")
    return AddItemRequest(
        char_id=char_id,
        item_id=item_id,
        quantity=quantity,
        container=request.container,
        slot=slot,
        extra=request.extra,
        source=str(request.source or "character_inventory"),
    )


def preview_add_item(
    request: AddItemRequest,
    *,
    adapter_family: str,
    inventory_supported: bool,
    character_found: bool,
    character_online: bool | None = None,
    item_known: bool | None = None,
    stack_limit: int | None = None,
    destination_known: bool | None = None,
    adapter_write_verified: bool = False,
) -> ActionPreview:
    """Build a deterministic add-item preview without performing a write."""
    req = normalize_add_item_request(request)
    warnings: list[ActionWarning] = []

    if not character_found:
        warnings.append(ActionWarning("character_not_found", "Character does not exist.", True))
    if not inventory_supported:
        warnings.append(ActionWarning(
            "inventory_not_supported",
            "Connected server schema does not expose a recognized character inventory capability.",
            True,
        ))
    if character_online is True:
        warnings.append(ActionWarning(
            "character_online",
            "Character appears to be online; direct database inventory edits may be overwritten by map-server state.",
            True,
        ))
    elif character_online is None:
        warnings.append(ActionWarning(
            "online_state_unknown",
            "Character online state could not be verified.",
            False,
        ))
    if item_known is False:
        warnings.append(ActionWarning("item_unknown", "Item ID is not present in the resolved item catalog.", True))
    elif item_known is None:
        warnings.append(ActionWarning("item_catalog_unavailable", "Item catalog validation was not available.", False))
    if stack_limit is not None and req.quantity > int(stack_limit):
        warnings.append(ActionWarning(
            "stack_limit_exceeded",
            f"Requested quantity {req.quantity} exceeds the item stack limit {int(stack_limit)}.",
            True,
        ))
    if destination_known is False:
        warnings.append(ActionWarning(
            "destination_invalid",
            "Requested inventory container/slot is not valid for this server adapter.",
            True,
        ))
    if not adapter_write_verified:
        warnings.append(ActionWarning(
            "adapter_write_unverified",
            f"{adapter_family or 'unknown'} inventory write semantics are not yet verified.",
            True,
        ))

    blocking = any(w.blocking for w in warnings)
    return ActionPreview(
        action="add_item",
        adapter=adapter_family or "unknown",
        char_id=req.char_id,
        payload={
            "item_id": req.item_id,
            "quantity": req.quantity,
            "container": req.container,
            "slot": req.slot,
            "extra_present": req.extra is not None,
            "source": req.source,
        },
        warnings=warnings,
        write_ready=not blocking,
    )
