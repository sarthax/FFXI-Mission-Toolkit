"""Preview-only Auction House administrative action contracts.

This module deliberately performs no SQL mutation. It normalizes administrator intent and
produces deterministic previews that later apply endpoints can bind to fresh database snapshots.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActionWarning:
    code: str
    message: str
    blocking: bool = False


@dataclass(frozen=True)
class ListItemRequest:
    item_id: int
    seller_id: int
    price: int
    stack: bool = False


@dataclass(frozen=True)
class PurchaseRequest:
    auction_id: int
    buyer_id: int | None = None
    mode: str = "admin_cleanup"


@dataclass
class ActionPreview:
    action: str
    adapter: str
    payload: dict[str, Any]
    snapshot: dict[str, Any]
    economic_effect: dict[str, Any]
    warnings: list[ActionWarning] = field(default_factory=list)
    apply_supported: bool = False

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["warnings"] = [asdict(w) for w in self.warnings]
        # Presentation-time provenance is best-effort here so isolated unit callers that have no
        # configured server environment retain the original pure preview contract. The AH GUI
        # always has an active environment and therefore receives the normalized envelope.
        try:
            from workbench.runtime.legacy_settings import get_active_server_identity, get_active_server_root
            from .config_policy import load_active_legacy_policy
            from .lsb_policy import load_lsb_policy, preview_lsb_policy_binding
            from .policy_binding import preview_policy_binding
            from .preview_provenance import make_preview_provenance

            identity = get_active_server_identity()
            root = get_active_server_root()
            family = str(identity.get("family") or "").strip().lower()
            policy_binding: dict[str, Any] | None = None
            if root is not None and family in {"dsp", "topaz"}:
                policy_binding = preview_policy_binding(load_active_legacy_policy(server_root=root, family=family))
            elif root is not None and family == "lsb":
                policy_binding = preview_lsb_policy_binding(load_lsb_policy(root))
            if identity and root is not None:
                out["preview_provenance"] = make_preview_provenance(
                    environment=identity,
                    schema_family_hint=self.adapter,
                    policy_binding=policy_binding,
                    action=self.action,
                    adapter=self.adapter,
                )
        except Exception:
            pass
        return out


def normalize_list_request(request: ListItemRequest) -> ListItemRequest:
    item_id = int(request.item_id)
    seller_id = int(request.seller_id)
    price = int(request.price)
    if item_id <= 0:
        raise ValueError("item_id must be positive")
    if seller_id <= 0:
        raise ValueError("seller_id must be positive")
    if price <= 0:
        raise ValueError("price must be positive")
    return ListItemRequest(item_id=item_id, seller_id=seller_id, price=price, stack=bool(request.stack))


def normalize_purchase_request(request: PurchaseRequest) -> PurchaseRequest:
    auction_id = int(request.auction_id)
    buyer_id = None if request.buyer_id is None else int(request.buyer_id)
    mode = str(request.mode or "admin_cleanup").strip().lower()
    if auction_id <= 0:
        raise ValueError("auction_id must be positive")
    if buyer_id is not None and buyer_id <= 0:
        raise ValueError("buyer_id must be positive when supplied")
    if mode not in {"admin_cleanup", "normal_purchase"}:
        raise ValueError("mode must be admin_cleanup or normal_purchase")
    if mode == "normal_purchase" and buyer_id is None:
        raise ValueError("normal_purchase requires buyer_id")
    return PurchaseRequest(auction_id=auction_id, buyer_id=buyer_id, mode=mode)


def preview_list_item(
    request: ListItemRequest,
    *,
    adapter_family: str,
    item: dict[str, Any] | None,
    seller: dict[str, Any] | None,
) -> ActionPreview:
    req = normalize_list_request(request)
    warnings: list[ActionWarning] = []
    if item is None:
        warnings.append(ActionWarning("item_not_found", "Item does not exist in item_basic.", True))
    elif int(item.get("category_id") or 0) <= 0:
        warnings.append(ActionWarning("item_not_auctionable", "Item is not assigned to an Auction House category.", True))
    if seller is None:
        warnings.append(ActionWarning("seller_not_found", "Seller character does not exist.", True))
    stack_size = max(1, int((item or {}).get("stack_size") or 1))
    if req.stack and stack_size <= 1:
        warnings.append(ActionWarning("not_stackable", "Item cannot be listed as a stack.", True))
    warnings.append(ActionWarning(
        "preview_only",
        "Auction House write/apply operations are not enabled in this phase; this preview cannot change server state.",
        True,
    ))
    quantity = stack_size if req.stack else 1
    return ActionPreview(
        action="list_item",
        adapter=adapter_family or "unknown",
        payload={"item_id": req.item_id, "seller_id": req.seller_id, "price": req.price, "stack": req.stack},
        snapshot={"item": item, "seller": seller},
        economic_effect={
            "listing_price": req.price,
            "quantity": quantity,
            "price_per_item": round(req.price / quantity, 2),
            "gil_created": 0,
            "gil_removed": 0,
        },
        warnings=warnings,
        apply_supported=False,
    )


def preview_purchase(
    request: PurchaseRequest,
    *,
    adapter_family: str,
    listing: dict[str, Any] | None,
    buyer: dict[str, Any] | None = None,
) -> ActionPreview:
    req = normalize_purchase_request(request)
    warnings: list[ActionWarning] = []
    if listing is None:
        warnings.append(ActionWarning("auction_not_found", "Active auction does not exist or is already sold.", True))
    if req.mode == "normal_purchase" and buyer is None:
        warnings.append(ActionWarning("buyer_not_found", "Buyer character does not exist.", True))
    warnings.append(ActionWarning(
        "preview_only",
        "Auction House write/apply operations are not enabled in this phase; this preview cannot change server state.",
        True,
    ))
    asking = int((listing or {}).get("asking_price") or 0)
    effect = {
        "mode": req.mode,
        "remove_active_listing": listing is not None,
        "seller_compensation": asking if listing is not None else 0,
        "buyer_charge": asking if req.mode == "normal_purchase" and listing is not None else 0,
        "admin_economy_injection": asking if req.mode == "admin_cleanup" and listing is not None else 0,
    }
    return ActionPreview(
        action="purchase_item",
        adapter=adapter_family or "unknown",
        payload={"auction_id": req.auction_id, "buyer_id": req.buyer_id, "mode": req.mode},
        snapshot={"listing": listing, "buyer": buyer},
        economic_effect=effect,
        warnings=warnings,
        apply_supported=False,
    )
