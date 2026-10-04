from pathlib import Path
from types import SimpleNamespace

from workbench.server_admin.auction_house import lsb_validation, validation_report
from workbench.server_admin.auction_house.lsb_policy import load_lsb_policy, listing_fee


class Cursor:
    def __init__(self, connection):
        self.connection = connection
    def execute(self, sql, params=None):
        self.connection.executed.append((sql, params))
    def close(self):
        pass

class Connection:
    def __init__(self):
        self.executed = []
        self.rollback_count = 0
    def cursor(self):
        return Cursor(self)
    def rollback(self):
        self.rollback_count += 1

class Service:
    def __init__(self):
        self.connection = Connection()
        self.schema = SimpleNamespace(
            family_hint="lsb-compatible",
            auction_columns={"id":"id","item_id":"itemid","seller_id":"seller","stack":"stack","sold_at":"sale","asking_price":"price"},
        )
        self.item = {"item_id":100,"category_id":3,"stack_size":12,"name":"Test Item"}
        self.seller = {"char_id":20,"name":"Seller"}
        self.listing = {"auction_id":55,"item_id":100,"seller_id":20,"asking_price":5000,"sold_at":0,"stack":False}
        self.buyer = {"char_id":30,"name":"Buyer"}
    def item_snapshot(self, item_id):
        return dict(self.item) if item_id == 100 else None
    def character_snapshot(self, char_id):
        return dict(self.seller) if char_id == 20 else (dict(self.buyer) if char_id == 30 else None)
    def active_listing_by_id(self, auction_id):
        return dict(self.listing) if auction_id == 55 else None

def _env():
    return {"profile_id":7,"name":"LSB Test","environment":"TEST","family":"lsb","is_active":True}

def _root(tmp_path):
    path = tmp_path / "settings" / "default"
    path.mkdir(parents=True)
    (path / "map.lua").write_text(
        """xi.settings.map = {\nAH_BASE_FEE_SINGLE = 1,\nAH_BASE_FEE_STACKS = 4,\nAH_TAX_RATE_SINGLE = 1.0,\nAH_TAX_RATE_STACKS = 0.5,\nAH_MAX_FEE = 10000,\nAH_LIST_LIMIT = 7,\n}\n""",
        encoding="utf-8",
    )
    return tmp_path

def _list_preview(service, stack=False):
    return {
        "action":"list_item","adapter":"lsb-compatible",
        "payload":{"item_id":100,"seller_id":20,"price":5000,"stack":stack},
        "snapshot":{"item":dict(service.item),"seller":dict(service.seller)},
        "environment":_env(),"apply_supported":False,
    }

def _purchase_preview(service):
    return {
        "action":"purchase_item","adapter":"lsb-compatible",
        "payload":{"auction_id":55,"buyer_id":30,"mode":"normal_purchase"},
        "snapshot":{"listing":dict(service.listing),"buyer":dict(service.buyer)},
        "environment":_env(),"apply_supported":False,
    }

def _stub_evidence(monkeypatch, *, seller_gil=99999, seller_qty=12, listings=0, buyer_gil=99999, capacity=80, occupied=10, cheapest=55, delivery=0):
    monkeypatch.setattr(lsb_validation, "_character_gil", lambda connection, char_id: seller_gil if char_id == 20 else buyer_gil)
    monkeypatch.setattr(lsb_validation, "_seller_item_quantity", lambda connection, seller_id, item_id: seller_qty)
    monkeypatch.setattr(lsb_validation, "_seller_active_listings", lambda service, seller_id: listings)
    monkeypatch.setattr(lsb_validation, "_buyer_inventory_state", lambda connection, buyer_id: (capacity, occupied))
    monkeypatch.setattr(lsb_validation, "_cheapest_qualifying", lambda service, listing: cheapest)
    monkeypatch.setattr(lsb_validation, "_delivery_count", lambda connection, seller_id: delivery)

def test_lsb_policy_matches_source_fee_model(tmp_path):
    policy = load_lsb_policy(_root(tmp_path))
    assert policy.policy_ready is True
    assert listing_fee(policy, price=5000, stack=False) == 51
    assert listing_fee(policy, price=5000, stack=True) == 29
    assert policy.policy_fingerprint

