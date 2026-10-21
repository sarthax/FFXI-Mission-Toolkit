"""Synthetic tests: no DSP access or mutation."""
import pytest
from workbench.server_admin.feature_testing import bounded_inventory as mod

class Cursor:
    def __init__(self, rows):
        self.rows = rows
    def execute(self, sql, args):
        assert sql.startswith("SELECT ")
        self.result = ({"charid": args[0]} if "FROM chars" in sql else
                       {"n": len([r for r in self.rows if r["location"] == args[1]])} if "COUNT" in sql else
                       [r for r in self.rows if r["location"] == args[1]][args[3]:args[3]+args[2]])
    def fetchone(self):
        return self.result
    def fetchall(self):
        return self.result
    def close(self):
        pass

class Conn:
    def rollback(self):
        pass
    def close(self):
        pass

def test_completeness_and_exdata(monkeypatch):
    rows = [{"location": 1, "slot": i, "itemId": 100+i, "quantity": 1, "extra": b"\x00" if i == 0 else None} for i in range(101)]
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), Cursor(rows)))
    first = mod.inventory_snapshot_v2(7, 1, 0, 100)
    assert first["status"] == "INCOMPLETE" and first["has_more"] and len(first["items"]) == 100
    assert first["items"][0]["extra_base64"] == "AA==" and first["items"][1]["extra_base64"] is None
    last = mod.inventory_snapshot_v2(7, 1, 100, 100)
    assert not last["complete"] and last["row_count"] == 1

def test_fail_closed(monkeypatch):
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: None)
    assert mod.inventory_snapshot_v2(7, 10)["status"] == "UNAVAILABLE"
    for container in (-1, 9, 999):
        with pytest.raises(ValueError):
            mod.inventory_snapshot_v2(7, container)
    with pytest.raises(ValueError):
        mod.inventory_snapshot_v2(7, 1, -1)
    with pytest.raises(ValueError):
        mod.inventory_snapshot_v2(7, 1, 0, 101)


def test_missing_character_never_looks_like_empty_complete(monkeypatch):
    class MissingCursor(Cursor):
        def fetchone(self):
            if "FROM chars" in self.last_sql:
                return None
            return super().fetchone()
        def execute(self, sql, args):
            self.last_sql = sql
            super().execute(sql, args)
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), MissingCursor([])))
    result = mod.inventory_snapshot_v2(7, 1)
    assert result["status"] == "UNKNOWN_CHARACTER"
    assert result["complete"] is False and result["total_rows"] is None

def test_safe_and_safe2_are_distinct_scopes(monkeypatch):
    rows = [
        {"location": 1, "slot": 0, "itemId": 101, "quantity": 2, "extra": b""},
        {"location": 10, "slot": 0, "itemId": 202, "quantity": 1, "extra": None},
    ]
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), Cursor(rows)))
    safe1 = mod.inventory_snapshot_v2(7, 1)
    safe2 = mod.inventory_snapshot_v2(7, 10)
    assert safe1["complete"] and safe2["complete"]
    assert safe1["items"][0]["itemId"] == 101
    assert safe2["items"][0]["itemId"] == 202
    assert safe1["items"][0]["extra_base64"] == ""
    assert safe2["items"][0]["extra_base64"] is None

def test_disallowed_character_rejected_before_query(monkeypatch):
    def reject(charid):
        raise ValueError("character not approved for supervisor diagnostics")
    monkeypatch.setattr(mod, "_approved_connection", reject)
    with pytest.raises(ValueError, match="not approved"):
        mod.inventory_snapshot_v2(99, 1)
