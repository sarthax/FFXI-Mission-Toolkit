"""Shared synthetic DB/service fakes for Auction House reward preview + execute tests.

Only models the exact read-only character-query surface those tests use.
Unexpected SQL fails closed, and each service owns a separate mutable roster.
No live DB connection, credentials, or write-capable cursor are provided.
"""

from types import SimpleNamespace


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, sql, params=()):
        if sql.startswith("DESCRIBE `chars`"):
            self.rows = [("charid",), ("charname",)]
        elif "FROM `chars`" in sql:
            if " IN (" in sql:
                wanted = {int(value) for value in params}
                self.rows = [row for row in self.connection.characters if row[0] in wanted]
            else:
                limit = int(params[0]) if params else 5001
                self.rows = list(self.connection.characters)[:limit]
        else:
            raise AssertionError(sql)

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class Connection:
    def __init__(self, characters):
        self.characters = list(characters)

    def cursor(self):
        return Cursor(self)


class Service:
    def __init__(self, characters=((1, "Alpha"), (2, "Beta"))):
        self.connection = Connection(characters)
        self.schema = SimpleNamespace(family_hint="legacy-compatible")

    def item_snapshot(self, item_id):
        if int(item_id) != 100:
            return None
        return {"item_id": 100, "name": "Potion", "stack_size": 12}


