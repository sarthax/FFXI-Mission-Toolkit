from __future__ import annotations

from fastapi import FastAPI

from workbench.server_admin.auction_house.gui import router
from workbench.server_admin.auction_house.write_probe import probe_write_readiness


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, sql, params=None):
        if sql == "SELECT DATABASE()":
            self.rows = [(self.connection.database,)]
        elif sql == "SHOW TABLES":
            self.rows = [(name,) for name in self.connection.tables]
        elif "information_schema`.`TRIGGERS" in sql:
            assert params == (self.connection.database,)
            self.rows = [(name,) for name in self.connection.triggers]
        else:
            raise AssertionError(f"unexpected SQL: {sql}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class _Connection:
    def __init__(self, *, tables, triggers, database="xidb"):
        self.tables = tuple(tables)
        self.triggers = tuple(triggers)
        self.database = database

    def cursor(self):
        return _Cursor(self)


def test_lsb_probe_reports_listing_and_purchase_prerequisites_present():
    probe = probe_write_readiness(_Connection(
        tables={"auction_house", "item_basic", "chars", "delivery_box"},
        triggers={"auction_house_list", "auction_house_buy", "delivery_box_insert"},
    ))
    assert probe.database == "xidb"
    assert probe.lsb_listing_ready is True
    assert probe.lsb_purchase_ready is True
    assert any("execution remains disabled" in note for note in probe.notes)


def test_probe_reports_each_missing_prerequisite_without_guessing():
    probe = probe_write_readiness(_Connection(
        tables={"auction_house", "chars"},
        triggers={"auction_house_buy"},
    ))
    assert probe.lsb_listing_ready is False
    assert probe.lsb_purchase_ready is False
    joined = " | ".join(probe.notes)
    assert "listing missing table: item_basic" in joined
    assert "listing missing trigger: auction_house_list" in joined
    assert "purchase missing table: delivery_box" in joined
    assert "purchase missing trigger: delivery_box_insert" in joined


def test_write_readiness_route_is_get_only_and_no_apply_route_exists():
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()["paths"]
    assert "/auction-house/write-readiness.json" in paths
    assert set(paths["/auction-house/write-readiness.json"]) == {"get"}
    assert not any("/apply" in path or "/commit" in path for path in paths)
