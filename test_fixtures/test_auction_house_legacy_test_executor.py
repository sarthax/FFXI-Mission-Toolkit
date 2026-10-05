from __future__ import annotations

import pytest

from workbench.server_admin.auction_house.legacy_test_executor import (
    LegacyTestExecutionBlocked,
    evaluate_legacy_test_write_gate,
    execute_legacy_test_price_change,
)


class _Schema:
    family_hint = "legacy-dsp-topaz-compatible"
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


def _env(family="topaz", **overrides):
    value = {
        "profile_id": 2,
        "name": f"{family.upper()} Test",
        "environment": "test",
        "family": family,
        "enabled": True,
        "is_active": True,
    }
    value.update(overrides)
    return value


def test_gate_allows_topaz_and_dsp_test_only_with_flag_and_confirmation():
    for family in ("topaz", "dsp"):
        env = _env(family)
        result = evaluate_legacy_test_write_gate(
            environment=env,
            schema_family_hint="legacy-dsp-topaz-compatible",
            confirmation=env["name"],
            feature_enabled=True,
        )
        assert result.ready is True


def test_gate_rejects_live_wrong_family_wrong_schema_confirmation_and_flag():
    cases = (
        (_env("topaz", environment="live"), "legacy-dsp-topaz-compatible", "TOPAZ Test", True, "environment_not_test"),
        (_env("lsb"), "legacy-dsp-topaz-compatible", "LSB Test", True, "lineage_not_legacy_supported"),
        (_env("dsp"), "lsb-compatible", "DSP Test", True, "schema_not_legacy_compatible"),
        (_env("dsp"), "legacy-dsp-topaz-compatible", "wrong", True, "test_confirmation_required"),
        (_env("topaz"), "legacy-dsp-topaz-compatible", "TOPAZ Test", False, "legacy_test_write_feature_disabled"),
    )
    for environment, schema, confirmation, enabled, code in cases:
        result = evaluate_legacy_test_write_gate(
            environment=environment,
            schema_family_hint=schema,
            confirmation=confirmation,
            feature_enabled=enabled,
        )
        assert result.ready is False
        assert code in {issue.code for issue in result.issues}


@pytest.mark.parametrize("family", ["topaz", "dsp"])
def test_price_change_commits_one_active_legacy_test_row(family):
    service = _Service({55: {"price": 12000, "sale": 0}})
    env = _env(family)
    result = execute_legacy_test_price_change(
        service=service,
        environment=env,
        auction_id=55,
        expected_price=12000,
        new_price=12500,
        confirmation=env["name"],
        feature_enabled=True,
    )
    assert result["status"] == "committed"
    assert result["family"] == family
    assert result["before"]["asking_price"] == 12000
    assert result["after"]["asking_price"] == 12500
    assert service.connection.rows[55]["price"] == 12500
    assert service.connection.commits == 1
    assert service.connection.rollbacks == 0


def test_stale_preview_rolls_back():
    service = _Service({55: {"price": 13000, "sale": 0}})
    env = _env("topaz")
    with pytest.raises(LegacyTestExecutionBlocked, match="changed after preview"):
        execute_legacy_test_price_change(
            service=service,
            environment=env,
            auction_id=55,
            expected_price=12000,
            new_price=12500,
            confirmation=env["name"],
            feature_enabled=True,
        )
    assert service.connection.rows[55]["price"] == 13000
    assert service.connection.commits == 0
    assert service.connection.rollbacks == 1


def test_sold_row_and_missing_row_roll_back():
    env = _env("dsp")
    sold = _Service({55: {"price": 12000, "sale": 12000}})
    with pytest.raises(LegacyTestExecutionBlocked, match="no longer active"):
        execute_legacy_test_price_change(
            service=sold,
            environment=env,
            auction_id=55,
            expected_price=12000,
            new_price=12500,
            confirmation=env["name"],
            feature_enabled=True,
        )
    assert sold.connection.commits == 0
    assert sold.connection.rollbacks == 1

    missing = _Service({})
    with pytest.raises(LegacyTestExecutionBlocked, match="does not exist"):
        execute_legacy_test_price_change(
            service=missing,
            environment=env,
            auction_id=55,
            expected_price=12000,
            new_price=12500,
            confirmation=env["name"],
            feature_enabled=True,
        )
    assert missing.connection.commits == 0
    assert missing.connection.rollbacks == 1


def test_live_environment_never_executes_even_with_feature_enabled():
    service = _Service({55: {"price": 12000, "sale": 0}})
    env = _env("topaz", environment="live")
    with pytest.raises(LegacyTestExecutionBlocked, match="environment_not_test"):
        execute_legacy_test_price_change(
            service=service,
            environment=env,
            auction_id=55,
            expected_price=12000,
            new_price=12500,
            confirmation=env["name"],
            feature_enabled=True,
        )
    assert service.connection.rows[55]["price"] == 12000
    assert service.connection.commits == 0
