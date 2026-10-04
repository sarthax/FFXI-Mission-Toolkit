from types import SimpleNamespace

from workbench.server_admin.auction_house.invariants import (
    LegacyAuctionPolicy,
    legacy_listing_fee,
    validate_legacy_invariants,
)


def _evidence(**overrides):
    values = {
        "snapshot": {},
        "seller_gil": None,
        "buyer_gil": None,
        "seller_active_listing_count": None,
        "inventory_rows": (),
        "delivery_rows": (),
        "transaction_mode": "read_only_rolled_back",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _list_preview(*, price=12000, stack=False):
    return {
        "payload": {"item_id": 4096, "seller_id": 100, "price": price, "stack": stack},
        "snapshot": {},
    }


def _purchase_preview(*, mode="normal_purchase"):
    return {
        "payload": {"auction_id": 55, "buyer_id": 200 if mode == "normal_purchase" else None, "mode": mode},
        "snapshot": {},
    }


def test_legacy_listing_fee_matches_source_formula_and_clamp():
    policy = LegacyAuctionPolicy()
    assert legacy_listing_fee(12000, stack=False, policy=policy) == 121
    assert legacy_listing_fee(12000, stack=True, policy=policy) == 64
    assert legacy_listing_fee(5_000_000, stack=False, policy=policy) == 10000


def test_single_listing_passes_read_only_invariants():
    evidence = _evidence(
        snapshot={"item": {"item_id": 4096, "category_id": 9, "stack_size": 12}, "seller": {"char_id": 100}},
        seller_gil=5000,
        seller_active_listing_count=2,
        inventory_rows=({"quantity": 3, "location": 0, "slot": 1},),
    )
    report = validate_legacy_invariants(
        operation="list_item",
        preview=_list_preview(),
        evidence=evidence,
        policy=LegacyAuctionPolicy(),
    )
    assert report.invariants_ready is True
    assert report.listing_fee == 121
    assert report.required_quantity == 1
    assert report.executor_enabled is False
    assert report.executable is False


def test_stack_listing_requires_one_full_stack_row():
    evidence = _evidence(
        snapshot={"item": {"item_id": 4096, "category_id": 9, "stack_size": 12}, "seller": {"char_id": 100}},
        seller_gil=5000,
        seller_active_listing_count=1,
        inventory_rows=({"quantity": 11, "location": 0, "slot": 1}, {"quantity": 1, "location": 0, "slot": 2}),
    )
    report = validate_legacy_invariants(
        operation="list_item",
        preview=_list_preview(stack=True),
        evidence=evidence,
        policy=LegacyAuctionPolicy(),
    )
    assert any(issue.code == "full_stack_unavailable" for issue in report.issues)
    assert report.invariants_ready is False


def test_listing_rejects_insufficient_fee_and_listing_limit():
    evidence = _evidence(
        snapshot={"item": {"item_id": 4096, "category_id": 9, "stack_size": 12}, "seller": {"char_id": 100}},
        seller_gil=10,
        seller_active_listing_count=7,
        inventory_rows=({"quantity": 1},),
    )
    report = validate_legacy_invariants(
        operation="list_item",
        preview=_list_preview(),
        evidence=evidence,
        policy=LegacyAuctionPolicy(list_limit=7),
    )
    codes = {issue.code for issue in report.issues}
    assert "seller_gil_insufficient" in codes
    assert "listing_limit_reached" in codes
    assert report.invariants_ready is False


def test_normal_purchase_requires_buyer_funds_and_reports_settlement_queue():
    evidence = _evidence(
        snapshot={"listing": {"auction_id": 55, "asking_price": 12000, "seller_id": 100}, "buyer": {"char_id": 200}},
        buyer_gil=11999,
        delivery_rows=(
            {"box": 1, "slot": 0, "itemid": 1},
            {"box": 1, "slot": 8, "itemid": 2},
            {"box": 1, "slot": 9, "itemid": 3},
        ),
    )
    report = validate_legacy_invariants(
        operation="purchase_item",
        preview=_purchase_preview(),
        evidence=evidence,
        policy=LegacyAuctionPolicy(),
    )
    assert any(issue.code == "buyer_gil_insufficient" for issue in report.issues)
    assert report.next_delivery_slot == 10
    assert report.settlement_ready is True
    assert report.invariants_ready is False


def test_admin_cleanup_does_not_require_buyer_funds():
    evidence = _evidence(
        snapshot={"listing": {"auction_id": 55, "asking_price": 12000, "seller_id": 100}, "buyer": None},
        buyer_gil=None,
        delivery_rows=(),
    )
    report = validate_legacy_invariants(
        operation="admin_cleanup",
        preview=_purchase_preview(mode="admin_cleanup"),
        evidence=evidence,
        policy=LegacyAuctionPolicy(),
    )
    assert not any(issue.code.startswith("buyer_gil") for issue in report.issues)
    assert report.next_delivery_slot == 8
    assert report.settlement_ready is True
    assert report.invariants_ready is True


def test_delivery_queue_safety_ceiling_can_fail_closed():
    evidence = _evidence(
        snapshot={"listing": {"auction_id": 55, "asking_price": 12000, "seller_id": 100}, "buyer": None},
        delivery_rows=({"box": 1, "slot": 31},),
    )
    report = validate_legacy_invariants(
        operation="admin_cleanup",
        preview=_purchase_preview(mode="admin_cleanup"),
        evidence=evidence,
        policy=LegacyAuctionPolicy(max_delivery_queue_slot=31),
    )
    assert report.next_delivery_slot == 32
    assert any(issue.code == "delivery_queue_safety_limit" for issue in report.issues)
    assert report.settlement_ready is False


def test_duplicate_delivery_slots_fail_settlement_readiness():
    evidence = _evidence(
        snapshot={"listing": {"auction_id": 55, "asking_price": 12000, "seller_id": 100}, "buyer": None},
        delivery_rows=({"box": 1, "slot": 8}, {"box": 1, "slot": 8}),
    )
    report = validate_legacy_invariants(
        operation="admin_cleanup",
        preview=_purchase_preview(mode="admin_cleanup"),
        evidence=evidence,
        policy=LegacyAuctionPolicy(),
    )
    assert any(issue.code == "delivery_slot_collision" for issue in report.issues)
    assert report.settlement_ready is False


def test_non_read_only_evidence_is_rejected():
    evidence = _evidence(
        snapshot={"item": {"item_id": 4096, "category_id": 9, "stack_size": 1}, "seller": {"char_id": 100}},
        seller_gil=5000,
        seller_active_listing_count=0,
        inventory_rows=({"quantity": 1},),
        transaction_mode="unknown",
    )
    report = validate_legacy_invariants(
        operation="list_item",
        preview=_list_preview(),
        evidence=evidence,
        policy=LegacyAuctionPolicy(),
    )
    assert any(issue.code == "reread_not_read_only" for issue in report.issues)
    assert report.invariants_ready is False
