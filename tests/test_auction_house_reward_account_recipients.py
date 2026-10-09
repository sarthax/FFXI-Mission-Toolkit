"""Account-scoped Mog Inbox recipient selection is schema-backed and fail-closed."""
import pytest

from workbench.server_admin.auction_house.legacy_test_executor import LegacyTestExecutionBlocked
from workbench.server_admin.auction_house.reward_delivery import _resolve_recipients


class Cursor:
    def __init__(self, account_field="accid", account=77):
        self.account_field = account_field
        self.account = account
        self.result = []
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        if sql == "DESCRIBE `chars`":
            fields = ["charid", "charname"]
            if self.account_field:
                fields.append(self.account_field)
            self.result = [(field,) for field in fields]
        elif "SELECT `accid`" in sql or "SELECT `account_id`" in sql:
            self.result = [(self.account,)] if self.account else []
        elif "WHERE `accid`=%s" in sql or "WHERE `account_id`=%s" in sql:
            self.result = [(11, "Alpha"), (12, "Beta")]
        else:
            raise AssertionError(f"Unexpected SQL: {sql}")

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0] if self.result else None

    def close(self):
        pass


class Connection:
    def __init__(self, **kwargs):
        self.c = Cursor(**kwargs)

    def cursor(self):
        return self.c


class Service:
    def __init__(self, **kwargs):
        self.connection = Connection(**kwargs)


def test_account_mode_includes_only_verified_account_characters():
    service = Service()
    assert _resolve_recipients(service, mode="account", character_ids=[11]) == [
        {"char_id": 11, "char_name": "Alpha"}, {"char_id": 12, "char_name": "Beta"}
    ]
    queries = service.connection.c.queries
    assert any("WHERE `accid`=%s" in sql and params[0] == 77 for sql, params in queries)


@pytest.mark.parametrize("anchors", [[], [0], [11, 12], [-1]])
def test_account_mode_requires_exactly_one_valid_anchor(anchors):
    with pytest.raises(LegacyTestExecutionBlocked, match="exactly one"):
        _resolve_recipients(Service(), mode="account", character_ids=anchors)


def test_account_mode_rejects_missing_account_schema():
    with pytest.raises(LegacyTestExecutionBlocked, match="schema"):
        _resolve_recipients(Service(account_field=None), mode="account", character_ids=[11])


def test_account_mode_rejects_unlinked_character():
    with pytest.raises(LegacyTestExecutionBlocked, match="account linkage"):
        _resolve_recipients(Service(account=None), mode="account", character_ids=[11])
