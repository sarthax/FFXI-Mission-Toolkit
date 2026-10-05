from types import SimpleNamespace

import pytest

from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked
from workbench.server_admin.auction_house.reward_delivery import execute_reward_delivery, preview_reward_delivery


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
    def __init__(self, characters):
        self.connection = Connection(characters)
        self.schema = SimpleNamespace(family_hint="legacy-compatible")

    def item_snapshot(self, item_id):
        if int(item_id) == 100:
            return {"item_id": 100, "name": "Potion", "stack_size": 12}
        return None


def _allow(monkeypatch, module):
    monkeypatch.setattr(module, "evaluate_legacy_test_write_gate", lambda **kwargs: SimpleNamespace(ready=True, issues=[]))
    monkeypatch.setattr(module, "_validate_delivery_write_path", lambda service: None)


def test_execution_rejects_recipient_drift(monkeypatch):
    import workbench.server_admin.auction_house.reward_delivery as module

    service = Service([(1, "Alpha")])
    preview = preview_reward_delivery(
        service=service,
        mode="all",
        character_ids=[],
        items=[{"item_id": 100, "quantity": 1}],
    )
    service.connection.characters.append((2, "Beta"))
    _allow(monkeypatch, module)
    with pytest.raises(LegacyTestExecutionBlocked, match="stale"):
        execute_reward_delivery(
            service=service,
            environment={},
            mode="all",
            character_ids=[],
            items=[{"item_id": 100, "quantity": 1}],
            preview_token=preview["preview_token"],
            preview_id=preview["preview_id"],
            replay_id=preview["replay_id"],
            confirmation="Test",
            feature_enabled=True,
        )


def test_execution_reports_partial_per_recipient(monkeypatch):
    import workbench.server_admin.auction_house.reward_delivery as module

    service = Service([(1, "Alpha"), (2, "Beta")])
    preview = preview_reward_delivery(
        service=service,
        mode="selected",
        character_ids=[1, 2],
        items=[{"item_id": 100, "quantity": 1}],
    )
    _allow(monkeypatch, module)
    monkeypatch.setattr(module, "claim_replay_once", lambda **kwargs: None)

    def deliver(service, recipient, items):
        if recipient["char_id"] == 2:
            raise RuntimeError("box full")
        return {"char_id": 1, "char_name": "Alpha", "status": "committed", "rows": 1}

    monkeypatch.setattr(module, "_deliver_one", deliver)
    result = execute_reward_delivery(
        service=service,
        environment={},
        mode="selected",
        character_ids=[1, 2],
        items=[{"item_id": 100, "quantity": 1}],
        preview_token=preview["preview_token"],
        preview_id=preview["preview_id"],
        replay_id=preview["replay_id"],
        confirmation="Test",
        feature_enabled=True,
    )
    assert result["status"] == "partial"
    assert result["committed_recipients"] == 1
    assert result["failed_recipients"] == 1
