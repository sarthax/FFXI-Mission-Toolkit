"""Character Editor service over a detected DSP/Topaz/LSB live schema."""
from __future__ import annotations

from typing import Any

from .adapters import compare_schema
from .adapters.inventory import inspect_inventory_contract
from .categories import build_tab_manifest
from .inventory import inventory_summary
from .inventory_slots import CAPACITY_COLUMNS, CONTAINERS, CONTAINER_LABELS
from .item_catalog import ItemCatalogService
from .item_transactions import apply_item_injection, build_item_injection_plan
from .scalar_transactions import apply_scalar_edit, build_scalar_edit_plan, editable_columns
from .schema import CharacterSchema, discover_character_schema
from .session_state import detect_online_state


class CharacterEditorService:
    def __init__(self, connection, *, adapter_family: str = "unknown", adapter_confidence: str = "unknown"):
        self.connection = connection
        self.schema: CharacterSchema = discover_character_schema(connection)
        self.adapter_family = str(adapter_family or "unknown")
        self.adapter_confidence = str(adapter_confidence or "unknown")

    @staticmethod
    def _dict_rows(cursor) -> list[dict[str, Any]]:
        names = [str(d[0]) for d in cursor.description or ()]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def _chars_table(self):
        table = self.schema.table("chars")
        if table is None:
            raise RuntimeError("Connected database has no recognized chars table")
        return table

    def refresh_schema(self) -> CharacterSchema:
        self.schema = discover_character_schema(self.connection)
        return self.schema

    def search_characters(self, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        table = self._chars_table()
        cols = table.column_names
        id_col = "charid" if "charid" in cols else ("char_id" if "char_id" in cols else None)
        name_col = "charname" if "charname" in cols else ("name" if "name" in cols else None)
        if not id_col or not name_col:
            raise RuntimeError("chars table is missing a recognized character id/name column")

        optional = [c for c in ("accid", "gmlevel", "pos_zone", "nation", "mjob", "sjob", "lastonline") if c in cols]
        selected = [id_col, name_col, *optional]
        sql = "SELECT " + ", ".join(f"`{c}`" for c in selected) + " FROM `chars`"
        params: list[Any] = []
        q = (query or "").strip()
        if q:
            if q.isdigit():
                sql += f" WHERE `{id_col}` = %s OR `{name_col}` LIKE %s"
                params.extend([int(q), f"%{q}%"])
            else:
                sql += f" WHERE `{name_col}` LIKE %s"
                params.append(f"%{q}%")
        sql += f" ORDER BY `{name_col}` LIMIT %s"
        params.append(max(1, min(int(limit), 500)))
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql, tuple(params))
            return self._dict_rows(cursor)
        finally:
            cursor.close()

    def _identity(self, char_id: int) -> dict[str, Any] | None:
        table = self._chars_table()
        cols = table.column_names
        id_col = "charid" if "charid" in cols else "char_id"
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM `chars` WHERE `{id_col}` = %s LIMIT 1", (int(char_id),))
            rows = self._dict_rows(cursor)
            return rows[0] if rows else None
        finally:
            cursor.close()

    def character_exists(self, char_id: int) -> bool:
        return self._identity(char_id) is not None

    def session_state(self, char_id: int) -> dict[str, Any]:
        return detect_online_state(self.connection, self.schema, char_id).as_dict()

    def inventory_contract(self) -> dict[str, Any]:
        return inspect_inventory_contract(self.schema, self.adapter_family).as_dict()

    def tab_manifest(self) -> list[dict[str, Any]]:
        inventory = inventory_summary(self.schema, self.adapter_family)
        return build_tab_manifest(self.schema, inventory)

    def editable_fields(self, table_name: str) -> list[dict[str, Any]]:
        return editable_columns(self.schema, table_name)

    def preview_scalar_edit(self, char_id: int, table_name: str, *, selector: dict[str, Any] | None = None,
                            changes: dict[str, Any] | None = None) -> dict[str, Any]:
        return build_scalar_edit_plan(self.connection, char_id=char_id, table_name=table_name, selector=selector,
                                      changes=changes, adapter_family=self.adapter_family).as_dict()

    def apply_scalar_edit_request(self, char_id: int, table_name: str, *, selector: dict[str, Any] | None = None,
                                  changes: dict[str, Any] | None = None, approved: bool = False) -> dict[str, Any]:
        plan = build_scalar_edit_plan(self.connection, char_id=char_id, table_name=table_name, selector=selector,
                                      changes=changes, adapter_family=self.adapter_family)
        return apply_scalar_edit(self.connection, plan, approved=approved)

    def search_items(self, query: str = "", *, limit: int = 100, client_snapshot_id: str | None = None) -> list[dict[str, Any]]:
        catalog = ItemCatalogService(self.connection, client_snapshot_id=client_snapshot_id)
        return [record.as_dict() for record in catalog.search(query, limit=limit)]

    def get_item(self, item_id: int, *, client_snapshot_id: str | None = None) -> dict[str, Any] | None:
        record = ItemCatalogService(self.connection, client_snapshot_id=client_snapshot_id).get(item_id)
        return record.as_dict() if record else None

    def preview_add_item(self, char_id: int, item_id: int, *, quantity: int = 1, location: int = 0,
                         client_snapshot_id: str | None = None) -> dict[str, Any]:
        plan = build_item_injection_plan(self.connection, char_id=char_id, item_id=item_id, quantity=quantity,
                                         location=location, adapter_family=self.adapter_family,
                                         client_snapshot_id=client_snapshot_id)
        return plan.as_dict()

    def add_item(self, char_id: int, item_id: int, *, quantity: int = 1, location: int = 0,
                 client_snapshot_id: str | None = None, approved: bool = False) -> dict[str, Any]:
        plan = build_item_injection_plan(self.connection, char_id=char_id, item_id=item_id, quantity=quantity,
                                         location=location, adapter_family=self.adapter_family,
                                         client_snapshot_id=client_snapshot_id)
        return apply_item_injection(self.connection, plan, approved=approved)

    def load_table(self, char_id: int, table_name: str, limit: int = 5000) -> list[dict[str, Any]]:
        table = self.schema.table(table_name)
        if table is None:
            raise KeyError(f"Unknown or non-character table: {table_name}")
        if table_name == "chars":
            identity = self._identity(char_id)
            return [identity] if identity else []
        if table.character_key is None:
            return []
        safe_limit = max(1, min(int(limit), 20000))
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM `{table_name}` WHERE `{table.character_key}` = %s LIMIT %s",
                           (int(char_id), safe_limit))
            return self._dict_rows(cursor)
        finally:
            cursor.close()

    def inventory_containers(self, char_id: int) -> list[dict[str, Any]]:
        rows = self.load_table(char_id, "char_inventory")
        by_location: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            location = int(row.get("location") or 0)
            by_location.setdefault(location, []).append(row)
        storage_row: dict[str, Any] = {}
        try:
            storage_rows = self.load_table(char_id, "char_storage", limit=1)
            if storage_rows:
                storage_row = storage_rows[0]
        except (KeyError, RuntimeError):
            storage_row = {}
        locations = set(CONTAINERS)
        locations.update(by_location)
        out = []
        for location in sorted(locations):
            column = CAPACITY_COLUMNS.get(location)
            capacity = None
            supported = True
            if column:
                if column in storage_row:
                    capacity = max(0, int(storage_row.get(column) or 0))
                else:
                    supported = False
            elif location == 2:
                supported = True
            elif location == 3:
                supported = bool(by_location.get(location))
            container_rows = sorted(by_location.get(location, []), key=lambda r: int(r.get("slot") or 0))
            if not supported and not container_rows:
                continue
            out.append({
                "location": location,
                "name": CONTAINERS.get(location, f"container_{location}"),
                "label": CONTAINER_LABELS.get(location, f"Container {location}"),
                "capacity": capacity,
                "count": len(container_rows),
                "rows": container_rows,
                "capacity_source": column or ("furnishing_runtime" if location == 2 else "runtime_or_unknown"),
            })
        return out

    def load_character(self, char_id: int, include_rows: bool = False) -> dict[str, Any]:
        identity = self._identity(char_id)
        if identity is None:
            raise KeyError(f"Character {char_id} was not found")
        sections: dict[str, Any] = {}
        for capability, table_names in sorted(self.schema.capabilities.items()):
            section = {"tables": table_names, "available": bool(table_names)}
            if include_rows:
                section["rows"] = {table_name: self.load_table(char_id, table_name) for table_name in table_names}
            sections[capability] = section
        inventory = inventory_summary(self.schema, self.adapter_family)
        scalar_tables = {
            name: self.editable_fields(name)
            for name in (
                "chars", "char_profile", "char_look", "char_style", "char_jobs", "char_exp", "char_stats",
                "char_skills", "char_points", "char_merit", "char_job_points", "char_unlocks", "char_vars",
            )
            if self.schema.table(name) is not None
        }
        return {
            "character": identity,
            "adapter": {"family": self.adapter_family, "confidence": self.adapter_confidence},
            "online_state": self.session_state(char_id),
            "inventory_contract": self.inventory_contract(),
            "tabs": build_tab_manifest(self.schema, inventory),
            "sections": sections,
            "packed_fields": dict(self.schema.packed_fields),
            "schema": self.schema.summary(),
            "lineage_comparison": compare_schema(self.schema, self.adapter_family),
            "inventory": inventory,
            "scalar_editors": scalar_tables,
            "write_enabled": True,
            "write_capabilities": ["inventory_basic_offline", "scalar_character_offline"],
        }

    def capability_manifest(self) -> dict[str, Any]:
        inventory = inventory_summary(self.schema, self.adapter_family)
        return {
            "adapter": {"family": self.adapter_family, "confidence": self.adapter_confidence},
            "schema": self.schema.summary(),
            "lineage_comparison": compare_schema(self.schema, self.adapter_family),
            "inventory_contract": self.inventory_contract(),
            "tabs": build_tab_manifest(self.schema, inventory),
            "inventory": inventory,
            "write_enabled": True,
            "write_capabilities": ["inventory_basic_offline", "scalar_character_offline"],
        }
