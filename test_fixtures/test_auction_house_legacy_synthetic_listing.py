from __future__ import annotations

import pytest

from workbench.server_admin.auction_house.legacy_test_executor import (
    LegacyTestExecutionBlocked,
    execute_legacy_test_synthetic_listing,
)


class _Schema:
    family_hint = "legacy-dsp-topaz-compatible"
    auction_columns = {
        "id": "id",
        "item_id": "itemid",
        "stack": "stack",
        "seller_id": "seller",
        "seller_name": "seller_name",
        "listed_at": "date",
        "asking_price": "price",
        "sale_price": "sale",
        "sold_at": "sell_date",
    }


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 0
        self.lastrowid = 0
        self._row = None

    def execute(self, sql, params=None):
        params = tuple(params or ())
        if sql == "START TRANSACTION":
            self.connection.in_transaction = True
            return
        if sql.startswith("INSERT INTO `auction_house`"):
            self.lastrowid = self.connection.next_id
            self.connection.next_id += 1
            item_id, stack, seller_id, seller_name, listed_at, price = params
            self.connection.rows[self.lastrowid] = {
                "itemid": int(item_id),
                "stack": int(stack),
                "seller": int(seller_id),
                "seller_name": str(seller_name),
                "date": int(listed_at),
                "price": int(price),
                "sale": 0,
                "sell_date": 0,
            }
            self.rowcount = 1
            return
        if sql.startswith("SELECT `itemid`,`stack`,`seller`,`price`,`sale`,`sell_date`"):
            auction_id = int(params[0])
            row = self.connection.rows.get(auction_id)
            self._row = None if row is None else (
                row["itemid"], row["stack"], row["seller"], row["price"], row["sale"], row["sell_date"]
            )
            return
        raise AssertionError(sql)

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _Connection:
    def __init__(self):
        self.rows = {}
        self.next_id = 100
        self._before = None
        self.in_transaction = False
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        if not self.in_transaction:
            self._before = {key: dict(value) for key, value in self.rows.items()}
        return _Cursor(self)

    def commit(self):
        self.commits += 1
        self.in_transaction = False
        self._before = None

    def rollback(self):
        self.rollbacks += 1
        if self._before is not None:
            self.rows = {key: dict(value) for key, value in self._before.items()}
        self.in_transaction = False


class _Service:
    def __init__(self, *, item=None, seller=None):
        self.schema = _Schema()
        self.connection = _Connection()
        self.item = item if item is not None else {
            "item_id": 4096,
            "name": "Test Item",
            "stack_size": 12,
            "category_id": 9,
        }
        self.seller = seller if seller is not None else {"char_id": 77, "char_name": "AuctionBot"}

    def item_snapshot(self, item_id):
        return dict(self.item) if self.item and int(item_id) == int(self.item["item_id"]) else None

    def character_snapshot(self, char_id):
        return dict(self.seller) if self.seller and int(char_id) == int(self.seller["char_id"]) else None


def _env(family):
    return {
        "profile_id": 4,
        "name": f"{family.upper()} Test",
        "environment": "test",
        "family": family,
        "enabled": True,
        "is_active": True,
    }


@pytest.mark.parametrize("family", ["dsp", "topaz"])
def test_synthetic_listing_commits_for_legacy_test_environments(family):
    service = _Service()
    env = _env(family)
    result = execute_legacy_test_synthetic_listing(
        service=service,
        environment=env,
        item_id=4096,
        seller_id=77,
        price=12000,
        stack=True,
        confirmation=env["name"],
        feature_enabled=True,
        listed_at=123456,
    )
    assert result["status"] == "committed"
    assert result["operation"] == "synthetic_listing"
    assert result["quantity"] == 12
    assert result["economic_effect"]["listing_fee_charged"] == 0
    assert result["economic_effect"]["seller_inventory_removed"] == 0
    assert service.connection.commits == 1
    assert service.connection.rollbacks == 0
    row = service.connection.rows[result["auction_id"]]
    assert row["itemid"] == 4096
    assert row["seller"] == 77
    assert row["price"] == 12000
    assert row["sale"] == 0


def test_synthetic_listing_rejects_unauctionable_or_missing_entities_without_write():
    env = _env("topaz")
    unauctionable = _Service(item={"item_id":4096,"name":"No AH","stack_size":1,"category_id":0})
    with pytest.raises(LegacyTestExecutionBlocked, match="not assigned"):
        execute_legacy_test_synthetic_listing(
            service=unauctionable,
            environment=env,
            item_id=4096,
            seller_id=77,
            price=100,
            stack=False,
            confirmation=env["name"],
            feature_enabled=True,
        )
    assert unauctionable.connection.commits == 0

    missing_seller = _Service(seller={"char_id":88,"char_name":"Other"})
    with pytest.raises(LegacyTestExecutionBlocked, match="seller character does not exist"):
        execute_legacy_test_synthetic_listing(
            service=missing_seller,
            environment=env,
            item_id=4096,
            seller_id=77,
            price=100,
            stack=False,
            confirmation=env["name"],
            feature_enabled=True,
        )
    assert missing_seller.connection.commits == 0


def test_synthetic_listing_live_is_hard_blocked():
    service = _Service()
    env = _env("dsp")
    env["environment"] = "live"
    with pytest.raises(LegacyTestExecutionBlocked, match="environment_not_test"):
        execute_legacy_test_synthetic_listing(
            service=service,
            environment=env,
            item_id=4096,
            seller_id=77,
            price=100,
            stack=False,
            confirmation=env["name"],
            feature_enabled=True,
        )
    assert service.connection.commits == 0
    assert service.connection.rows == {}
