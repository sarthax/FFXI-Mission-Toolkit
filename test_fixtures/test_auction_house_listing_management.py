from __future__ import annotations

from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house import listing_management as lm
from workbench.server_admin.auction_house.listing_management import ListingFilter


class _Schema:
    family_hint = "legacy-dsp-topaz-compatible"
    auction_columns = {
        "id": "id", "item_id": "itemid", "stack": "stack", "seller_id": "seller",
        "seller_name": "seller_name", "listed_at": "date", "asking_price": "price",
        "sale_price": "sale", "sold_at": "sell_date",
    }
    item_columns = {"item_id": "itemid", "name": "name", "stack_size": "stackSize", "ah_category": "aH"}


class _Cursor:
    def __init__(self, con):
        self.con = con
        self.rowcount = 0
        self._row = None
        self._rows = []

    def execute(self, sql, params=()):
        params = tuple(params or ())
        self.rowcount = 0
        if sql == "START TRANSACTION":
            self.con.in_tx = True
            return
        if "FROM `auction_house` ah JOIN `item_basic` ib" in sql:
            self._rows = [(55, 100, "Potion", 12, 42, 1, 7, "Seller", 123456, 9000)]
            return
        if sql.startswith("SELECT `id`,`itemid`,`stack`,`seller`,`price`,`sale`,`sell_date`"):
            row = self.con.auctions.get(int(params[0]))
            self._row = None if row is None else (row["id"], row["itemid"], row["stack"], row["seller"], row["price"], row["sale"], row["sell_date"])
            return
        if sql.startswith("DELETE FROM `auction_house`"):
            auction_id = int(params[0])
            row = self.con.auctions.get(auction_id)
            if row and row["sale"] == 0 and row["sell_date"] == 0:
                del self.con.auctions[auction_id]
                self.rowcount = 1
            return
        if sql.startswith("INSERT INTO `char_inventory`"):
            charid, location, slot, itemid, quantity, bazaar, signature, extra = params
            self.con.inventory[(int(charid), int(location), int(slot))] = {
                "itemId": int(itemid), "quantity": int(quantity)
            }
            self.rowcount = 1
            return
        if sql.startswith("SELECT `itemId`,`quantity` FROM `char_inventory`"):
            charid, slot = map(int, params)
            row = self.con.inventory.get((charid, 0, slot))
            self._row = None if row is None else (row["itemId"], row["quantity"])
            return
        if sql.startswith("SELECT 1 FROM `auction_house`"):
            self._row = (1,) if int(params[0]) in self.con.auctions else None
            return
        raise AssertionError(sql)

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows

    def close(self):
        pass


class _Connection:
    def __init__(self):
        self.auctions = {55: {"id": 55, "itemid": 100, "stack": 1, "seller": 7, "price": 9000, "sale": 0, "sell_date": 0}}
        self.inventory = {}
        self.in_tx = False
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1
        self.in_tx = False

    def rollback(self):
        self.rollbacks += 1
        self.in_tx = False


class _Service:
    def __init__(self):
        self.schema = _Schema()
        self.connection = _Connection()

    def item_snapshot(self, item_id):
        return {"item_id": 100, "name": "Potion", "stack_size": 12, "category_id": 42} if int(item_id) == 100 else None

    def character_snapshot(self, char_id):
        return {"char_id": 7, "char_name": "Seller"} if int(char_id) == 7 else None


def _env():
    return {"name": "TOPAZ Test", "family": "topaz", "environment": "test", "enabled": True, "is_active": True}


def test_browse_active_listings_exposes_granular_actions():
    rows = lm.browse_active_listings(_Service(), ListingFilter(seller_id=7, category_id=42, q="Potion"))
    assert len(rows) == 1
    row = rows[0]
    assert row["auction_id"] == 55
    assert row["seller_id"] == 7
    assert row["category_id"] == 42
    assert row["quantity"] == 12
    assert row["available_actions"] == ["preview_buy", "return_to_seller"]


def test_return_to_seller_deletes_listing_and_restores_full_stack(monkeypatch):
    service = _Service()
    monkeypatch.setattr(lm, "discover_character_schema", lambda connection: object())
    monkeypatch.setattr(lm, "inspect_inventory_contract", lambda schema, family: SimpleNamespace(basic_insert_verified=True))
    monkeypatch.setattr(lm, "detect_online_state", lambda connection, schema, char_id: SimpleNamespace(online=False))
    monkeypatch.setattr(lm, "inspect_slots", lambda connection, char_id, location: SimpleNamespace(first_free_slot=3))
    monkeypatch.setattr(lm, "build_basic_insert_plan", lambda contract, **kw: {
        "sql": "INSERT INTO `char_inventory` (`charid`,`location`,`slot`,`itemId`,`quantity`,`bazaar`,`signature`,`extra`) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        "params": (kw["char_id"], kw["location"], kw["slot"], kw["item_id"], kw["quantity"], 0, "", None),
    })

    result = lm.execute_legacy_test_return_to_seller(
        service=service,
        environment=_env(),
        auction_id=55,
        confirmation="TOPAZ Test",
        feature_enabled=True,
    )
    assert result["status"] == "committed"
    assert result["quantity"] == 12
    assert result["return_slot"] == 3
    assert 55 not in service.connection.auctions
    assert service.connection.inventory[(7, 0, 3)] == {"itemId": 100, "quantity": 12}
    assert service.connection.commits == 1
    assert service.connection.rollbacks == 0


def test_return_to_seller_refuses_online_or_full_inventory(monkeypatch):
    for online, free_slot, message in ((True, 3, "must be offline"), (False, None, "Inventory is full")):
        service = _Service()
        monkeypatch.setattr(lm, "discover_character_schema", lambda connection: object())
        monkeypatch.setattr(lm, "inspect_inventory_contract", lambda schema, family: SimpleNamespace(basic_insert_verified=True))
        monkeypatch.setattr(lm, "detect_online_state", lambda connection, schema, char_id, value=online: SimpleNamespace(online=value))
        monkeypatch.setattr(lm, "inspect_slots", lambda connection, char_id, location, slot=free_slot: SimpleNamespace(first_free_slot=slot))
        with pytest.raises(lm.LegacyTestExecutionBlocked, match=message):
            lm.execute_legacy_test_return_to_seller(
                service=service,
                environment=_env(),
                auction_id=55,
                confirmation="TOPAZ Test",
                feature_enabled=True,
            )
        assert 55 in service.connection.auctions
        assert service.connection.commits == 0
        assert service.connection.rollbacks == 1
