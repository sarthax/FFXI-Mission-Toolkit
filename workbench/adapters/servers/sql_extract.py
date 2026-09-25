"""Transitional SQL-dump extraction for profile-backed server adapters.

This reuses the mature root SQL tokenizer while the parser is migrated into the
package layout. Physical rows are immediately normalized into logical records.
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import build_sql_index as sqlidx

from .base import LogicalRecord, ServerAdapter

_SET_RE=re.compile(r"^SET\s+@(\w+)\s*=\s*([^;]+);",re.I)


def _eval_int_expr(expr: str, variables: dict[str,int]) -> int | None:
    total=0
    saw=False
    for part in expr.split("|"):
        token=part.strip()
        if not token:
            continue
        if token.startswith("@"):
            name=token[1:]
            if name not in variables:
                return None
            value=variables[name]
        else:
            raw=token.strip()
            try:
                value=int(raw,0)
            except ValueError:
                return None
        total |= value
        saw=True
    return total if saw else None


def _variables(path: Path) -> dict[str,int]:
    result: dict[str,int]={}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
        m=_SET_RE.match(line.strip())
        if not m:
            continue
        value=_eval_int_expr(m.group(2),result)
        if value is not None:
            result[m.group(1)]=value
    return result


def _coerce(raw: Any, variables: dict[str,int]) -> Any:
    if raw is None or not isinstance(raw,str):
        return raw
    value=raw.strip()
    if value.upper()=="NULL":
        return None
    if "@" in value or "|" in value:
        resolved=_eval_int_expr(value,variables)
        if resolved is not None:
            return resolved
    unquoted=sqlidx.unquote(value)
    if unquoted is None:
        return None
    if not isinstance(unquoted,str):
        return unquoted
    text=unquoted.strip()
    try:
        return int(text,0)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return unquoted


def extract_physical_rows(adapter: ServerAdapter, logical_name: str) -> list[dict[str,Any]]:
    shape=adapter.resolve_table(logical_name)
    if shape is None:
        raise KeyError(f"Unknown logical table: {logical_name}")
    if not shape.parse_columns:
        raise ValueError(f"No physical parse column order declared for {adapter.family}:{logical_name}")
    path=adapter.source_path(logical_name)
    if path is None or not path.exists():
        return []
    clean=sqlidx.cleaned_path(path)
    variables=_variables(clean)
    rows=[]
    for raw in sqlidx.parse_table_file(clean,shape.physical_table,list(shape.parse_columns)):
        rows.append({key:_coerce(value,variables) for key,value in raw.items()})
    return rows


def extract_logical_records(adapter: ServerAdapter, logical_name: str) -> list[LogicalRecord]:
    rows=extract_physical_rows(adapter,logical_name)
    related=None
    if adapter.family=="DSP" and logical_name=="mob_groups":
        pools=extract_logical_records(adapter,"mob_pools")
        related={"mob_pools":pools}
    records=adapter.normalize_rows(logical_name,rows,related)
    path=adapter.source_path(logical_name)
    location=str(path) if path is not None else logical_name
    return [
        replace(record,notes=record.notes+(f"Extracted from {location}.",))
        for record in records
    ]
