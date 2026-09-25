"""Shared logical contract for FFXI server-source adapters.

Adapters describe physical source layouts without leaking those layouts into the
canonical Workbench model. They do not parse or migrate data by themselves.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from pathlib import Path


@dataclass(frozen=True)
class FieldMapping:
    logical_name: str
    physical_names: tuple[str, ...]
    required: bool = False


@dataclass(frozen=True)
class LogicalRecord:
    logical_type: str
    identity: tuple[tuple[str, Any], ...]
    fields: dict[str, Any]
    source_family: str
    source_table: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TableShape:
    logical_name: str
    source_file: str
    physical_table: str
    aliases: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = ()
    optional_columns: tuple[str, ...] = ()
    field_mappings: tuple[FieldMapping, ...] = ()
    identity_fields: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchemaProfile:
    profile_id: str
    family: str
    tables: dict[str, TableShape]
    version_hint: str | None = None
    notes: tuple[str, ...] = ()

    def table(self, logical_name: str) -> TableShape | None:
        return self.tables.get(logical_name)


@dataclass(frozen=True)
class AdapterProbe:
    adapter_id: str
    family: str
    root: str
    compatible: bool
    missing_paths: tuple[str, ...] = ()
    evidence_paths: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class ServerAdapter(ABC):
    """Source-specific interpretation behind a source-neutral interface."""

    adapter_id: str
    family: str

    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    @abstractmethod
    def schema_profile(self) -> SchemaProfile:
        raise NotImplementedError

    def resolve_table(self, logical_name: str) -> TableShape | None:
        return self.schema_profile.table(logical_name)

    def source_path(self, logical_name: str) -> Path | None:
        shape = self.resolve_table(logical_name)
        return self.root / "sql" / shape.source_file if shape else None

    def normalize_row(self, logical_name: str, row: Mapping[str, Any]) -> LogicalRecord:
        shape = self.resolve_table(logical_name)
        if shape is None:
            raise KeyError(f"Unknown logical table: {logical_name}")
        lowered = {str(key).lower(): value for key, value in row.items()}
        fields: dict[str, Any] = {}
        missing: list[str] = []
        for mapping in shape.field_mappings:
            value = None
            found = False
            for physical in mapping.physical_names:
                key = physical.lower()
                if key in lowered:
                    value = lowered[key]
                    found = True
                    break
            fields[mapping.logical_name] = value
            if mapping.required and not found:
                missing.append(mapping.logical_name)
        identity = tuple((name, fields.get(name)) for name in shape.identity_fields)
        notes = list(shape.notes)
        if missing:
            notes.append("Missing required physical fields: " + ", ".join(sorted(missing)))
        return LogicalRecord(
            logical_type=logical_name,
            identity=identity,
            fields=fields,
            source_family=self.family,
            source_table=shape.physical_table,
            notes=tuple(notes),
        )

    def normalize_rows(
        self,
        logical_name: str,
        rows: Sequence[Mapping[str, Any]],
        related_records: Mapping[str, Sequence[LogicalRecord]] | None = None,
    ) -> list[LogicalRecord]:
        return [self.normalize_row(logical_name, row) for row in rows]

    def probe(self) -> AdapterProbe:
        required = [self.root / "sql"]
        evidence = [p for p in required if p.exists()]
        missing = [str(p) for p in required if not p.exists()]
        return AdapterProbe(
            adapter_id=self.adapter_id,
            family=self.family,
            root=str(self.root),
            compatible=not missing,
            missing_paths=tuple(missing),
            evidence_paths=tuple(str(p) for p in evidence),
        )
