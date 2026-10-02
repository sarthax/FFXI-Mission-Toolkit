"""Server-backed item catalog with optional local-client DAT enrichment."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

try:
    from workbench.client.dat_adapter import ItemDatAdapter
except Exception:  # local client tooling may be unavailable on non-Windows hosts
    ItemDatAdapter = None

RARE_FLAG = 0x8000
EXCLUSIVE_FLAG = 0x4000


@dataclass(frozen=True)
class ItemCatalogRecord:
    item_id: int
    name: str
    flags: int
    stack_size: int
    item_type: int | None = None
    client_fields: dict[str, Any] | None = None

    @property
    def rare(self) -> bool:
        return bool(self.flags & RARE_FLAG)

    @property
    def exclusive(self) -> bool:
        return bool(self.flags & EXCLUSIVE_FLAG)

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["rare"] = self.rare
        out["exclusive"] = self.exclusive
        return out


class ItemCatalogService:
    def __init__(self, connection, *, client_snapshot_id: str | None = None):
        self.connection = connection
        self._columns = self._discover_columns()
        self._client = None
        if client_snapshot_id and ItemDatAdapter is not None:
            try:
                self._client = ItemDatAdapter(client_snapshot_id)
            except Exception:
                self._client = None

    def _discover_columns(self) -> dict[str, str]:
        cursor = self.connection.cursor()
        try:
            cursor.execute("DESCRIBE `item_basic`")
            names = {str(row[0]) for row in cursor.fetchall() or []}
        finally:
            cursor.close()

        def pick(*candidates: str, required: bool = True) -> str | None:
            for candidate in candidates:
                if candidate in names:
                    return candidate
            if required:
                raise RuntimeError(f"item_basic is missing expected column(s): {', '.join(candidates)}")
            return None

        return {
            "id": pick("itemid", "itemId", "item_id", "id"),
            "name": pick("name"),
            "flags": pick("flags"),
            "stack": pick("stackSize", "stack_size", "stack"),
            "type": pick("type", "item_type", required=False),
        }

    def _record_from_row(self, row: tuple[Any, ...]) -> ItemCatalogRecord:
        item_id, name, flags, stack_size, item_type = row
        client_fields = None
        if self._client is not None:
            try:
                client = self._client.read(int(item_id))
                client_fields = dict(client.fields) if client else None
            except Exception:
                client_fields = None
        return ItemCatalogRecord(
            item_id=int(item_id),
            name=str(name or ""),
            flags=int(flags or 0),
            stack_size=max(1, int(stack_size or 1)),
            item_type=None if item_type is None else int(item_type),
            client_fields=client_fields,
        )

    def _select(self) -> str:
        c = self._columns
        type_expr = f"`{c['type']}`" if c["type"] else "NULL"
        return f"`{c['id']}`, `{c['name']}`, `{c['flags']}`, `{c['stack']}`, {type_expr}"

    def get(self, item_id: int) -> ItemCatalogRecord | None:
        c = self._columns
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"SELECT {self._select()} FROM `item_basic` WHERE `{c['id']}` = %s LIMIT 1",
                (int(item_id),),
            )
            row = cursor.fetchone()
            return self._record_from_row(row) if row else None
        finally:
            cursor.close()

    def search(self, query: str = "", *, limit: int = 100) -> list[ItemCatalogRecord]:
        c = self._columns
        safe_limit = max(1, min(int(limit), 500))
        q = str(query or "").strip()
        sql = f"SELECT {self._select()} FROM `item_basic`"
        params: list[Any] = []
        if q:
            if q.isdigit():
                sql += f" WHERE `{c['id']}` = %s OR `{c['name']}` LIKE %s"
                params.extend([int(q), f"%{q}%"])
            else:
                sql += f" WHERE `{c['name']}` LIKE %s"
                params.append(f"%{q}%")
        sql += f" ORDER BY `{c['name']}` LIMIT %s"
        params.append(safe_limit)
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            return [self._record_from_row(row) for row in cursor.fetchall() or []]
        finally:
            cursor.close()
