import pytest

from workbench.server_admin.voidwatch import edits as E


class FakeConn:
    def __init__(self, rows):
        self.rows = rows


def _patch(monkeypatch, rows_by_sql):
    def fake(conn, sql, params=()):
        for k, v in rows_by_sql.items():
            if k in sql:
                return v
        return []
    monkeypatch.setattr(E.R, "_rows", fake)


def test_rejects_unlisted_column_and_table(monkeypatch):
    _patch(monkeypatch, {})
    with pytest.raises(E.EditError):
        E.plan(None, "mob_groups", 1, {"dropid": 5})
    with pytest.raises(E.EditError):
        E.plan(None, "item_basic", 1, {"name": "x"})


def test_range_and_level_order(monkeypatch):
    _patch(monkeypatch, {"FROM `mob_groups`": [(80,)], "SELECT minLevel,maxLevel": [(80, 85)]})
    with pytest.raises(E.EditError):
        E.plan(None, "mob_groups", 1, {"minLevel": 999})
    with pytest.raises(E.EditError):
        E.plan(None, "mob_groups", 1, {"minLevel": 90})


def test_zero_position_refused(monkeypatch):
    _patch(monkeypatch, {"FROM `mob_spawn_points`": [(1.0,)], "SELECT pos_x,pos_y,pos_z": [(1.0, 2.0, 3.0)]})
    with pytest.raises(E.EditError):
        E.plan(None, "mob_spawn_points", 7, {"pos_x": 0, "pos_y": 0, "pos_z": 0})


def test_plan_builds_update(monkeypatch):
    _patch(monkeypatch, {"FROM `mob_groups`": [(45408,)], "SELECT minLevel,maxLevel": [(80, 85)]})
    p = E.plan(None, "mob_groups", 11004, {"HP": "50000"})
    assert p["sql"] == "UPDATE `mob_groups` SET `HP`=50000 WHERE `groupid`=11004;" and p["before"] == {"HP": 45408}
