"""Guarded scalar-field editing for Character Editor.

Only verified row-backed character state is writable here. Packed/BLOB state is intentionally
excluded until lineage-specific codecs exist.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from .audit import attach_committed_audit
from .schema import CharacterSchema, ColumnInfo, discover_character_schema
from .session_state import detect_online_state

_ALLOWED_COLUMNS: dict[str, set[str] | None] = {
    "chars": {
        "nation", "pos_zone", "pos_prevzone", "pos_prevzonelineid", "pos_rot", "pos_x", "pos_y", "pos_z",
        "moghouse", "boundary", "home_zone", "home_rot", "home_x", "home_y", "home_z", "playtime", "gmlevel",
        "languages", "mentor", "job_master", "campaign_allegiance", "isstylelocked", "settings", "chatfilters_1",
        "chatfilters_2", "moghancement",
    },
    "char_profile": None,
    "char_look": None,
    "char_style": None,
    "char_jobs": None,
    "char_exp": None,
    "char_stats": {
        "hp", "mp", "mhflag", "mjob", "sjob", "death", "2h", "title", "zoning", "mlvl", "slvl",
        "pet_id", "pet_type", "pet_level", "pet_hp", "pet_mp",
    },
    "char_skills": {"value", "rank"},
    "char_points": None,
    "char_merit": {"upgrades"},
    "char_job_points": None,
    "char_unlocks": {
        "outpost_sandy", "outpost_bastok", "outpost_windy", "mog_locker", "runic_portal", "maw",
        "campaign_sandy", "campaign_bastok", "campaign_windy", "traverser_claimed",
    },
    "char_vars": {"value", "expiry"},
}
_ALLOWED_SELECTORS = {
    "char_skills": {"skillid"},
    "char_merit": {"meritid"},
    "char_job_points": {"jobid"},
    "char_vars": {"varname"},
}
_KEY_COLUMNS = {"charid", "char_id", "character_id", "skillid", "meritid", "jobid", "varname"}
_VERIFIED_FAMILIES = {"dsp", "topaz", "lsb"}


@dataclass(frozen=True)
class ScalarIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class ScalarEditPlan:
    char_id: int
    table: str
    selector: dict[str, Any]
    changes: dict[str, Any]
    before: dict[str, Any] | None
    online: bool | None
    adapter_family: str
    issues: list[ScalarIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.before is not None and bool(self.changes) and not any(i.blocking for i in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "char_id": self.char_id,
            "table": self.table,
            "selector": dict(self.selector),
            "changes": dict(self.changes),
            "before": dict(self.before) if self.before else None,
            "online": self.online,
            "adapter_family": self.adapter_family,
            "issues": [asdict(i) for i in self.issues],
            "ready": self.ready,
        }


def editable_columns(schema: CharacterSchema, table_name: str) -> list[dict[str, Any]]:
    table = schema.table(table_name)
    if table is None or table_name not in _ALLOWED_COLUMNS:
        return []
    allow = _ALLOWED_COLUMNS[table_name]
    out = []
    for column in table.columns:
        if column.name in _KEY_COLUMNS or column.is_binary:
            continue
        if allow is not None and column.name not in allow:
            continue
        out.append({
            "name": column.name,
            "sql_type": column.sql_type,
            "nullable": column.nullable,
            "default": column.default,
        })
    return out


def _bounds(column: ColumnInfo) -> tuple[int | None, int | None]:
    t = column.sql_type.lower()
    match = re.match(r"(?:tinyint|smallint|mediumint|int|integer|bigint)(?:\(\d+\))?", t)
    if not match:
        return None, None
    bits = 8 if t.startswith("tinyint") else 16 if t.startswith("smallint") else 24 if t.startswith("mediumint") else 64 if t.startswith("bigint") else 32
    unsigned = "unsigned" in t
    return (0, (1 << bits) - 1) if unsigned else (-(1 << (bits - 1)), (1 << (bits - 1)) - 1)


def _coerce(column: ColumnInfo, value: Any) -> Any:
    if value is None:
        if column.nullable:
            return None
        raise ValueError(f"{column.name} cannot be null")
    t = column.sql_type.lower()
    if any(t.startswith(prefix) for prefix in ("tinyint", "smallint", "mediumint", "int", "integer", "bigint")):
        result = int(value)
        low, high = _bounds(column)
        if low is not None and not (low <= result <= high):
            raise ValueError(f"{column.name} must be between {low} and {high}")
        return result
    if any(t.startswith(prefix) for prefix in ("float", "double", "decimal", "numeric")):
        return float(value)
    if any(token in t for token in ("char", "text")):
        result = str(value)
        match = re.search(r"(?:var)?char\((\d+)\)", t)
        if match and len(result) > int(match.group(1)):
            raise ValueError(f"{column.name} exceeds maximum length {match.group(1)}")
        return result
    raise ValueError(f"{column.name} uses unsupported scalar type {column.sql_type}")


def _row(connection, schema: CharacterSchema, char_id: int, table_name: str, selector: dict[str, Any]) -> dict[str, Any] | None:
    table = schema.table(table_name)
    if table is None or table.character_key is None:
        return None
    allowed_selectors = _ALLOWED_SELECTORS.get(table_name, set())
    unknown = set(selector) - allowed_selectors
    if unknown:
        raise ValueError(f"Unsupported selector(s) for {table_name}: {', '.join(sorted(unknown))}")
    if allowed_selectors and set(selector) != allowed_selectors:
        missing = allowed_selectors - set(selector)
        raise ValueError(f"Missing selector(s) for {table_name}: {', '.join(sorted(missing))}")
    clauses = [f"`{table.character_key}` = %s"]
    params: list[Any] = [int(char_id)]
    for key, value in selector.items():
        if key not in table.column_names:
            raise ValueError(f"Unknown selector column {table_name}.{key}")
        clauses.append(f"`{key}` = %s")
        params.append(value)
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT * FROM `{table_name}` WHERE {' AND '.join(clauses)} LIMIT 1", tuple(params))
        names = [str(d[0]) for d in cursor.description or ()]
        row = cursor.fetchone()
        return dict(zip(names, row)) if row else None
    finally:
        cursor.close()


def build_scalar_edit_plan(connection, *, char_id: int, table_name: str, selector: dict[str, Any] | None = None,
                           changes: dict[str, Any] | None = None, adapter_family: str = "unknown") -> ScalarEditPlan:
    char_id = int(char_id)
    selector = dict(selector or {})
    requested = dict(changes or {})
    family = str(adapter_family or "unknown").lower()
    issues: list[ScalarIssue] = []
    schema = discover_character_schema(connection)
    table = schema.table(table_name)
    if family not in _VERIFIED_FAMILIES:
        issues.append(ScalarIssue("adapter_unverified", "A detected DSP/Topaz/LSB adapter is required for scalar writes."))
    if table is None:
        issues.append(ScalarIssue("table_missing", f"{table_name} is not present on the connected server."))
    if table_name not in _ALLOWED_COLUMNS:
        issues.append(ScalarIssue("table_not_enabled", f"{table_name} is not enabled for scalar editing."))

    online_state = detect_online_state(connection, schema, char_id)
    if online_state.online is True:
        issues.append(ScalarIssue("character_online", "Character is online; direct character writes are blocked."))
    elif online_state.online is None:
        issues.append(ScalarIssue("online_state_unknown", "Character online state could not be verified."))

    before = None
    normalized: dict[str, Any] = {}
    if table is not None and table_name in _ALLOWED_COLUMNS:
        try:
            before = _row(connection, schema, char_id, table_name, selector)
        except ValueError as exc:
            issues.append(ScalarIssue("invalid_selector", str(exc)))
        if before is None and not any(i.code == "invalid_selector" for i in issues):
            issues.append(ScalarIssue("row_missing", "Target character row does not exist."))
        columns = {c.name: c for c in table.columns}
        editable = {row["name"] for row in editable_columns(schema, table_name)}
        for name, value in requested.items():
            column = columns.get(name)
            if column is None:
                issues.append(ScalarIssue("unknown_column", f"Unknown column {table_name}.{name}."))
                continue
            if name not in editable:
                issues.append(ScalarIssue("column_not_editable", f"{table_name}.{name} is not enabled for scalar editing."))
                continue
            try:
                normalized[name] = _coerce(column, value)
            except (TypeError, ValueError) as exc:
                issues.append(ScalarIssue("invalid_value", str(exc)))

    return ScalarEditPlan(char_id, table_name, selector, normalized, before, online_state.online, family, issues)


def apply_scalar_edit(connection, plan: ScalarEditPlan, *, approved: bool = False) -> dict[str, Any]:
    if not approved:
        raise PermissionError("Explicit approval is required to apply character changes")
    if not plan.ready:
        raise RuntimeError("Scalar edit plan is not write-ready")
    try:
        if hasattr(connection, "start_transaction"):
            connection.start_transaction()
        else:
            cursor = connection.cursor()
            try:
                cursor.execute("START TRANSACTION")
            finally:
                cursor.close()
        schema = discover_character_schema(connection)
        state = detect_online_state(connection, schema, plan.char_id)
        if state.online is not False:
            raise RuntimeError("Character online state changed or cannot be verified")
        current = _row(connection, schema, plan.char_id, plan.table, plan.selector)
        if current != plan.before:
            raise RuntimeError("Character data changed since preview; rebuild the edit plan")
        table = schema.table(plan.table)
        if table is None or table.character_key is None:
            raise RuntimeError("Target table is no longer available")
        assignments = ", ".join(f"`{name}` = %s" for name in plan.changes)
        clauses = [f"`{table.character_key}` = %s"]
        params: list[Any] = list(plan.changes.values()) + [plan.char_id]
        for key, value in plan.selector.items():
            clauses.append(f"`{key}` = %s")
            params.append(value)
        cursor = connection.cursor()
        try:
            cursor.execute(f"UPDATE `{plan.table}` SET {assignments} WHERE {' AND '.join(clauses)} LIMIT 1", tuple(params))
            if getattr(cursor, "rowcount", 1) not in (0, 1):
                raise RuntimeError("Unexpected number of rows updated")
        finally:
            cursor.close()
        connection.commit()
        after = dict(plan.before or {})
        after.update(plan.changes)
        result = {
            "status": "committed",
            "char_id": plan.char_id,
            "table": plan.table,
            "selector": plan.selector,
            "changes": plan.changes,
            "before": plan.before,
            "after": after,
        }
        return attach_committed_audit(
            result,
            operation="scalar.update",
            char_id=plan.char_id,
            adapter_family=plan.adapter_family,
            target={"table": plan.table, "selector": dict(plan.selector)},
            before=plan.before,
            after=after,
            metadata={"changes": dict(plan.changes)},
            undo_supported=True,
        )
    except Exception:
        try:
            connection.rollback()
        finally:
            raise
