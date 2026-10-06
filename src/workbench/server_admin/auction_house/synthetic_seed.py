"""Bounded DSP/Topaz TEST-only synthetic Auction House category seeding."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .legacy_test_executor import (
    LegacyTestExecutionBlocked,
    evaluate_legacy_test_write_gate,
    execute_legacy_test_synthetic_listing,
)

_MAX_ITEMS = 250
_MAX_COPIES_PER_ITEM = 5
_MAX_ROWS = 500
_STACK_MODES = {"single", "stack", "auto"}


@dataclass(frozen=True)
class SeedItem:
    item_id: int
    item_name: str
    stack_size: int
    category_id: int
    stack: bool
    copies: int
    price: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _category_items(service, *, category_id: int, stack_mode: str, copies_per_item: int, price: int, limit_items: int) -> list[SeedItem]:
    category_id = int(category_id)
    copies_per_item = int(copies_per_item)
    price = int(price)
    limit_items = int(limit_items)
    stack_mode = str(stack_mode or "").strip().lower()
    if category_id <= 0 or price <= 0:
        raise LegacyTestExecutionBlocked("category_id and price must be positive")
    if stack_mode not in _STACK_MODES:
        raise LegacyTestExecutionBlocked("stack_mode must be single, stack, or auto")
    if not 1 <= copies_per_item <= _MAX_COPIES_PER_ITEM:
        raise LegacyTestExecutionBlocked(f"copies_per_item must be between 1 and {_MAX_COPIES_PER_ITEM}")
    if not 1 <= limit_items <= _MAX_ITEMS:
        raise LegacyTestExecutionBlocked(f"limit_items must be between 1 and {_MAX_ITEMS}")
    if copies_per_item * limit_items > _MAX_ROWS:
        raise LegacyTestExecutionBlocked(f"Requested seed exceeds {_MAX_ROWS} listing rows")

    i = service.schema.item_columns
    required = ("item_id", "name", "stack_size", "ah_category")
    if any(not i.get(name) for name in required):
        raise LegacyTestExecutionBlocked("Item schema is missing category-seed columns")

    cursor = service.connection.cursor()
    try:
        cursor.execute(
            f"SELECT `{i['item_id']}`,`{i['name']}`,`{i['stack_size']}`,`{i['ah_category']}` "
            f"FROM `item_basic` WHERE `{i['ah_category']}`=%s AND ({i.get('flags') and '`'+i['flags']+'` & 64' or '0'})=0 ORDER BY `{i['item_id']}` ASC LIMIT %s",
            (category_id, limit_items),
        )
        rows = list(cursor.fetchall() or [])
    finally:
        cursor.close()

    result: list[SeedItem] = []
    for row in rows:
        item_id = int(row[0] or 0)
        name = str(row[1] or "")
        stack_size = max(1, int(row[2] or 1))
        actual_category = int(row[3] or 0)
        if item_id <= 0 or actual_category != category_id:
            continue
        if stack_mode == "stack" and stack_size <= 1:
            continue
        stack = stack_mode == "stack" or (stack_mode == "auto" and stack_size > 1)
        result.append(SeedItem(
            item_id=item_id,
            item_name=name,
            stack_size=stack_size,
            category_id=actual_category,
            stack=stack,
            copies=copies_per_item,
            price=price,
        ))
    return result


def preview_synthetic_category_seed(
    *, service, category_id: int, price: int, stack_mode: str = "single",
    copies_per_item: int = 1, limit_items: int = 100,
) -> dict[str, Any]:
    items = _category_items(
        service,
        category_id=category_id,
        stack_mode=stack_mode,
        copies_per_item=copies_per_item,
        price=price,
        limit_items=limit_items,
    )
    rows = sum(item.copies for item in items)
    units = sum((item.stack_size if item.stack else 1) * item.copies for item in items)
    return {
        "operation": "synthetic_category_seed_preview",
        "category_id": int(category_id),
        "price": int(price),
        "stack_mode": str(stack_mode).strip().lower(),
        "copies_per_item": int(copies_per_item),
        "limit_items": int(limit_items),
        "item_count": len(items),
        "listing_rows": rows,
        "supply_units": units,
        "max_listing_rows": _MAX_ROWS,
        "items": [item.as_dict() for item in items],
        "synthetic": True,
        "note": "Preview only. No player inventory is removed and no AH listing fee is charged for synthetic supply.",
    }


def execute_synthetic_category_seed(
    *,
    service,
    environment: dict[str, Any],
    seller_id: int,
    category_id: int,
    price: int,
    stack_mode: str,
    copies_per_item: int,
    limit_items: int,
    confirmation: str,
    feature_enabled: bool | None = None,
) -> dict[str, Any]:
    gate = evaluate_legacy_test_write_gate(
        environment=environment,
        schema_family_hint=service.schema.family_hint,
        confirmation=confirmation,
        feature_enabled=feature_enabled,
    )
    if not gate.ready:
        codes = ", ".join(issue.code for issue in gate.issues if issue.blocking)
        raise LegacyTestExecutionBlocked(f"Auction House legacy TEST execution blocked: {codes}")

    seller_id = int(seller_id)
    if seller_id <= 0:
        raise LegacyTestExecutionBlocked("seller_id must be positive")
    seller = service.character_snapshot(seller_id)
    if not seller:
        raise LegacyTestExecutionBlocked("Synthetic seed seller character does not exist")

    preview = preview_synthetic_category_seed(
        service=service,
        category_id=category_id,
        price=price,
        stack_mode=stack_mode,
        copies_per_item=copies_per_item,
        limit_items=limit_items,
    )
    if not preview["items"]:
        raise LegacyTestExecutionBlocked("No Auction House items matched the requested category and stack mode")

    results: list[dict[str, Any]] = []
    committed = 0
    failed = 0
    injected_units = 0
    for item in preview["items"]:
        for copy_index in range(int(item["copies"])):
            try:
                result = execute_legacy_test_synthetic_listing(
                    service=service,
                    environment=environment,
                    item_id=int(item["item_id"]),
                    seller_id=seller_id,
                    price=int(item["price"]),
                    stack=bool(item["stack"]),
                    confirmation=confirmation,
                    feature_enabled=feature_enabled,
                )
                committed += 1
                injected_units += int(result.get("quantity") or 0)
                results.append({
                    "item_id": int(item["item_id"]),
                    "item_name": item["item_name"],
                    "copy": copy_index + 1,
                    "status": "committed",
                    "auction_id": result.get("auction_id"),
                    "quantity": result.get("quantity"),
                })
            except Exception as exc:
                failed += 1
                results.append({
                    "item_id": int(item["item_id"]),
                    "item_name": item["item_name"],
                    "copy": copy_index + 1,
                    "status": "failed",
                    "error": str(exc),
                })

    return {
        "status": "completed" if failed == 0 else ("failed" if committed == 0 else "partial"),
        "operation": "synthetic_category_seed",
        "test_only": True,
        "synthetic": True,
        "seller_id": seller_id,
        "seller_name": seller.get("char_name"),
        "category_id": int(category_id),
        "stack_mode": str(stack_mode).strip().lower(),
        "price": int(price),
        "attempted": committed + failed,
        "committed": committed,
        "failed": failed,
        "injected_supply_units": injected_units,
        "listing_fee_charged": 0,
        "seller_inventory_removed": 0,
        "partial_success_possible": True,
        "results": results,
    }
