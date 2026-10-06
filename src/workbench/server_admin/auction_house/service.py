"""SELECT-only Auction House administration queries."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .categories import category_metadata
from .schema import AuctionHouseSchema, discover_auction_house_schema, sellable_clause


def epoch_iso(value: Any) -> str | None:
    try:
        stamp = int(value or 0)
        return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat() if stamp > 0 else None
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class AuctionHouseService:
    """Normalized live AH reader. Administrative preview helpers remain SELECT-only."""

    def __init__(self, connection, *, schema: AuctionHouseSchema | None = None):
        self.connection = connection
        self.schema = schema or discover_auction_house_schema(connection)

    @staticmethod
    def q(name: str) -> str:
        return f"`{name}`"

    def status(self) -> dict[str, Any]:
        return self.schema.public_dict()

    def categories(self) -> list[dict[str, Any]]:
        i = self.schema.item_columns
        c = self.connection.cursor()
        try:
            c.execute(
                f"SELECT {self.q(i['ah_category'])}, COUNT(*) FROM `item_basic` "
                f"WHERE {sellable_clause(i, self.q)} GROUP BY {self.q(i['ah_category'])} "
                f"ORDER BY {self.q(i['ah_category'])}"
            )
            rows = []
            for r in c.fetchall() or []:
                category_id = int(r[0])
                meta = category_metadata(category_id)
                rows.append({
                    "category_id": category_id,
                    "group": meta.group,
                    "label": meta.label,
                    "path": meta.path,
                    "item_count": int(r[1]),
                })
            return rows
        finally:
            c.close()

    def item_snapshot(self, item_id: int) -> dict[str, Any] | None:
        i = self.schema.item_columns
        c = self.connection.cursor()
        try:
            c.execute(
                f"SELECT {self.q(i['item_id'])}, {self.q(i['name'])}, {self.q(i['stack_size'])}, "
                f"{self.q(i['ah_category'])} FROM `item_basic` WHERE {self.q(i['item_id'])}=%s LIMIT 1",
                (int(item_id),),
            )
            r = c.fetchone()
            if not r:
                return None
            category_id = int(r[3] or 0)
            meta = category_metadata(category_id)
            return {
                "item_id": int(r[0]),
                "name": str(r[1] or ""),
                "stack_size": max(1, int(r[2] or 1)),
                "category_id": category_id,
                "category_path": meta.path,
            }
        finally:
            c.close()

    def character_snapshot(self, char_id: int) -> dict[str, Any] | None:
        """Resolve the common DSP/Topaz/LSB chars identity shape without assuming extra fields."""
        c = self.connection.cursor()
        try:
            c.execute("DESCRIBE `chars`")
            columns = {str(row[0]) for row in c.fetchall() or []}
            id_col = next((name for name in ("charid", "charId", "char_id", "id") if name in columns), None)
            name_col = next((name for name in ("charname", "charName", "char_name", "name") if name in columns), None)
            if not id_col or not name_col:
                return None
            c.execute(
                f"SELECT {self.q(id_col)}, {self.q(name_col)} FROM `chars` WHERE {self.q(id_col)}=%s LIMIT 1",
                (int(char_id),),
            )
            r = c.fetchone()
            return None if not r else {"char_id": int(r[0]), "char_name": str(r[1] or "")}
        finally:
            c.close()

    def active_listing_by_id(self, auction_id: int) -> dict[str, Any] | None:
        a = self.schema.auction_columns
        seller_name = self.q(a["seller_name"]) if a.get("seller_name") else "NULL"
        c = self.connection.cursor()
        try:
            c.execute(
                "SELECT "
                f"{self.q(a['id'])}, {self.q(a['item_id'])}, {self.q(a['stack'])}, {self.q(a['seller_id'])}, "
                f"{seller_name}, {self.q(a['listed_at'])}, {self.q(a['asking_price'])} FROM `auction_house` "
                f"WHERE {self.q(a['id'])}=%s AND {self.q(a['sold_at'])}=0 LIMIT 1",
                (int(auction_id),),
            )
            r = c.fetchone()
            if not r:
                return None
            return {
                "auction_id": int(r[0]),
                "item_id": int(r[1]),
                "stack": bool(r[2]),
                "seller_id": int(r[3] or 0),
                "seller_name": r[4],
                "listed_at": int(r[5] or 0) or None,
                "listed_at_iso": epoch_iso(r[5]),
                "asking_price": int(r[6] or 0),
            }
        finally:
            c.close()

    def active_listings(self, item_id: int, *, limit: int = 200) -> list[dict[str, Any]]:
        a = self.schema.auction_columns
        seller_name = self.q(a["seller_name"]) if a.get("seller_name") else "NULL"
        c = self.connection.cursor()
        try:
            c.execute(
                "SELECT "
                f"{self.q(a['id'])}, {self.q(a['stack'])}, {self.q(a['seller_id'])}, {seller_name}, "
                f"{self.q(a['listed_at'])}, {self.q(a['asking_price'])} FROM `auction_house` "
                f"WHERE {self.q(a['item_id'])}=%s AND {self.q(a['sold_at'])}=0 "
                f"ORDER BY {self.q(a['listed_at'])} ASC LIMIT %s",
                (int(item_id), max(1, min(int(limit), 1000))),
            )
            return [
                {"auction_id": int(r[0]), "stack": bool(r[1]), "seller_id": int(r[2] or 0),
                 "seller_name": r[3], "listed_at": int(r[4] or 0) or None,
                 "listed_at_iso": epoch_iso(r[4]), "asking_price": int(r[5] or 0)}
                for r in c.fetchall() or []
            ]
        finally:
            c.close()

    def sale_history(self, item_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        a = self.schema.auction_columns
        seller_name = self.q(a["seller_name"]) if a.get("seller_name") else "NULL"
        buyer_name = self.q(a["buyer_name"]) if a.get("buyer_name") else "NULL"
        buyer_id = self.q(a["buyer_id"]) if a.get("buyer_id") else "NULL"
        c = self.connection.cursor()
        try:
            c.execute(
                "SELECT "
                f"{self.q(a['id'])}, {self.q(a['stack'])}, {self.q(a['seller_id'])}, {seller_name}, "
                f"{buyer_id}, {buyer_name}, {self.q(a['sale_price'])}, {self.q(a['sold_at'])} "
                "FROM `auction_house` "
                f"WHERE {self.q(a['item_id'])}=%s AND {self.q(a['sold_at'])}>0 "
                f"ORDER BY {self.q(a['sold_at'])} DESC LIMIT %s",
                (int(item_id), max(1, min(int(limit), 1000))),
            )
            rows = []
            for r in c.fetchall() or []:
                rows.append({
                    "auction_id": int(r[0]), "stack": bool(r[1]), "seller_id": int(r[2] or 0),
                    "seller_name": r[3], "buyer_id": None if r[4] is None else int(r[4] or 0),
                    "buyer_name": r[5], "sale_price": int(r[6] or 0), "sold_at": int(r[7] or 0),
                    "sold_at_iso": epoch_iso(r[7]),
                })
            return rows
        finally:
            c.close()
