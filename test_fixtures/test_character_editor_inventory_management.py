from __future__ import annotations

from pathlib import Path

from workbench.editors.character.inventory_management import (
    InventoryManagementIssue,
    InventoryManagementPlan,
    apply_inventory_management,
)
from workbench.editors.character.inventory_slots import CAPACITY_COLUMNS

ROOT = Path(__file__).resolve().parents[1]


class _NoWriteConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_inventory_management_requires_explicit_approval_before_touching_db():
    con = _NoWriteConnection()
    plan = InventoryManagementPlan(
        char_id=1,
        action="remove",
        source_location=0,
        source_slot=1,
        source_fingerprint="abc",
        source={"charid": 1, "location": 0, "slot": 1, "itemId": 4096, "quantity": 1, "bazaar": 0, "signature": "", "extra": b""},
        item={"item_id": 4096, "name": "Potion", "stack_size": 12},
        quantity_after=None,
        destination_location=None,
        destination_slot=None,
        online=False,
        adapter_family="lsb",
        issues=[],
    )
    try:
        apply_inventory_management(con, plan, approved=False)
    except PermissionError:
        pass
    else:
        raise AssertionError("unapproved inventory management was not blocked")
    assert con.commits == 0
    assert con.rollbacks == 0


def test_inventory_management_issue_blocks_plan():
    plan = InventoryManagementPlan(
        char_id=1,
        action="move",
        source_location=0,
        source_slot=1,
        source_fingerprint="abc",
        source={"itemId": 4096},
        item={"item_id": 4096, "stack_size": 12},
        quantity_after=None,
        destination_location=2,
        destination_slot=None,
        online=False,
        adapter_family="topaz",
        issues=[InventoryManagementIssue("destination_not_safe", "Storage capacity is runtime-derived")],
    )
    assert plan.ready is False


def test_direct_destination_contract_excludes_runtime_derived_containers():
    assert 0 in CAPACITY_COLUMNS
    assert 1 in CAPACITY_COLUMNS
    assert 4 in CAPACITY_COLUMNS
    assert 8 in CAPACITY_COLUMNS
    assert 16 in CAPACITY_COLUMNS
    assert 2 not in CAPACITY_COLUMNS  # Storage is furnishing-derived.
    assert 3 not in CAPACITY_COLUMNS  # Temporary Items are runtime-managed.


def test_inventory_management_http_and_ui_contract():
    gui = (ROOT / "src" / "workbench" / "editors" / "character" / "gui.py").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "character_editor_inventory_manage.js").read_text(encoding="utf-8")
    wrapper = (ROOT / "gui" / "templates" / "character_editor_progression.html").read_text(encoding="utf-8")
    injection = (ROOT / "src" / "workbench" / "editors" / "character" / "item_transactions.py").read_text(encoding="utf-8")

    assert '/characters/{char_id}/inventory/preview' in gui
    assert '/characters/{char_id}/inventory/apply' in gui
    assert 'expected_source_fingerprint' in gui
    assert 'apply_inventory_management' in gui
    assert '/static/character_editor_inventory_manage.js' in wrapper

    assert '/inventory/preview' in script
    assert '/inventory/apply' in script
    assert 'expected_source_fingerprint' in script
    assert "data-action=\"quantity\"" in script
    assert "data-action=\"move\"" in script
    assert "data-action=\"remove\"" in script
    assert 'editableOnline()' in script
    assert 'itemLocation' in script
    assert 'destination_location' in script
    assert 'Storage and Temporary Items remain protected' in script

    assert 'location not in CAPACITY_COLUMNS' in injection
    assert 'location_name' in injection


if __name__ == "__main__":
    test_inventory_management_requires_explicit_approval_before_touching_db()
    test_inventory_management_issue_blocks_plan()
    test_direct_destination_contract_excludes_runtime_derived_containers()
    test_inventory_management_http_and_ui_contract()
