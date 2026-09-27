"""Source-neutral comparison of logical records emitted by server adapters."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .base import LogicalRecord

@dataclass(frozen=True)
class LogicalDifference:
    field: str
    source_value: Any
    target_value: Any
    status: str

@dataclass(frozen=True)
class LogicalComparison:
    logical_type: str
    identity: tuple[tuple[str, Any], ...]
    status: str
    differences: tuple[LogicalDifference, ...]

def compare_records(source: LogicalRecord, target: LogicalRecord) -> LogicalComparison:
    if source.logical_type != target.logical_type:
        raise ValueError("Logical record types differ")
    if source.identity != target.identity:
        raise ValueError("Logical record identities differ")
    fields=sorted(set(source.fields) | set(target.fields))
    diffs=[]
    for field in fields:
        sv=source.fields.get(field)
        tv=target.fields.get(field)
        if sv == tv:
            continue
        if sv is None or tv is None:
            status="MISSING_FIELD_VALUE"
        else:
            status="VALUE_MISMATCH"
        diffs.append(LogicalDifference(field,sv,tv,status))
    status="EQUIVALENT" if not diffs else "DIFFERENT"
    return LogicalComparison(source.logical_type,source.identity,status,tuple(diffs))
