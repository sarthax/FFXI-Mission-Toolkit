from __future__ import annotations

from fastapi import APIRouter, FastAPI

from workbench import gui_shell
from workbench.server_admin.auction_house.actions import (
    ListItemRequest,
    PurchaseRequest,
    preview_list_item,
    preview_purchase,
)
from workbench.server_admin.auction_house.categories import category_metadata
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


def test_canonical_auction_house_category_hierarchy_and_custom_fallback():
    sword = category_metadata(3)
    assert sword.group == "Weapons"
    assert sword.label == "Sword"
    assert sword.path == "Weapons → Sword"

    meat = category_metadata(52)
    assert meat.group == "Food"
    assert meat.path == "Food → Meals → Meat & Eggs"

    custom = category_metadata(99)
    assert custom.group == "Custom / Unknown"
    assert custom.label == "Category 99"
    assert custom.id == 99


def test_service_exposes_no_mutation_contract():
    forbidden = {"create", "add", "insert", "update", "delete", "buy", "sell", "deliver", "purchase", "purge"}
    public = {name.lower() for name in dir(AuctionHouseService) if not name.startswith("_")}
    assert not forbidden.intersection(public)


def test_list_preview_is_explicitly_non_applying_and_stack_aware():
    preview = preview_list_item(
        ListItemRequest(item_id=4096, seller_id=12, price=12000, stack=True),
        adapter_family="lsb-compatible",
        item={"item_id": 4096, "name": "Fire Crystal", "stack_size": 12, "category_id": 35},
        seller={"char_id": 12, "char_name": "Admin"},
    )
    assert preview.apply_supported is False
    assert preview.economic_effect["quantity"] == 12
    assert preview.economic_effect["price_per_item"] == 1000
    assert any(w.code == "preview_only" and w.blocking for w in preview.warnings)


def test_list_preview_blocks_invalid_stack_and_unknown_seller():
    preview = preview_list_item(
        ListItemRequest(item_id=1, seller_id=999, price=100, stack=True),
        adapter_family="legacy-dsp-topaz-compatible",
        item={"item_id": 1, "name": "Test", "stack_size": 1, "category_id": 1},
        seller=None,
    )
    codes = {w.code for w in preview.warnings if w.blocking}
    assert {"seller_not_found", "not_stackable", "preview_only"} <= codes


def test_purchase_preview_exposes_admin_economy_injection():
    listing = {"auction_id": 77, "item_id": 4096, "asking_price": 9000, "seller_id": 55, "stack": False}
    preview = preview_purchase(
        PurchaseRequest(auction_id=77, mode="admin_cleanup"),
        adapter_family="lsb-compatible",
        listing=listing,
    )
    assert preview.apply_supported is False
    assert preview.economic_effect["seller_compensation"] == 9000
    assert preview.economic_effect["buyer_charge"] == 0
    assert preview.economic_effect["admin_economy_injection"] == 9000


def test_normal_purchase_requires_real_buyer_snapshot():
    preview = preview_purchase(
        PurchaseRequest(auction_id=77, buyer_id=100, mode="normal_purchase"),
        adapter_family="legacy-dsp-topaz-compatible",
        listing={"auction_id": 77, "asking_price": 5000},
        buyer=None,
    )
    assert any(w.code == "buyer_not_found" and w.blocking for w in preview.warnings)


def test_router_surface_has_only_read_and_preview_operations():
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()["paths"]
    expected = {
        "/auction-house",
        "/auction-house/status.json",
        "/auction-house/overview.json",
        "/auction-house/categories.json",
        "/auction-house/items.json",
        "/auction-house/items/{item_id}.json",
        "/auction-house/items/{item_id}/history.json",
        "/auction-house/items/{item_id}/trends.json",
        "/auction-house/items/{item_id}/icon.png",
        "/auction-house/admin/list/preview.json",
        "/auction-house/admin/purchase/preview.json",
    }
    assert expected <= set(paths)

    for path, methods in paths.items():
        assert set(methods) <= {"get", "post"}
        if "post" in methods:
            assert path.endswith("/preview.json")
    assert not any("apply" in path or "commit" in path or "delete" in path for path in paths)


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
