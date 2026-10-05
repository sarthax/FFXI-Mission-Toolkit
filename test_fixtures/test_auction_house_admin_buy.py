from __future__ import annotations

from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house import admin_buy as ab
from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked


class _Schema:
    family_hint = "legacy-dsp-topaz-compatible"
    auction_columns = {
        "id": "id", "item_id": "itemid", "stack": "stack", "seller_id": "seller",
        "seller_name": "seller_name", "asking_price": "price", "buyer_name": "buyer_name",
        "sale_price": "sale", "sold_at": "sell_date",
    }


class _Cursor:
    def __init__(self, con):
        self.con = con
        self.rowcount = 0
        self._row = None

    def execute(self, sql, params=()):
        params = tuple(params or ())
        self.rowcount = 0
        if sql == "START TRANSACTION":
            self.con.in_tx = True
            return
        if sql.startswith("SELECT `itemid`,`stack`,`seller`,`seller_name`,`price`,`sale`,`sell_date`"):
            row = self.con.auctions.get(int(params[0]))
            self._row = None if row is None else (
                row["itemid"], row["stack"], row["seller"], row["seller_name"],
                row["price"], row["sale"], row["sell_date"],
            )
            return
        if sql.startswith("SELECT COUNT(*) FROM `delivery_box`"):
            seller_id, item_id, quantity = map(int, params)
            self._row = (sum(1 for r in self.con.delivery if r == (seller_id, item_id, quantity)),)
            return
        if sql.startswith("UPDATE `auction_house`"):
            buyer_name, sale, sold_at, auction_id, expected_price = params
            row = self.con.auctions.get(int(auction_id))
            if row and row["price"] == int(expected_price) and row["sale"] == 0 and row["sell_date"] == 0:
                row["buyer_name"] = str(buyer_name)
                row["sale"] = int(sale)
                row["sell_date"] = int(sold_at)
                self.rowcount = 1
                if self.con.trigger_enabled:
                    self.con.delivery.append((row["seller"], row["itemid"], int(sale)))
            return
        if sql.startswith("SELECT `buyer_name`,`sale`,`sell_date`"):
            row = self.con.auctions.get(int(params[0]))
            self._row = None if row is None else (row.get("buyer_name"), row["sale"], row["sell_date"])
            return
        raise AssertionError(sql)

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []

    def close(self):
        pass


class _Connection:
    def __init__(self, *, trigger_enabled=True):
        self.auctions = {55: {
            "itemid": 100, "stack": 1, "seller": 7, "seller_name": "Seller",
            "price": 9000, "sale": 0, "sell_date": 0, "buyer_name": None,
        }}
        self.delivery = []
        self.trigger_enabled = trigger_enabled
        self.commits = 0
        self.rollbacks = 0
        self.in_tx = False

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.commits += 1
        self.in_tx = False

    def rollback(self):
        self.rollbacks += 1
        self.in_tx = False


class _Service:
    def __init__(self, *, trigger_enabled=True):
        self.schema = _Schema()
        self.connection = _Connection(trigger_enabled=trigger_enabled)

    def item_snapshot(self, item_id):
        return {"item_id": 100, "name": "Potion", "stack_size": 12, "category_id": 42} if int(item_id) == 100 else None


def _env(family="topaz"):
    return {"name": f"{family.upper()} Test", "family": family, "environment": "test", "enabled": True, "is_active": True}


def _patch_prereqs(monkeypatch):
    monkeypatch.setattr(ab, "probe_write_readiness", lambda connection: SimpleNamespace(legacy_purchase_prerequisites_present=True))
    monkeypatch.setattr(ab, "_delivery_columns", lambda connection: {"charid", "box", "itemid", "quantity", "sender"})


@pytest.mark.parametrize("family", ["topaz", "dsp"])
def test_admin_buy_closes_exact_listing_and_observes_settlement(monkeypatch, family):
    _patch_prereqs(monkeypatch)
    service = _Service()
    env = _env(family)
    result = ab.execute_legacy_test_admin_buy(
        service=service,
        environment=env,
        auction_id=55,
        expected_price=9000,
        confirmation=env["name"],
        feature_enabled=True,
        sold_at=123456,
    )
    assert result["status"] == "committed"
    assert result["seller_proceeds_queued"] == 9000
    assert result["quantity"] == 12
    assert service.connection.auctions[55]["sale"] == 9000
    assert service.connection.delivery == [(7, 100, 9000)]
    assert service.connection.commits == 1
    assert service.connection.rollbacks == 0


def test_admin_buy_rejects_stale_price(monkeypatch):
    _patch_prereqs(monkeypatch)
    service = _Service()
    env = _env()
    with pytest.raises(LegacyTestExecutionBlocked, match="price changed"):
        ab.execute_legacy_test_admin_buy(
            service=service, environment=env, auction_id=55, expected_price=8000,
            confirmation=env["name"], feature_enabled=True, sold_at=123456,
        )
    assert service.connection.auctions[55]["sale"] == 0
    assert service.connection.commits == 0
    assert service.connection.rollbacks == 1


def test_admin_buy_rolls_back_if_settlement_trigger_is_not_observed(monkeypatch):
    _patch_prereqs(monkeypatch)
    service = _Service(trigger_enabled=False)
    env = _env("dsp")
    with pytest.raises(LegacyTestExecutionBlocked, match="settlement was not queued"):
        ab.execute_legacy_test_admin_buy(
            service=service, environment=env, auction_id=55, expected_price=9000,
            confirmation=env["name"], feature_enabled=True, sold_at=123456,
        )
    assert service.connection.commits == 0
    assert service.connection.rollbacks == 1
