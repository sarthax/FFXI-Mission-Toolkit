"""Shared logical contract for FFXI server-source adapters.

Adapters describe physical source layouts without leaking those layouts into the
canonical Workbench model. They do not parse or migrate data by themselves.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TableShape:
    logical_name: str
    source_file: str
    physical_table: str
    aliases: tuple[str, ...] = ()
    required_columns: tuple[str, ...] = ()
    optional_columns: tuple[str, ...] = ()
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
