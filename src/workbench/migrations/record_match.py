"""Semantic matching helpers for logical records across server lineages."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
from workbench.adapters.servers.base import LogicalRecord

@dataclass(frozen=True)
class RecordMatch:
    logical_type: str
    source: LogicalRecord
    target: LogicalRecord
    match_basis: str
    identity_changes: tuple[tuple[str,Any,Any], ...] = ()

def _norm_name(value: Any) -> str:
    return str(value or "").strip().lower()

def match_records(source: Iterable[LogicalRecord], target: Iterable[LogicalRecord]) -> list[RecordMatch]:
    source=list(source); target=list(target)
    if not source:
        return []
    logical_type=source[0].logical_type
    if any(r.logical_type != logical_type for r in source+target):
        raise ValueError("Mixed logical record types are not supported")

    matches=[]
    used=set()
    for s in source:
        exact=next((t for i,t in enumerate(target) if i not in used and t.identity==s.identity),None)
        if exact is not None:
            idx=target.index(exact); used.add(idx)
            matches.append(RecordMatch(logical_type,s,exact,"EXACT_IDENTITY"))
            continue

        if logical_type=="instances":
            sname=_norm_name(s.fields.get("name"))
            candidates=[(i,t) for i,t in enumerate(target) if i not in used and _norm_name(t.fields.get("name"))==sname and sname]
            if len(candidates)==1:
                idx,t=candidates[0]; used.add(idx)
                changes=()
                sid=s.fields.get("instance_id"); tid=t.fields.get("instance_id")
                if sid != tid:
                    changes=(("instance_id",sid,tid),)
                matches.append(RecordMatch(logical_type,s,t,"UNIQUE_NORMALIZED_NAME",changes))
    return matches

def compare_instance_membership(
    source_entities: Iterable[LogicalRecord],
    target_entities: Iterable[LogicalRecord],
    source_instance_id: Any,
    target_instance_id: Any,
) -> dict[str,Any]:
    source_ids={r.fields.get("entity_id") for r in source_entities if r.fields.get("instance_id")==source_instance_id}
    target_ids={r.fields.get("entity_id") for r in target_entities if r.fields.get("instance_id")==target_instance_id}
    return {
        "source_instance_id":source_instance_id,
        "target_instance_id":target_instance_id,
        "shared":sorted(x for x in source_ids & target_ids if x is not None),
        "source_only":sorted(x for x in source_ids - target_ids if x is not None),
        "target_only":sorted(x for x in target_ids - source_ids if x is not None),
    }
