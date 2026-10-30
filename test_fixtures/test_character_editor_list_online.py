"""Online/offline state appears on character list rows (batch form of the lock check)."""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from workbench.editors.character.service import CharacterEditorService
from workbench.editors.character.session_state import detect_online_state, detect_online_states


class _Conn:
    """sqlite3 stand-in that accepts MySQL-style %s placeholders."""
    def __init__(self, db): self.db = db
    def cursor(self):
        cur = self.db.cursor()
        real = cur.execute
        class C:
            def execute(s, sql, params=()): real(sql.replace("%s", "?"), params); return s
            def __getattr__(s, n): return getattr(cur, n)
        return C()


def _schema(session_cols=("charid",)):
    tables = {"chars": SimpleNamespace(column_names=["charid", "charname", "pos_zone"])}
    if session_cols is not None:
        tables["accounts_sessions"] = SimpleNamespace(column_names=list(session_cols))
    return SimpleNamespace(table=tables.get)


def _db():
    db = sqlite3.connect(":memory:")
    db.executescript("""CREATE TABLE chars(charid INT, charname TEXT, pos_zone INT);
        INSERT INTO chars VALUES (1,'Alpha',230),(2,'Bravo',231),(3,'Carol',232);
        CREATE TABLE accounts_sessions(charid INT, accid INT);
        INSERT INTO accounts_sessions VALUES (2,9),(2,9);""")
    return _Conn(db)


def test_batch_matches_single_lookup_and_dedupes_sessions():
    conn, schema = _db(), _schema()
    assert detect_online_states(conn, schema, [1, 2, 3]) == {1: False, 2: True, 3: False}
    for cid, state in detect_online_states(conn, schema, [1, 2]).items():
        assert detect_online_state(conn, schema, cid).online is state


def test_undetectable_session_table_is_unknown_not_offline():
    assert detect_online_states(_db(), _schema(None), [1, 2]) == {1: None, 2: None}
    assert detect_online_states(_db(), _schema(("accid",)), [1]) == {1: None}
    assert detect_online_states(_db(), _schema(), []) == {}


def test_search_characters_rows_carry_online_flag():
    service = object.__new__(CharacterEditorService)
    service.connection, service.schema = _db(), _schema()
    rows = {r["charid"]: r for r in service.search_characters("")}
    assert [rows[i]["online"] for i in (1, 2, 3)] == [False, True, False]
    assert rows[1]["pos_zone"] == 230
