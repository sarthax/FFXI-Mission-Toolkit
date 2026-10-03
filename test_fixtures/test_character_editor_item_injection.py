from __future__ import annotations

from workbench.editors.character.item_catalog import EXCLUSIVE_FLAG, RARE_FLAG, ItemCatalogRecord
from workbench.editors.character.inventory_slots import CONTAINERS
from workbench.editors.character.item_transactions import ItemInjectionPlan, TransactionIssue, apply_item_injection


def test_item_flag_decode_and_container_ids():
    item = ItemCatalogRecord(1, "Test", RARE_FLAG | EXCLUSIVE_FLAG, 1)
    assert item.rare is True
    assert item.exclusive is True
    assert CONTAINERS[0] == "Inventory"
    assert CONTAINERS[8] == "Wardrobe"
    assert CONTAINERS[16] == "Wardrobe 8"


class _NoWriteConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_item_injection_requires_explicit_approval_before_touching_db():
    con = _NoWriteConnection()
    plan = ItemInjectionPlan(
        char_id=1,
        item=ItemCatalogRecord(4096, "Potion", 0, 12),
        quantity=1,
        location=0,
        slot=1,
        online=False,
        adapter_family="lsb",
        issues=[],
    )
    try:
        apply_item_injection(con, plan, approved=False)
    except PermissionError:
        pass
    else:
        raise AssertionError("unapproved item injection was not blocked")
    assert con.commits == 0
    assert con.rollbacks == 0


def test_blocking_issue_prevents_write_ready_plan():
    plan = ItemInjectionPlan(
        char_id=1,
        item=ItemCatalogRecord(4096, "Potion", 0, 12),
        quantity=1,
        location=0,
        slot=1,
        online=True,
        adapter_family="topaz",
        issues=[TransactionIssue("character_online", "Character is online")],
    )
    assert plan.ready is False
    assert plan.as_dict()["issues"][0]["code"] == "character_online"
