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


def test_oversized_extra_fails_closed(monkeypatch):
    rows = [{"location": 1, "slot": 1, "itemId": 111, "quantity": 1,
             "extra": bytes(mod._MAX_EXTRA_BYTES + 1)}]
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), Cursor(rows)))
    result = mod.inventory_snapshot_v2(7, 1)
    assert result["status"] == "INCOMPLETE_OVERSIZED_EXTRA"
    assert result["complete"] is False and result["items"] == []

def test_aggregate_extra_budget_fails_closed(monkeypatch):
    rows = [{"location": 1, "slot": i, "itemId": 100+i, "quantity": 1,
             "extra": bytes(mod._MAX_EXTRA_BYTES)} for i in range(20)]
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), Cursor(rows)))
    result = mod.inventory_snapshot_v2(7, 1)
    assert result["status"] == "INCOMPLETE_RESPONSE_BUDGET"
    assert result["complete"] is False and result["items"] == []

def test_count_page_disagreement_is_not_complete(monkeypatch):
    class ContradictingCursor(Cursor):
        def execute(self, sql, args):
            super().execute(sql, args)
            if "COUNT(*)" in sql:
                self.result = {"n": 1}
    rows = [{"location": 1, "slot": 0, "itemId": 2, "quantity": 1, "extra": None},
            {"location": 1, "slot": 1, "itemId": 3, "quantity": 1, "extra": None}]
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Conn(), ContradictingCursor(rows)))
    result = mod.inventory_snapshot_v2(7, 1)
    assert result["status"] == "INCOMPLETE_INCONSISTENT_PAGE"
    assert result["complete"] is False

def test_select_privilege_failure_rolls_back_and_closes(monkeypatch):
    calls = []
    class Denied(Cursor):
        def execute(self, sql, args):
            raise PermissionError("SELECT denied")
        def close(self):
            calls.append("cursor_close")
    class Connection(Conn):
        def rollback(self):
            calls.append("rollback")
        def close(self):
            calls.append("connection_close")
    monkeypatch.setattr(mod, "_approved_connection", lambda charid: (Connection(), Denied([])))
    with pytest.raises(RuntimeError, match="inventory observation unavailable"):
        mod.inventory_snapshot_v2(7, 1)
    assert calls == ["rollback", "cursor_close", "connection_close"]


def test_http_supervisor_token_and_character_scope_without_database(monkeypatch):
    """Exercise the real route/bearer and existing approved-character guard.

    No DB connection is made: approved disposable id with no configured DB is
    unavailable, rather than an empty COMPLETE snapshot.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from workbench.server_admin.feature_testing import supervisor

    app = FastAPI()
    app.include_router(supervisor.router)
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "s" * 40)
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS", "7")
    for key in ("MISSION_TOOLKIT_SUPERVISOR_DB_USER",
                "MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD",
                "MISSION_TOOLKIT_SUPERVISOR_DB_NAME"):
        monkeypatch.delenv(key, raising=False)

    url = "/api/supervisor/test-character-inventory-v2"
    client = TestClient(app)
    params = {"charid": 7, "location": 1, "cursor": 0, "limit": 100}
    assert client.get(url, params=params).status_code == 403
    assert client.get(url, params=params,
                      headers={"Authorization": "Bearer wrong"}).status_code == 403

    auth = {"Authorization": "Bearer " + "s" * 40}
    denied = client.get(url, params={**params, "charid": 8}, headers=auth)
    assert denied.status_code == 400
    assert "not approved" in denied.json()["detail"]

    approved_unavailable = client.get(url, params=params, headers=auth)
    assert approved_unavailable.status_code == 200
    data = approved_unavailable.json()
    assert data["status"] == "UNAVAILABLE" and data["complete"] is False
    assert data["items"] == [] and data["total_rows"] is None
    assert data["execution_enabled"] is False
    for overrides in ({"location": 9}, {"cursor": -1}, {"limit": 101}):
        response = client.get(url, params={**params, **overrides}, headers=auth)
        assert response.status_code == 400