def test_lsb_listing_invariants_use_inventory_fee_and_limit(tmp_path, monkeypatch):
    service = Service()
    _stub_evidence(monkeypatch)
    prepared, evidence, invariants, policy, binding = lsb_validation.prepare_lsb_preview_validation(
        service=service, operation="list_item", environment=_env(), preview=_list_preview(service), server_root=_root(tmp_path)
    )
    assert prepared.validation_ready is True
    assert evidence.transaction_mode == "read_only_rolled_back"
    assert invariants.invariants_ready is True
    assert invariants.details["listing_fee"] == 51
    assert policy.policy_ready is True and binding.binding_ready is True
    assert service.connection.executed[0][0] == "START TRANSACTION READ ONLY"
    assert service.connection.rollback_count == 1

def test_lsb_full_stack_quantity_and_fee_funds_fail_closed(tmp_path, monkeypatch):
    service = Service()
    _stub_evidence(monkeypatch, seller_gil=10, seller_qty=11, listings=7)
    _, _, invariants, _, _ = lsb_validation.prepare_lsb_preview_validation(
        service=service, operation="list_item", environment=_env(), preview=_list_preview(service, stack=True), server_root=_root(tmp_path)
    )
    codes = {issue.code for issue in invariants.issues}
    assert {"seller_inventory_insufficient", "seller_gil_insufficient", "listing_limit_reached"} <= codes

def test_lsb_purchase_checks_buyer_funds_capacity_and_cheapest_listing(tmp_path, monkeypatch):
    service = Service()
    _stub_evidence(monkeypatch, buyer_gil=100, capacity=80, occupied=80, cheapest=54)
    _, evidence, invariants, _, _ = lsb_validation.prepare_lsb_preview_validation(
        service=service, operation="purchase_item", environment=_env(), preview=_purchase_preview(service), server_root=_root(tmp_path)
    )
    codes = {issue.code for issue in invariants.issues}
    assert {"buyer_gil_insufficient", "buyer_inventory_full", "cheapest_listing_changed"} <= codes
    assert evidence.delivery_row_count == 0

def test_lsb_stale_preview_is_rejected(tmp_path, monkeypatch):
    service = Service()
    _stub_evidence(monkeypatch)
    preview = _list_preview(service)
    service.item["stack_size"] = 99
    prepared, _, _, _, _ = lsb_validation.prepare_lsb_preview_validation(
        service=service, operation="list_item", environment=_env(), preview=preview, server_root=_root(tmp_path)
    )
    assert prepared.validation_ready is False
    assert "stale_preview" in {issue.code for issue in prepared.issues}

def test_lsb_missing_policy_blocks_validation(tmp_path, monkeypatch):
    service = Service()
    _stub_evidence(monkeypatch)
    _, _, invariants, policy, _ = lsb_validation.prepare_lsb_preview_validation(
        service=service, operation="list_item", environment=_env(), preview=_list_preview(service), server_root=tmp_path
    )
    assert policy.policy_ready is False
    assert "lsb_listing_fee_unavailable" in {issue.code for issue in invariants.issues}

def test_lsb_unified_report_uses_lsb_trigger_readiness(tmp_path, monkeypatch):
    service = Service()
    _stub_evidence(monkeypatch)
    class Probe:
        def as_dict(self):
            return {"database":"xidb","tables":(),"triggers":(),"lsb_listing_ready":True,"lsb_purchase_ready":True,"legacy_listing_shape_present":False,"legacy_purchase_prerequisites_present":True,"notes":()}
    monkeypatch.setattr(validation_report, "probe_write_readiness", lambda connection: Probe())
    report = validation_report.run_lsb_preview_validation(service=service, environment=_env(), preview=_list_preview(service), server_root=_root(tmp_path))
    assert report["status"] == "ready"
    assert report["read_only_validation_ready"] is True
    assert report["validation_model"] == "lsb-source-settings-and-trigger"
    assert report["execution_ready"] is False
    assert report["stages"]["policy"]["ready"] is True
    assert report["stages"]["invariants"]["ready"] is True

def test_lsb_validation_source_has_no_mutation_or_commit_primitive():
    source = Path("src/workbench/server_admin/auction_house/lsb_validation.py").read_text(encoding="utf-8").upper()
    assert "START TRANSACTION READ ONLY" in source
    assert "UPDATE AUCTION_HOUSE" not in source
    assert "INSERT INTO AUCTION_HOUSE" not in source
    assert "DELETE FROM AUCTION_HOUSE" not in source
    assert ".COMMIT(" not in source

if __name__ == "__main__":
    print("Auction House LSB strong invariant regression: PASS")
