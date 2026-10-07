"""Connect to the live server DB with item table names mapped to what that server actually calls them.

The Item Editor is written against Topaz's `item_equipment`; DSP's equivalent is `item_armor` (same columns).
Every statement is rewritten to the name the connected database really has, so one editor serves both.
"""
from __future__ import annotations

import re

from workbench.devtools.spatial import active_zone_plot as zone_plot

_ALIASES = ("item_equipment", "item_armor")
_resolved: dict[str, str] = {}


class _Cursor:
    def __init__(self, cursor, table):
        self._c, self._t = cursor, table

    def _sql(self, sql):
        return re.sub(r"\bitem_equipment\b", self._t, sql) if self._t != "item_equipment" and isinstance(sql, str) else sql

    def execute(self, sql, *args, **kw):
        return self._c.execute(self._sql(sql), *args, **kw)

    def executemany(self, sql, *args, **kw):
        return self._c.executemany(self._sql(sql), *args, **kw)

    def __getattr__(self, name):
        return getattr(self._c, name)

    def __iter__(self):
        return iter(self._c)


class _Connection:
    def __init__(self, conn, table):
        self._conn, self._t = conn, table

    def cursor(self, *args, **kw):
        return _Cursor(self._conn.cursor(*args, **kw), self._t)

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._conn.close()


def is_dsp(server=None) -> bool:
    """True when the connected server is DSP (its armor table is item_armor, Topaz's is item_equipment)."""
    return item_db(server)._t == "item_armor"


def item_db(server=None):
    conn = zone_plot._db(server) if server else zone_plot._db()
    key = str(conn.database)
    table = _resolved.get(key)
    if table is None:
        cur = conn.cursor()
        try:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name IN ('item_equipment','item_armor')")
            found = {r[0].lower() for r in cur.fetchall()}
        finally:
            cur.close()
        table = "item_equipment" if "item_equipment" in found or not found else "item_armor"
        _resolved[key] = table
    return _Connection(conn, table)
