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


_DSP_POLICY_COLUMNS={
    "time_limit":"timeLimit",
    "level_cap":"levelCap",
    "party_size":"partySize",
    "loot_drop_id":"lootDropId",
    "rules":"rules",
    "is_mission":"isMission",
}


@dataclass(frozen=True)
class DspBattlefieldPolicyProposal:
    battlefield_id: int
    desired_fields: Mapping[str, Any]
    target_fields: Mapping[str, Any]
    differences: tuple[tuple[str, Any, Any], ...]
    update_sql: str | None
    status: str
    safe_to_generate: bool


def _sql_scalar(value: Any) -> str:
    if isinstance(value,bool):
        return "1" if value else "0"
    if isinstance(value,(int,float)):
        return str(value)
    raise TypeError(f"Unsupported battlefield policy SQL value: {value!r}")


def propose_dsp_battlefield_policy(
    battlefield_id: int,
    desired_fields: Mapping[str, Any],
    target_record: Any | None,
) -> DspBattlefieldPolicyProposal:
    unknown=set(desired_fields)-set(_DSP_POLICY_COLUMNS)
    if unknown:
        raise ValueError(f"Unsupported DSP battlefield policy fields: {sorted(unknown)}")

    desired=dict(desired_fields)
    if target_record is None:
        return DspBattlefieldPolicyProposal(
            battlefield_id=battlefield_id,
            desired_fields=desired,
            target_fields={},
            differences=(),
            update_sql=None,
            status="MISSING_TARGET",
            safe_to_generate=False,
        )

    target=dict(_mapping(target_record))
    if int(target.get("battlefield_id",-1)) != battlefield_id:
        raise ValueError("Target battlefield record identity does not match requested battlefield_id")

    differences=tuple(
        (field,desired[field],target.get(field))
        for field in sorted(desired)
        if desired[field] != target.get(field)
        and not (
            isinstance(desired[field],bool)
            and int(bool(desired[field])) == target.get(field)
        )
    )
    if not differences:
        status="EQUIVALENT"
        sql=None
        safe=True
    else:
        assignments=", ".join(
            f"`{_DSP_POLICY_COLUMNS[field]}`={_sql_scalar(source_value)}"
            for field,source_value,_target_value in differences
        )
        sql=f"UPDATE `bcnm_info` SET {assignments} WHERE `bcnmId`={battlefield_id};"
        status="UPDATE_PROPOSAL"
        safe=True

    return DspBattlefieldPolicyProposal(
        battlefield_id=battlefield_id,
        desired_fields=desired,
        target_fields=target,
        differences=differences,
        update_sql=sql,
        status=status,
        safe_to_generate=safe,
    )
