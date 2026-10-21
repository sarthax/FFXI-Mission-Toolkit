import pytest

from workbench.server_admin.feature_testing import database_diagnostics as dd


def _blob(owned=(), seen=()):
    data = bytearray(7 * 128)
    for ids, offset in ((owned, 0), (seen, 64)):
        for ki in ids:
            table, bit = divmod(ki, 512)
            data[table * 128 + offset + bit // 8] |= 1 << (bit % 8)
    return bytes(data)


def test_decode_keyitems_round_trip_across_tables():
    out = dd.decode_keyitems(_blob(owned=[1, 8, 511, 512, 3000], seen=[8, 513]))
    assert out["owned"] == [1, 8, 511, 512, 3000]
    assert out["seen"] == [8, 513]
    assert out["blob_bytes"] == out["expected_bytes"] == 896


def test_decode_keyitems_tolerates_short_or_missing_blob():
    assert dd.decode_keyitems(None)["owned"] == []
    assert dd.decode_keyitems(_blob(owned=[2])[:10])["owned"] == [2]


def test_unapproved_character_refused(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "5")
    for call in (lambda: dd.key_items_snapshot(6), lambda: dd.char_vars_snapshot(6, ["a"])):
        with pytest.raises(ValueError):
            call()


def test_unconfigured_db_is_not_observed(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "5")
    for key in ("USER", "PASSWORD", "NAME"):
        monkeypatch.delenv("MISSION_TOOLKIT_SUPERVISOR_DB_" + key, raising=False)
    assert dd.key_items_snapshot(5)["configured"] is False
    assert dd.char_vars_snapshot(5, ["a"])["configured"] is False


@pytest.mark.parametrize("names", [[], ["a'b"], ["x" * 31], ["%"], ["ok"] * 0])
def test_char_vars_rejects_bad_names(monkeypatch, names):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "5")
    with pytest.raises(ValueError):
        dd.char_vars_snapshot(5, names)


class _Cur:
    def __init__(self, rows): self.rows, self.sql = rows, []
    def execute(self, sql, params=None): self.sql.append(sql)
    def fetchone(self): return self.rows[0] if self.rows else None
    def fetchall(self): return self.rows
    def close(self): pass


class _Conn:
    def rollback(self): pass
    def close(self): pass


def test_queries_are_select_only_and_fixed(monkeypatch):
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "5")
    cur = _Cur([{"keyitems": _blob(owned=[7])}])
    monkeypatch.setattr(dd, "_approved_connection", lambda charid: (_Conn(), cur))
    assert dd.key_items_snapshot(5)["owned"] == [7]
    cur2 = _Cur([{"varname": "a", "value": 3}])
    monkeypatch.setattr(dd, "_approved_connection", lambda charid: (_Conn(), cur2))
    assert dd.char_vars_snapshot(5, ["a", "b"])["vars"] == {"a": 3, "b": None}
    assert all(s.lstrip().upper().startswith("SELECT") for s in cur.sql + cur2.sql)
