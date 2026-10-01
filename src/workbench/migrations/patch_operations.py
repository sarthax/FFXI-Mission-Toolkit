"""Deterministic, review-only source patch operations.

Operations require exact textual anchors and can be previewed in memory. This module
never writes target files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class PatchOperation:
    operation_id: str
    target_path: str
    operation_type: str
    anchor: str
    content: str
    expected_occurrences: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PatchOperationResult:
    operation_id: str
    status: str
    occurrences: int
    message: str


@dataclass(frozen=True)
class PatchPreview:
    status: str
    output: str
    results: tuple[PatchOperationResult, ...]


def preview_patch_operations(
    source_text: str,
    operations: Iterable[PatchOperation],
) -> PatchPreview:
    text=source_text
    results=[]

    for op in operations:
        occurrences=text.count(op.anchor)
        if occurrences != op.expected_occurrences:
            results.append(PatchOperationResult(
                op.operation_id,
                "MANUAL_REQUIRED",
                occurrences,
                f"Expected {op.expected_occurrences} anchor occurrence(s), found {occurrences}.",
            ))
            continue

        if op.operation_type=="INSERT_BEFORE":
            text=text.replace(op.anchor,op.content+op.anchor,1)
        elif op.operation_type=="INSERT_AFTER":
            text=text.replace(op.anchor,op.anchor+op.content,1)
        elif op.operation_type=="REPLACE_EXACT":
            text=text.replace(op.anchor,op.content,1)
        else:
            results.append(PatchOperationResult(
                op.operation_id,
                "MANUAL_REQUIRED",
                occurrences,
                f"Unsupported operation type: {op.operation_type}",
            ))
            continue

        results.append(PatchOperationResult(
            op.operation_id,
            "READY",
            occurrences,
            "Exact anchor matched and preview operation applied in memory.",
        ))

    status="READY" if results and all(r.status=="READY" for r in results) else "MANUAL_REQUIRED"
    return PatchPreview(status,text,tuple(results))
