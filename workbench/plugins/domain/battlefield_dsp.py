"""Legacy DSP battlefield membership reshape proposals.

This plugin backend converts an already-resolved semantic battlefield group layout
into legacy DSP bcnm_battlefield rows. It only proposes missing INSERT rows.
Conflicting or extra target rows force manual review; no DELETE/UPDATE SQL is emitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True, order=True)
class DspBattlefieldMember:
    battlefield_id: int
    battlefield_number: int
    entity_id: int
    conditions: int = 3


@dataclass(frozen=True)
class DspBattlefieldMembershipProposal:
    battlefield_id: int
    desired_rows: tuple[DspBattlefieldMember, ...]
    target_rows: tuple[DspBattlefieldMember, ...]
    missing_rows: tuple[DspBattlefieldMember, ...]
    extra_rows: tuple[DspBattlefieldMember, ...]
    insert_sql: tuple[str, ...]
    status: str
    safe_to_generate: bool


def _mapping(row: Any) -> Mapping[str, Any]:
    fields=getattr(row,"fields",None)
    if isinstance(fields,Mapping):
        return fields
    if isinstance(row,Mapping):
        return row
    raise TypeError(f"Unsupported battlefield membership row: {type(row)!r}")


def _normalized_target_rows(
    battlefield_id: int,
    rows: Iterable[Any],
) -> tuple[DspBattlefieldMember, ...]:
    out=[]
    for row in rows:
        fields=_mapping(row)
        if int(fields.get("battlefield_id",-1)) != battlefield_id:
            continue
        out.append(DspBattlefieldMember(
            battlefield_id=battlefield_id,
            battlefield_number=int(fields["battlefield_number"]),
            entity_id=int(fields["entity_id"]),
            conditions=int(fields.get("conditions",3)),
        ))
    return tuple(sorted(set(out)))


def propose_dsp_battlefield_membership(
    battlefield_id: int,
    source_groups: Sequence[Sequence[int]],
    target_rows: Iterable[Any] = (),
    *,
    conditions: int = 3,
) -> DspBattlefieldMembershipProposal:
    desired=tuple(sorted(
        DspBattlefieldMember(
            battlefield_id=battlefield_id,
            battlefield_number=group_number,
            entity_id=int(entity_id),
            conditions=conditions,
        )
        for group_number,group in enumerate(source_groups,start=1)
        for entity_id in group
    ))
    target=_normalized_target_rows(battlefield_id,target_rows)
    desired_set=set(desired)
    target_set=set(target)
    missing=tuple(sorted(desired_set-target_set))
    extra=tuple(sorted(target_set-desired_set))

    if not missing and not extra:
        status="EQUIVALENT"
        safe=True
        sql=()
    elif missing and not extra:
        status="ADDITIVE"
        safe=True
        sql=tuple(
            f"INSERT INTO `bcnm_battlefield` VALUES "
            f"({row.battlefield_id},{row.battlefield_number},{row.entity_id},{row.conditions});"
            for row in missing
        )
    else:
        status="DRIFT"
        safe=False
        sql=()

    return DspBattlefieldMembershipProposal(
        battlefield_id=battlefield_id,
        desired_rows=desired,
        target_rows=target,
        missing_rows=missing,
        extra_rows=extra,
        insert_sql=sql,
        status=status,
        safe_to_generate=safe,
    )
