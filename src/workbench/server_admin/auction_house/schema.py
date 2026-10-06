"""Runtime schema discovery for DSP, Topaz, and LandSandBoat Auction House data.

The read-only administration surface intentionally discovers the live schema instead of assuming
that a configured checkout perfectly matches an upstream lineage. Forks commonly retain old AH
layouts. Only columns proven present by DESCRIBE are ever referenced by the service.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AuctionHouseSchema:
    auction_columns: dict[str, str]
    item_columns: dict[str, str]
    family_hint: str
    capabilities: tuple[str, ...]

    def auction(self, logical: str) -> str | None:
        return self.auction_columns.get(logical)

    def item(self, logical: str) -> str | None:
        return self.item_columns.get(logical)

    def public_dict(self) -> dict[str, object]:
        return {
            "family_hint": self.family_hint,
            "capabilities": list(self.capabilities),
            "auction_columns": dict(self.auction_columns),
            "item_columns": dict(self.item_columns),
            "read_only": True,
        }


ITEM_FLAG_NOAUCTION = 0x0040   # item_basic.flags bit: cannot be sold on the AH
UNSELLABLE_CATEGORY = 99        # aH value this data uses for items with no AH category


def sellable_clause(item_columns: dict, qn, alias: str = "") -> str:
    """SQL predicate: an AH category is assigned and the NoAuction flag is clear."""
    p = f"{alias}." if alias else ""
    cat = f"{p}{qn(item_columns['ah_category'])}"
    sql = f"{cat} > 0 AND {cat} < {UNSELLABLE_CATEGORY}"
    if item_columns.get("flags"):
        sql += f" AND ({p}{qn(item_columns['flags'])} & {ITEM_FLAG_NOAUCTION}) = 0"
    return sql


def _columns(connection, table: str) -> set[str]:
    cursor = connection.cursor()
    try:
        cursor.execute(f"DESCRIBE `{table}`")
        return {str(row[0]) for row in cursor.fetchall() or []}
    finally:
        cursor.close()


def _pick(names: set[str], candidates: Iterable[str], *, required: bool = False) -> str | None:
    for candidate in candidates:
        if candidate in names:
            return candidate
    if required:
        joined = ", ".join(candidates)
        raise RuntimeError(f"live schema is missing required column; expected one of: {joined}")
    return None


def discover_auction_house_schema(connection) -> AuctionHouseSchema:
    ah = _columns(connection, "auction_house")
    items = _columns(connection, "item_basic")

    auction_candidates = {
        "id": ("id",),
        "item_id": ("itemid", "itemId", "item_id"),
        "stack": ("stack",),
        "seller_id": ("seller", "seller_id", "sellerId"),
        "seller_name": ("seller_name", "sellerName"),
        "listed_at": ("date", "list_date", "listed_at"),
        "asking_price": ("price", "asking_price"),
        "buyer_id": ("buyer", "buyer_id", "buyerId"),
        "buyer_name": ("buyer_name", "buyerName"),
        "sale_price": ("sale", "sale_price"),
        "sold_at": ("sell_date", "sellDate", "sold_at"),
    }
    required_ah = {"id", "item_id", "stack", "seller_id", "listed_at", "asking_price", "sale_price", "sold_at"}
    auction_columns: dict[str, str] = {}
    for logical, candidates in auction_candidates.items():
        value = _pick(ah, candidates, required=logical in required_ah)
        if value:
            auction_columns[logical] = value

    item_candidates = {
        "item_id": ("itemid", "itemId", "item_id", "id"),
        "name": ("name",),
        "stack_size": ("stackSize", "stacksize", "stack_size", "stack"),
        "ah_category": ("aH", "ah", "auction_house_category"),
        "flags": ("flags",),
    }
    required_items = {"item_id", "name", "stack_size", "ah_category"}
    item_columns: dict[str, str] = {}
    for logical, candidates in item_candidates.items():
        value = _pick(items, candidates, required=logical in required_items)
        if value:
            item_columns[logical] = value

    # Current LandSandBoat added the numeric buyer column; historical Topaz/DSP layouts do not
    # have it. This is a shape hint, not a claim about a fork's identity.
    family_hint = "lsb-compatible" if "buyer_id" in auction_columns else "legacy-dsp-topaz-compatible"
    capabilities = ["categories", "item_search", "active_listings", "sale_history", "price_trends", "economy_summary"]
    if "seller_name" in auction_columns:
        capabilities.append("seller_names")
    if "buyer_name" in auction_columns:
        capabilities.append("buyer_names")
    if "buyer_id" in auction_columns:
        capabilities.append("buyer_ids")

    return AuctionHouseSchema(
        auction_columns=auction_columns,
        item_columns=item_columns,
        family_hint=family_hint,
        capabilities=tuple(capabilities),
    )
