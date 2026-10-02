from __future__ import annotations

from workbench.editors.character.adapters.inventory import (
    CORE_COLUMNS,
    build_basic_insert_plan,
    inspect_inventory_contract,
)
from workbench.editors.character.schema import CharacterSchema, ColumnInfo, TableInfo
from workbench.editors.character.session_state import detect_online_state


def _col(name: str, sql_type: str = "int") -> ColumnInfo:
    return ColumnInfo(name, sql_type, False, "", None, "")


def _schema(*, include_sessions: bool = True, inventory_columns=CORE_COLUMNS):
    inventory = TableInfo(
        "char_inventory",
        [_col(c, "blob(24)" if c == "extra" else "int") for c in inventory_columns],
        "inventory",
        "charid",
    )
    tables = {"char_inventory": inventory}
    caps = {"inventory": ["char_inventory"]}
    if include_sessions:
        sessions = TableInfo(
            "accounts_sessions",
            [_col("charid"), _col("accid")],
            "sessions",
            "charid",
        )
        tables["accounts_sessions"] = sessions
        caps["sessions"] = ["accounts_sessions"]
    return CharacterSchema(tables=tables, capabilities=caps, packed_profile_fields={})


def test_inventory_contract_accepts_shared_reference_shape():
    contract = inspect_inventory_contract(_schema(), "lsb")
    assert contract.valid
    assert contract.basic_insert_verified
    assert contract.missing_columns == ()
    assert not contract.extra_codec_verified

    plan = build_basic_insert_plan(
        contract,
        char_id=123,
        item_id=4096,
        location=0,
        slot=1,
        quantity=2,
    )
    assert plan["operation"] == "insert"
    assert plan["table"] == "char_inventory"
    assert plan["params"][:5] == (123, 0, 1, 4096, 2)


def test_inventory_contract_rejects_schema_drift_and_unverified_extra():
    contract = inspect_inventory_contract(_schema(inventory_columns=CORE_COLUMNS[:-1]), "topaz")
    assert not contract.valid
    assert contract.missing_columns == ("extra",)

    good = inspect_inventory_contract(_schema(), "dsp")
    try:
        build_basic_insert_plan(
            good,
            char_id=1,
            item_id=2,
            location=0,
            slot=0,
            quantity=1,
            extra=b"opaque",
        )
    except RuntimeError as exc:
        assert "verified lineage-specific codec" in str(exc)
    else:
        raise AssertionError("opaque extra data must remain blocked")


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.executed = None
        self.closed = False

    def execute(self, sql, params):
        self.executed = (sql, params)

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class _Connection:
    def __init__(self, row):
        self.row = row
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = _Cursor(self.row)
        return self.last_cursor


def test_online_state_uses_accounts_sessions_row_presence():
    online_conn = _Connection((1,))
    state = detect_online_state(online_conn, _schema(), 42)
    assert state.online is True
    assert state.source_table == "accounts_sessions"
    assert online_conn.last_cursor.executed[1] == (42,)
    assert online_conn.last_cursor.closed

    offline = detect_online_state(_Connection(None), _schema(), 42)
    assert offline.online is False


def test_online_state_is_unknown_when_session_table_is_missing():
    state = detect_online_state(_Connection(None), _schema(include_sessions=False), 42)
    assert state.online is None
    assert state.reason == "accounts_sessions_not_detected"
