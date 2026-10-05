from __future__ import annotations

import pytest

from workbench.server_admin.auction_house.test_executor import (
    TestExecutionBlocked,
    evaluate_lsb_test_write_gate,
    execute_lsb_test_price_change,
)


class _Schema:
    family_hint = "lsb-compatible"
    auction_columns = {"id": "id", "asking_price": "price", "sale_price": "sale"}


class _Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rowcount = 0
        self._row = None

    def execute(self, sql, params=None):
        params = params or ()
        if sql == "START TRANSACTION":
            self.connection.in_transaction = True
            return
        if sql.startswith("SELECT"):
            auction_id = int(params[0])
            row = self.connection.rows.get(auction_id)
            self._row = None if row is None else (auction_id, row["price"], row["sale"])
            return
        if sql.startswith("UPDATE"):
            new_price, auction_id, expected_price = map(int, params)
            row = self.connection.rows.get(auction_id)
            if row and row["price"] == expected_price and row["sale"] == 0:
                row["price"] = new_price
                self.rowcount = 1
            else:
                self.rowcount = 0
            return
        raise AssertionError(sql)

    def fetchone(self):
        return self._row

    def close(self):
        pass


class _Connection:
    def __init__(self, rows):
        self.rows = {key: dict(value) for key, value in rows.items()}
        self._before = None
        self.in_transaction = False
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        if not self.in_transaction:
            self._before = {key: dict(value) for key, value in self.rows.items()}
        return _Cursor(self)

    def commit(self):
        self.commits += 1
        self.in_transaction = False
        self._before = None

    def rollback(self):
        self.rollbacks += 1
        if self._before is not None:
            self.rows = {key: dict(value) for key, value in self._before.items()}
        self.in_transaction = False


class _Service:
    def __init__(self, rows):
        self.schema = _Schema()
        self.connection = _Connection(rows)


def _env(**overrides):
    value = {
        "profile_id": 2,
        "name": "LSB Test",
        "environment": "test",
        "family": "lsb",
        "enabled": True,
        "is_active": True,
    }
    value.update(overrides)
    return value


def test_gate_requires_lsb_test_feature_flag_and_exact_confirmation():
    ready = evaluate_lsb_test_write_gate(
        environment=_env(),
        schema_family_hint="lsb-compatible",
        confirmation="LSB Test",
        feature_enabled=True,
    )
    assert ready.ready is True

    for environment, schema, confirmation, enabled, code in (
        (_env(environment="live"), "lsb-compatible", "LSB Test", True, "environment_not_test"),
        (_env(family="topaz"), "lsb-compatible", "LSB Test", True, "lineage_not_lsb"),
        (_env(), "legacy-dsp-topaz-compatible", "LSB Test", True, "schema_not_lsb_compatible"),
        (_env(), "lsb-compatible", "wrong", True, "test_confirmation_required"),
        (_env(), "lsb-compatible", "LSB Test", False, "test_write_feature_disabled"),
    ):
        result = evaluate_lsb_test_write_gate(
            environment=environment,
            schema_family_hint=schema,
            confirmation=confirmation,
            feature_enabled=enabled,
        )
        assert result.ready is False
        assert code in {issue.code for issue in result.issues}


def test_price_change_commits_exactly_one_active_test_row():
    service = _Service({55: {"price": 12000, "sale": 0}})
    result = execute_lsb_test_price_change(
        service=service,
        environment=_env(),
        auction_id=55,
        expected_price=12000,
        new_price=12500,
        confirmation="LSB Test",
        feature_enabled=True,
    )
    assert result["status"] == "committed"
    assert result["before"]["asking_price"] == 12000
    assert result["after"]["asking_price"] == 12500
    assert service.connection.rows[55]["price"] == 12500
    assert service.connection.commits == 1
    assert service.connection.rollbacks == 0


def test_price_change_rejects_stale_preview_and_rolls_back():
    service = _Service({55: {"price": 13000, "sale": 0}})
    with pytest.raises(TestExecutionBlocked, match="changed after preview"):
        execute_lsb_test_price_change(
            service=service,
            environment=_env(),
            auction_id=55,
            expected_price=12000,
            new_price=12500,
            confirmation="LSB Test",
            feature_enabled=True,
        )
    assert service.connection.rows[55]["price"] == 13000
    assert service.connection.commits == 0
    assert service.connection.rollbacks == 1


def test_price_change_rejects_sold_row_and_never_commits():
    service = _Service({55: {"price": 12000, "sale": 12000}})
    with pytest.raises(TestExecutionBlocked, match="no longer active"):
        execute_lsb_test_price_change(
            service=service,
            environment=_env(),
            auction_id=55,
            expected_price=12000,
            new_price=12500,
            confirmation="LSB Test",
            feature_enabled=True,
        )
    assert service.connection.rows[55]["price"] == 12000
    assert service.connection.commits == 0
    assert service.connection.rollbacks == 1


def test_live_environment_can_never_execute_even_with_feature_enabled():
    service = _Service({55: {"price": 12000, "sale": 0}})
    with pytest.raises(TestExecutionBlocked, match="environment_not_test"):
        execute_lsb_test_price_change(
            service=service,
            environment=_env(environment="live"),
            auction_id=55,
            expected_price=12000,
            new_price=12500,
            confirmation="LSB Test",
            feature_enabled=True,
        )
    assert service.connection.rows[55]["price"] == 12000
    assert service.connection.commits == 0
