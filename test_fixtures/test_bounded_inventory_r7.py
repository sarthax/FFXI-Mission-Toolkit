"""Synthetic tests: no DSP access or mutation."""
import pytest
from workbench.server_admin.feature_testing import bounded_inventory as mod

class Cursor:
    def __init__(self, rows):
        self.rows = rows
    def execute(self, sql, args):
        assert sql.startswith("SELECT ")
        self.result = ({"n": len(self.rows)} if "COUNT" in sql else
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
