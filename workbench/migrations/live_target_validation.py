"""Read-only validation of normalized server records against a live target database.

This layer is intentionally adapter-aware and DB-API based:
- ServerAdapter owns physical table/column interpretation.
- The validator issues SELECT queries only.
- Expected records are LogicalRecord instances produced by an adapter/source analyzer.
- Live rows are normalized through the target adapter before comparison.
- Credentials/connections are never persisted in Workbench records.

The generic validator does not replace specialized health checks such as mob_groups
content-duplication analysis; those remain additional validators.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Iterable, Protocol

from workbench.adapters.servers.base import LogicalRecord, ServerAdapter
from workbench.adapters.servers.logical import compare_records

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class LiveRecordValidation:
    logical_type: str
    identity: tuple[tuple[str, Any], ...]
    status: str
    confidence: str
    target_table: str | None
    matched_rows: int
    differences: tuple[dict[str, Any], ...] = ()
    notes: tuple[str, ...] = ()


class TargetReader(Protocol):
    def columns(self, table: str) -> tuple[str, ...]: ...
    def select_by_identity(
        self,
        table: str,
        identity: tuple[tuple[str, Any], ...],
    ) -> list[dict[str, Any]]: ...


class DBAPITargetReader:
    """Minimal read-only DB-API reader."""

    def __init__(self, connection, *, paramstyle: str = "qmark"):
        if paramstyle not in {"qmark", "format"}:
            raise ValueError("paramstyle must be qmark or format")
        self.connection = connection
        self.paramstyle = paramstyle

    @staticmethod
    def _quote(identifier: str) -> str:
        if not _IDENT_RE.fullmatch(identifier):
            raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
        return chr(96) + identifier + chr(96)

    def columns(self, table: str) -> tuple[str, ...]:
        qtable=self._quote(table)
        cursor=self.connection.cursor()
        try:
            cursor.execute(f"SELECT * FROM {qtable} WHERE 1=0")
            return tuple(str(col[0]) for col in (cursor.description or ()))
        finally:
            cursor.close()

    def select_by_identity(
        self,
        table: str,
        identity: tuple[tuple[str, Any], ...],
    ) -> list[dict[str, Any]]:
        if not identity:
            raise ValueError("identity must not be empty")
        qtable=self._quote(table)
        placeholder="?" if self.paramstyle=="qmark" else "%s"
        clauses=[]
        values=[]
        for column,value in identity:
            qcol=self._quote(column)
            if value is None:
                clauses.append(f"{qcol} IS NULL")
            else:
                clauses.append(f"{qcol} = {placeholder}")
                values.append(value)
        cursor=self.connection.cursor()
        try:
            cursor.execute(
                f"SELECT * FROM {qtable} WHERE {' AND '.join(clauses)}",
                tuple(values),
            )
            columns=tuple(str(col[0]) for col in (cursor.description or ()))
            return [dict(zip(columns,row)) for row in cursor.fetchall()]
        finally:
            cursor.close()


def _physical_identity(
    adapter: ServerAdapter,
    logical_type: str,
    identity: tuple[tuple[str, Any], ...],
    live_columns: tuple[str, ...],
) -> tuple[tuple[str, Any], ...] | None:
    shape=adapter.resolve_table(logical_type)
    if shape is None:
        return None
    available={name.lower():name for name in live_columns}
    mappings={m.logical_name:m for m in shape.field_mappings}
    out=[]
    for logical_name,value in identity:
        mapping=mappings.get(logical_name)
        if mapping is None:
            return None
        selected=None
        for physical in mapping.physical_names:
            if physical.lower() in available:
                selected=available[physical.lower()]
                break
        if selected is None:
            return None
        out.append((selected,value))
    return tuple(out)


def validate_live_records(
    adapter: ServerAdapter,
    reader: TargetReader,
    logical_type: str,
    expected_records: Iterable[LogicalRecord],
    *,
    target_snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Validate expected normalized records against the current live target state."""
    shape=adapter.resolve_table(logical_type)
    if shape is None:
        return {
            "schema":1,
            "kind":"WORKBENCH_LIVE_TARGET_VALIDATION",
            "logical_type":logical_type,
            "target_snapshot_id":target_snapshot_id,
            "status":"UNKNOWN",
            "results":[],
            "notes":[f"Target adapter does not define logical table {logical_type!r}."],
        }

    table=shape.physical_table
    try:
        columns=reader.columns(table)
    except Exception as exc:
        return {
            "schema":1,
            "kind":"WORKBENCH_LIVE_TARGET_VALIDATION",
            "logical_type":logical_type,
            "target_snapshot_id":target_snapshot_id,
            "status":"FAILED",
            "results":[],
            "notes":[f"Could not inspect live target table {table}: {type(exc).__name__}: {exc}"],
        }

    results=[]
    for expected in expected_records:
        if expected.logical_type != logical_type:
            raise ValueError("Mixed logical record types are not supported")
        physical_identity=_physical_identity(adapter,logical_type,expected.identity,columns)
        if physical_identity is None:
            results.append(LiveRecordValidation(
                logical_type,expected.identity,"UNKNOWN","UNKNOWN",table,0,
                notes=("Target schema cannot map every logical identity field to a live physical column.",),
            ))
            continue
        try:
            rows=reader.select_by_identity(table,physical_identity)
        except Exception as exc:
            results.append(LiveRecordValidation(
                logical_type,expected.identity,"FAILED","VERIFIED",table,0,
                notes=(f"Live SELECT failed: {type(exc).__name__}: {exc}",),
            ))
            continue
        if not rows:
            results.append(LiveRecordValidation(
                logical_type,expected.identity,"MISSING","VERIFIED",table,0,
                notes=("No live target row exists at the expected logical identity.",),
            ))
            continue
        if len(rows)>1:
            results.append(LiveRecordValidation(
                logical_type,expected.identity,"AMBIGUOUS","VERIFIED",table,len(rows),
                notes=("Multiple live target rows resolve to the same logical identity.",),
            ))
            continue

        live=adapter.normalize_row(logical_type,rows[0])
        comparison=compare_records(expected,live)
        if comparison.status=="EQUIVALENT":
            results.append(LiveRecordValidation(
                logical_type,expected.identity,"VERIFIED","VERIFIED",table,1,
                notes=("Live target row matches the expected normalized record.",),
            ))
        else:
            diffs=tuple({
                "field":d.field,
                "source_value":d.source_value,
                "target_value":d.target_value,
                "status":d.status,
            } for d in comparison.differences)
            results.append(LiveRecordValidation(
                logical_type,expected.identity,"CONTRADICTED","VERIFIED",table,1,diffs,
                ("Live target row exists but differs after adapter normalization.",),
            ))

    serialized=[asdict(row) for row in results]
    statuses={row.status for row in results}
    if "FAILED" in statuses:
        overall="FAILED"
    elif statuses & {"CONTRADICTED","AMBIGUOUS"}:
        overall="CONTRADICTED"
    elif "MISSING" in statuses:
        overall="MISSING"
    elif "UNKNOWN" in statuses:
        overall="UNKNOWN"
    elif results and statuses=={"VERIFIED"}:
        overall="VERIFIED"
    else:
        overall="UNKNOWN"

    return {
        "schema":1,
        "kind":"WORKBENCH_LIVE_TARGET_VALIDATION",
        "logical_type":logical_type,
        "target_table":table,
        "target_snapshot_id":target_snapshot_id,
        "status":overall,
        "results":serialized,
        "notes":[
            "Read-only validation against current live database state.",
            "A successful result validates normalized database representation only; runtime behavior remains a separate validation dimension.",
        ],
    }
