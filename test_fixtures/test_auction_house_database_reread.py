from __future__ import annotations

from pathlib import Path

from workbench.server_admin.auction_house.database_reread import (
    collect_legacy_reread,
    prepare_from_database_reread,
)


class _Schema:
    family_hint = "legacy-dsp-topaz-compatible"
    auction_columns = {
        "id": "id",
        "item_id": "itemid",
        "stack": "stack",
        "seller_id": "seller",
        "sold_at": "sell_date",
        "asking_price": "price",
    }


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self._rows = []

    def execute(self, sql, params=()):
        self.connection.statements.append((sql, tuple(params or ())))
        upper = sql.upper()
        if upper == "START TRANSACTION READ ONLY":
            self._rows = []
        elif upper.startswith("DESCRIBE `CHARS`"):
            self._rows = [("charid",), ("charname",), ("gil",)]
        elif upper.startswith("DESCRIBE `CHAR_INVENTORY`"):
            self._rows = [("charid",), ("itemId",), ("quantity",), ("location",), ("slot",)]
        elif upper.startswith("DESCRIBE `DELIVERY_BOX`"):
            self._rows = [("charid",), ("box",), ("slot",), ("itemid",), ("quantity",), ("sender",)]
        elif "SELECT `GIL` FROM `CHARS`" in upper:
            char_id = int(params[0])
            self._rows = [(self.connection.gil.get(char_id),)] if char_id in self.connection.gil else []
        elif "SELECT COUNT(*) FROM `AUCTION_HOUSE`" in upper:
            self._rows = [(self.connection.active_listing_count,)]
        elif "FROM `CHAR_INVENTORY`" in upper:
            char_id, item_id = map(int, params)
            self._rows = list(self.connection.inventory.get((char_id, item_id), []))
        elif "FROM `DELIVERY_BOX`" in upper:
            char_id = int(params[0])
            self._rows = list(self.connection.delivery.get(char_id, []))
        elif "SELECT `ID` FROM `AUCTION_HOUSE`" in upper:
            self._rows = [] if self.connection.cheapest_id is None else [(self.connection.cheapest_id,)]
        else:
            raise AssertionError(f"Unexpected SQL in reread fixture: {sql}")

    def fetchone(self):
        return None if not self._rows else self._rows[0]

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class _Connection:
    def __init__(self):
        self.statements = []
        self.rollback_count = 0
        self.gil = {100: 50000, 200: 90000}
        self.active_listing_count = 2
        self.inventory = {
            (100, 4096): [(100, 4096, 12, 0, 3)],
            (200, 4096): [(200, 4096, 1, 0, 4)],
        }
        self.delivery = {100: [(100, 1, 0, 0, 12000, "AH")], 200: []}
        self.cheapest_id = 55

    def cursor(self):
        return _Cursor(self)

    def rollback(self):
        self.rollback_count += 1


class _Service:
    def __init__(self, connection):
        self.connection = connection
        self.schema = _Schema()
        self.item = {"item_id": 4096, "name": "test item", "stack_size": 12, "category_id": 9, "category_path": "Weapons"}
        self.characters = {
            100: {"char_id": 100, "char_name": "Seller"},
            200: {"char_id": 200, "char_name": "Buyer"},
        }
        self.listing = {
            "auction_id": 55,
            "item_id": 4096,
            "stack": False,
            "seller_id": 100,
            "seller_name": "Seller",
            "listed_at": 123456,
            "listed_at_iso": None,
            "asking_price": 12000,
        }

    def item_snapshot(self, item_id):
        return dict(self.item) if int(item_id) == 4096 else None

    def character_snapshot(self, char_id):
        value = self.characters.get(int(char_id))
        return None if value is None else dict(value)

    def active_listing_by_id(self, auction_id):
        return dict(self.listing) if int(auction_id) == 55 and self.listing is not None else None


def _env(family="topaz"):
    return {"profile_id": 9, "name": "Legacy Test", "environment": "test", "family": family, "enabled": True, "is_active": True}


