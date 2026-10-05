from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked
from workbench.server_admin.auction_house.reward_delivery import preview_reward_delivery


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, sql, params=()):
        if sql.startswith("DESCRIBE `chars`"):
            self.rows = [("charid",), ("charname",)]
        elif "FROM `chars`" in sql:
            if " IN (" in sql:
                wanted = {int(value) for value in params}
                self.rows = [row for row in self.connection.characters if row[0] in wanted]
            else:
                limit = int(params[0]) if params else 5001
                self.rows = list(self.connection.characters)[:limit]
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class Connection:
    def __init__(self, characters):
        self.characters = list(characters)

    def cursor(self):
        return Cursor(self)


class Service:
    def __init__(self):
        self.connection = Connection([(1, "Alpha"), (2, "Beta")])
        self.schema = SimpleNamespace(family_hint="legacy-compatible")

    def item_snapshot(self, item_id):
        if int(item_id) != 100:
            return None
        return {"item_id": 100, "name": "Potion", "stack_size": 12}


def test_preview_selected_resolves_exact_recipient_order():
    preview = preview_reward_delivery(
        service=Service(),
        mode="selected",
        character_ids=[2, 1],
        items=[{"item_id": 100, "quantity": 12}],
    )
    assert [row["char_id"] for row in preview["recipients"]] == [1, 2]
    assert preview["delivery_rows"] == 2
    assert preview["preview_token"]
    assert preview["replay_id"]


def test_preview_all_resolves_all_characters():
    preview = preview_reward_delivery(
        service=Service(),
        mode="all",
        character_ids=[],
        items=[{"item_id": 100, "quantity": 1}],
    )
    assert preview["recipient_count"] == 2


def test_preview_rejects_missing_recipient_and_invalid_stack_quantity():
    with pytest.raises(LegacyTestExecutionBlocked, match="were not found"):
        preview_reward_delivery(
            service=Service(),
            mode="selected",
            character_ids=[1, 99],
            items=[{"item_id": 100, "quantity": 1}],
        )
    with pytest.raises(LegacyTestExecutionBlocked, match="exceeds stack size"):
        preview_reward_delivery(
            service=Service(),
            mode="selected",
            character_ids=[1],
            items=[{"item_id": 100, "quantity": 13}],
        )
