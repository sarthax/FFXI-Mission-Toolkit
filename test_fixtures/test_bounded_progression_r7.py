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
        return {"charid": 9} if "SELECT charid FROM chars" in self.query else {"keyitems": bytes(896)}
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


def test_disallowed_character_rejected_before_query(monkeypatch):
    def reject(charid):
        raise ValueError("character not approved for supervisor diagnostics")
    monkeypatch.setattr(mod, "_approved_connection", reject)
    with pytest.raises(ValueError, match="not approved"):
        mod.progression_snapshot(999, ["Flag"])

def test_truncated_keyitems_remains_incomplete(monkeypatch):
    class ShortBitmap(Cursor):
        def fetchone(self):
            return {"charid": 9} if "SELECT charid FROM chars" in self.query else {"keyitems": bytes(24)}
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), ShortBitmap()))
    report = mod.progression_snapshot(9, ["Flag"])
    assert report["keyitems"]["status"] == "INCOMPLETE"
    assert report["keyitems"]["blob_bytes"] == 24
    assert report["supported_fields_complete"] is False
    assert report["complete"] is False

def test_missing_character_keyitems_is_not_empty_bitmap(monkeypatch):
    class NoCharacter(Cursor):
        def fetchone(self):
            return None
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), NoCharacter()))
    report = mod.progression_snapshot(9, ["Flag"])
    assert report["keyitems"]["status"] == "UNKNOWN_CHARACTER"
    assert report["supported_fields_complete"] is False
    assert report["complete"] is False


def test_missing_character_without_keyitems_never_claims_complete(monkeypatch):
    class MissingCharacter(Cursor):
        def fetchone(self):
            return None
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), MissingCharacter()))
    result = mod.progression_snapshot(9, ["Flag"], include_keyitems=False)
    assert result["status"] == "UNKNOWN_CHARACTER"
    assert result["complete"] is False
    assert result["supported_fields_complete"] is False
    assert result["keyitems"]["status"] == "NOT_REQUESTED"

def test_valid_character_without_keyitems_has_scoped_completeness(monkeypatch):
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), Cursor()))
    result = mod.progression_snapshot(9, ["Flag"], include_keyitems=False)
    assert result["supported_fields_complete"] is True
    assert result["complete"] is False
    assert result["keyitems"]["status"] == "NOT_REQUESTED"


def test_existing_character_absent_variable(monkeypatch):
    class EmptyVars(Cursor):
        def fetchall(self):
            return []
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), EmptyVars()))
    result = mod.progression_snapshot(9, ["NotPresent"], include_keyitems=False)
    assert result["status"] == "COMPLETE_SUPPORTED_FIELDS"
    assert result["vars"]["NotPresent"] == {"found": False, "status": "ABSENT", "value": None}
    assert result["complete"] is False

def test_null_keyitems_incomplete(monkeypatch):
    class NullBitmap(Cursor):
        def fetchone(self):
            return {"charid": 9} if "SELECT charid FROM chars" in self.query else {"keyitems": None}
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), NullBitmap()))
    result = mod.progression_snapshot(9, ["Flag"])
    assert result["keyitems"]["status"] == "INCOMPLETE"
    assert result["keyitems"]["blob_bytes"] == 0

def test_select_permission_failure_closes_read_only_connection(monkeypatch):
    calls = []
    class Denied(Cursor):
        def execute(self, sql, args):
            assert sql.startswith("SELECT ")
            calls.append("select")
            raise PermissionError("database SELECT grant absent")
        def close(self):
            calls.append("cursor_close")
    class Connection(Conn):
        def rollback(self):
            calls.append("rollback")
        def close(self):
            calls.append("connection_close")
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Connection(), Denied()))
    with pytest.raises(RuntimeError, match="progression observation unavailable"):
        mod.progression_snapshot(9, ["Flag"])
    assert calls == ["select", "rollback", "cursor_close", "connection_close"]