def _list_preview(service):
    return {
        "payload": {"item_id": 4096, "seller_id": 100, "price": 12000, "stack": True},
        "snapshot": {"item": dict(service.item), "seller": dict(service.characters[100])},
    }


def _purchase_preview(service):
    return {
        "payload": {"auction_id": 55, "buyer_id": 200, "mode": "normal_purchase"},
        "snapshot": {"listing": dict(service.listing), "buyer": dict(service.characters[200])},
    }


def test_listing_reread_collects_database_evidence_and_rolls_back():
    connection = _Connection()
    service = _Service(connection)
    evidence = collect_legacy_reread(service=service, operation="list_item", preview=_list_preview(service))

    assert evidence.snapshot["item"]["item_id"] == 4096
    assert evidence.seller_gil == 50000
    assert evidence.seller_active_listing_count == 2
    assert evidence.inventory_rows[0]["quantity"] == 12
    assert evidence.delivery_rows[0]["charid"] == 100
    assert evidence.transaction_mode == "read_only_rolled_back"
    assert connection.rollback_count == 1
    assert connection.statements[0][0] == "START TRANSACTION READ ONLY"


def test_purchase_reread_collects_buyer_seller_and_cheapest_listing():
    connection = _Connection()
    service = _Service(connection)
    evidence = collect_legacy_reread(service=service, operation="purchase_item", preview=_purchase_preview(service))

    assert evidence.snapshot["listing"]["auction_id"] == 55
    assert evidence.snapshot["buyer"]["char_id"] == 200
    assert evidence.seller_gil == 50000
    assert evidence.buyer_gil == 90000
    assert evidence.claim_count == 1
    assert evidence.cheapest_qualifying_auction_id == 55
    assert connection.rollback_count == 1


def test_database_reread_feeds_existing_stale_state_gate():
    connection = _Connection()
    service = _Service(connection)
    preview = _purchase_preview(service)

    prepared, evidence = prepare_from_database_reread(
        service=service,
        family="topaz",
        operation="purchase_item",
        environment=_env("topaz"),
        preview=preview,
        preview_environment=_env("topaz"),
    )
    assert prepared.validation_ready is True
    assert prepared.executable is False
    assert evidence.cheapest_qualifying_auction_id == 55

    service.listing["asking_price"] = 13000
    stale, _ = prepare_from_database_reread(
        service=service,
        family="topaz",
        operation="purchase_item",
        environment=_env("topaz"),
        preview=preview,
        preview_environment=_env("topaz"),
    )
    assert any(issue.code == "stale_preview" for issue in stale.issues)
    assert stale.executable is False


def test_cheapest_listing_change_blocks_normal_purchase():
    connection = _Connection()
    connection.cheapest_id = 54
    service = _Service(connection)
    prepared, _ = prepare_from_database_reread(
        service=service,
        family="dsp",
        operation="purchase_item",
        environment=_env("dsp"),
        preview=_purchase_preview(service),
        preview_environment=_env("dsp"),
    )
    assert any(issue.code == "cheapest_listing_changed" for issue in prepared.issues)
    assert prepared.executable is False


def test_reread_source_contains_no_mutation_or_commit_sql():
    source = Path("src/workbench/server_admin/auction_house/database_reread.py").read_text(encoding="utf-8").upper()
    assert "START TRANSACTION READ ONLY" in source
    assert "INSERT INTO" not in source
    assert "UPDATE AUCTION_HOUSE" not in source
    assert "DELETE FROM" not in source
    assert ".COMMIT(" not in source
    assert "ROLLBACK" in source


if __name__ == "__main__":
    test_listing_reread_collects_database_evidence_and_rolls_back()
    test_purchase_reread_collects_buyer_seller_and_cheapest_listing()
    test_database_reread_feeds_existing_stale_state_gate()
    test_cheapest_listing_change_blocks_normal_purchase()
    test_reread_source_contains_no_mutation_or_commit_sql()
    print("Auction House database reread regression: PASS")
