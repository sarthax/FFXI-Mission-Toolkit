from pathlib import Path
from types import SimpleNamespace

from workbench.server_admin.auction_house.lsb_validation import prepare_lsb_preview_validation
from workbench.server_admin.auction_house import validation_report


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
        self.schema = SimpleNamespace(family_hint="lsb-compatible")
        self.item = {"item_id": 100, "category_id": 3, "stack_size": 12, "name": "Test Item"}
        self.seller = {"char_id": 20, "name": "Seller"}
        self.listing = {"auction_id": 55, "item_id": 100, "seller_id": 20, "asking_price": 5000, "sold_at": 0, "stack": False}
        self.buyer = {"char_id": 30, "name": "Buyer"}

    def item_snapshot(self, item_id):
        return dict(self.item) if item_id == 100 else None

    def character_snapshot(self, char_id):
        if char_id == 20:
            return dict(self.seller)
        if char_id == 30:
            return dict(self.buyer)
        return None

    def active_listing_by_id(self, auction_id):
        return dict(self.listing) if auction_id == 55 else None


def _env():
    return {
        "profile_id": 7,
        "name": "LSB Test",
        "environment": "TEST",
        "family": "lsb",
        "is_active": True,
    }


def _list_preview(service):
    return {
        "action": "list_item",
        "adapter": "lsb-compatible",
        "payload": {"item_id": 100, "seller_id": 20, "price": 5000, "stack": False},
        "snapshot": {"item": dict(service.item), "seller": dict(service.seller)},
        "environment": _env(),
        "apply_supported": False,
    }


def test_lsb_reread_is_read_only_and_legacy_policy_is_not_applicable():
    service = Service()
    prepared, evidence, invariants, policy, binding = prepare_lsb_preview_validation(
        service=service,
        operation="list_item",
        environment=_env(),
        preview=_list_preview(service),
    )

    assert prepared.validation_ready is True
    assert evidence.transaction_mode == "read_only_rolled_back"
    assert invariants.invariants_ready is True
    assert policy.policy_ready is True
    assert binding.binding_ready is True
    assert service.connection.executed[0][0] == "START TRANSACTION READ ONLY"
    assert service.connection.rollback_count == 1
    assert policy.issues[0]["code"] == "lsb_legacy_policy_not_applicable"


def test_lsb_stale_preview_is_rejected():
    service = Service()
    preview = _list_preview(service)
    service.item["stack_size"] = 99

    prepared, _, _, _, _ = prepare_lsb_preview_validation(
        service=service,
        operation="list_item",
        environment=_env(),
        preview=preview,
    )
    assert prepared.validation_ready is False
    assert "stale_preview" in {issue.code for issue in prepared.issues}


def test_lsb_unified_report_uses_lsb_trigger_readiness(monkeypatch):
    service = Service()

    class Probe:
        def as_dict(self):
            return {
                "database": "xidb",
                "tables": ("auction_house", "item_basic", "chars", "delivery_box"),
                "triggers": ("auction_house_list", "auction_house_buy", "delivery_box_insert"),
                "lsb_listing_ready": True,
                "lsb_purchase_ready": True,
                "legacy_listing_shape_present": False,
                "legacy_purchase_prerequisites_present": True,
                "notes": (),
            }

    monkeypatch.setattr(validation_report, "probe_write_readiness", lambda connection: Probe())
    report = validation_report.run_lsb_preview_validation(
        service=service,
        environment=_env(),
        preview=_list_preview(service),
    )

    assert report["status"] == "ready"
    assert report["read_only_validation_ready"] is True
    assert report["validation_model"] == "lsb-source-and-trigger"
    assert report["execution_ready"] is False
    assert report["executor_enabled"] is False
    assert report["write_enabled"] is False
    assert report["stages"]["schema_readiness"]["ready"] is True
    assert report["stages"]["policy"]["ready"] is True
    assert report["stages"]["policy_binding"]["ready"] is True


def test_lsb_missing_listing_trigger_blocks_unified_report(monkeypatch):
    service = Service()

    class Probe:
        def as_dict(self):
            return {
                "database": "xidb",
                "tables": ("auction_house", "item_basic", "chars", "delivery_box"),
                "triggers": ("auction_house_buy", "delivery_box_insert"),
                "lsb_listing_ready": False,
                "lsb_purchase_ready": True,
                "legacy_listing_shape_present": True,
                "legacy_purchase_prerequisites_present": True,
                "notes": ("LSB listing missing trigger: auction_house_list",),
            }

    monkeypatch.setattr(validation_report, "probe_write_readiness", lambda connection: Probe())
    report = validation_report.run_lsb_preview_validation(
        service=service,
        environment=_env(),
        preview=_list_preview(service),
    )
    assert report["status"] == "blocked"
    assert report["stages"]["schema_readiness"]["ready"] is False
    assert "lsb_write_prerequisites_missing" in {item["code"] for item in report["blockers"]}


def test_lsb_validation_source_has_no_mutation_or_commit_primitive():
    source = Path("src/workbench/server_admin/auction_house/lsb_validation.py").read_text(encoding="utf-8").upper()
    assert "START TRANSACTION READ ONLY" in source
    assert "UPDATE AUCTION_HOUSE" not in source
    assert "INSERT INTO AUCTION_HOUSE" not in source
    assert "DELETE FROM AUCTION_HOUSE" not in source
    assert ".COMMIT(" not in source


if __name__ == "__main__":
    test_lsb_reread_is_read_only_and_legacy_policy_is_not_applicable()
    test_lsb_stale_preview_is_rejected()
    test_lsb_validation_source_has_no_mutation_or_commit_primitive()
    print("Auction House LSB validation regression: PASS")
