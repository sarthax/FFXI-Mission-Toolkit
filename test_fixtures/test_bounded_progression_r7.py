"""Offline regression contract: no MySQL or live character is accessed."""
import pytest
from workbench.server_admin.feature_testing import bounded_progression as mod

class Cursor:
    def execute(self, sql, args):
        assert sql.startswith("SELECT ")
        self.query = sql
    def fetchall(self):
        return [{"varname": "Flag", "value": 0}]
    def fetchone(self):
        return {"keyitems": bytes(896)}
    def close(self):
        pass

class Conn:
    def rollback(self):
        pass
    def close(self):
        pass

def test_explicit_absence_zero_and_no_fabricated_fields(monkeypatch):
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), Cursor()))
    r = mod.progression_snapshot(9, ["Flag", "Missing"])
    assert r["vars"]["Flag"] == {"found": True, "status": "PRESENT", "value": 0}
    assert r["vars"]["Missing"]["status"] == "ABSENT"
    assert r["keyitems"]["status"] == "COMPLETE"
    assert r["currencies"]["status"] == "UNSUPPORTED" and r["jobs"]["status"] == "UNSUPPORTED"
    assert r["complete"] is False and r["execution_enabled"] is False

def test_unavailable_and_names(monkeypatch):
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: None)
    assert mod.progression_snapshot(9, ["One"])["status"] == "UNAVAILABLE"
    for names in ([], ["a", "a"], ["bad-name"], ["n"] * 51):
        with pytest.raises(ValueError):
            mod.progression_snapshot(9, names)
