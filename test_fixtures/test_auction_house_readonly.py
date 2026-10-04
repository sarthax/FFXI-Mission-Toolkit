from __future__ import annotations

from fastapi import APIRouter, FastAPI

from workbench import gui_shell
from workbench.server_admin.auction_house.gui import router
from workbench.server_admin.auction_house.integration import install_legacy_gui_bridge
from workbench.server_admin.auction_house.schema import discover_auction_house_schema
from workbench.server_admin.auction_house.service import AuctionHouseService


class _Cursor:
    def __init__(self, tables):
        self.tables = tables
        self.rows = []

    def execute(self, sql, params=None):
        if sql.startswith("DESCRIBE `auction_house`"):
            self.rows = [(name,) for name in self.tables["auction_house"]]
        elif sql.startswith("DESCRIBE `item_basic`"):
            self.rows = [(name,) for name in self.tables["item_basic"]]
        else:
            raise AssertionError(f"unexpected SQL in schema test: {sql}")

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class _Connection:
    def __init__(self, tables):
        self.tables = tables

    def cursor(self):
        return _Cursor(self.tables)


def _tables(*, buyer: bool):
    ah = ["id", "itemid", "stack", "seller", "seller_name", "date", "price", "buyer_name", "sale", "sell_date"]
    if buyer:
        ah.append("buyer")
    return {
        "auction_house": ah,
        "item_basic": ["itemid", "name", "stackSize", "aH", "flags"],
    }


def test_lsb_compatible_schema_detects_numeric_buyer():
    schema = discover_auction_house_schema(_Connection(_tables(buyer=True)))
    assert schema.family_hint == "lsb-compatible"
    assert schema.auction("buyer_id") == "buyer"
    assert schema.item("ah_category") == "aH"
    assert "buyer_ids" in schema.capabilities
    assert schema.public_dict()["read_only"] is True


def test_legacy_dsp_topaz_schema_does_not_require_numeric_buyer():
    schema = discover_auction_house_schema(_Connection(_tables(buyer=False)))
    assert schema.family_hint == "legacy-dsp-topaz-compatible"
    assert schema.auction("buyer_id") is None
    assert "buyer_ids" not in schema.capabilities
    assert "sale_history" in schema.capabilities


def test_service_exposes_no_mutation_contract():
    forbidden = {"create", "add", "insert", "update", "delete", "buy", "sell", "deliver", "purchase", "purge"}
    public = {name.lower() for name in dir(AuctionHouseService) if not name.startswith("_")}
    assert not forbidden.intersection(public)


def test_readonly_router_surface_is_registered():
    app = FastAPI()
    app.include_router(router)
    paths = set(app.openapi()["paths"])
    assert "/auction-house" in paths
    assert "/auction-house/status.json" in paths
    assert "/auction-house/overview.json" in paths
    assert "/auction-house/categories.json" in paths
    assert "/auction-house/items.json" in paths
    assert "/auction-house/items/{item_id}.json" in paths
    assert "/auction-house/items/{item_id}/history.json" in paths
    assert "/auction-house/items/{item_id}/trends.json" in paths
    assert "/auction-house/items/{item_id}/icon.png" in paths

    methods = {method for path in app.openapi()["paths"].values() for method in path}
    assert methods <= {"get"}


def test_legacy_bridge_keeps_auction_house_at_root_and_in_server_workspace():
    carrier = APIRouter(prefix="/character-editor")
    install_legacy_gui_bridge(carrier)
    install_legacy_gui_bridge(carrier)  # idempotent across repeated package imports

    paths = [getattr(route, "path", "") for route in carrier.routes]
    assert "/auction-house" in paths
    assert "/character-editor/auction-house" not in paths
    assert paths.count("/auction-house") == 1

    server = next(workspace for workspace in gui_shell.WORKSPACES if workspace["name"] == "Server")
    ah_entries = [section for section in server["sections"] if section.get("href") == "/auction-house"]
    assert ah_entries == [{"label": "Auction House", "href": "/auction-house"}]

    owner = gui_shell.route_owner("/auction-house/items/123.json")
    assert owner["home"] == "Server"
    assert owner["section"] == "Auction House"
