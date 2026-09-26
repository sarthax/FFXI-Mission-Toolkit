"""Legacy DSP battlefield membership reshape proposals.

This plugin backend converts an already-resolved semantic battlefield group layout
into legacy DSP bcnm_battlefield rows. It only proposes missing INSERT rows.
Conflicting or extra target rows force manual review; no DELETE/UPDATE SQL is emitted.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping, Sequence

from workbench.migrations.generated_output import GeneratedOutput
from .base import PluginFinding


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


_DSP_CALLBACK_RE=re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",re.MULTILINE)


@dataclass(frozen=True)
class DspBattlefieldCallbackSurface:
    present_callbacks: tuple[str, ...]
    expected_callbacks: tuple[str, ...]
    missing_callbacks: tuple[str, ...]
    status: str


def analyze_dsp_battlefield_callbacks(
    lua_text: str,
    expected_callbacks: Sequence[str] = (),
) -> DspBattlefieldCallbackSurface:
    present=tuple(sorted(set(_DSP_CALLBACK_RE.findall(lua_text))))
    expected=tuple(dict.fromkeys(str(x) for x in expected_callbacks))
    missing=tuple(sorted(set(expected)-set(present)))
    return DspBattlefieldCallbackSurface(
        present_callbacks=present,
        expected_callbacks=expected,
        missing_callbacks=missing,
        status="COVERAGE_ALIGNED" if not missing else "CALLBACK_GAPS",
    )


def generated_outputs_for_dsp_battlefield(
    membership: DspBattlefieldMembershipProposal | None = None,
    policy: DspBattlefieldPolicyProposal | None = None,
) -> tuple[GeneratedOutput, ...]:
    outputs=[]
    if membership is not None and membership.safe_to_generate and membership.insert_sql:
        outputs.append(GeneratedOutput(
            output_id=f"generated:dsp:battlefield-membership:{membership.battlefield_id}",
            relative_path=f"sql-dsp/workbench_bcnm_battlefield_{membership.battlefield_id}.sql",
            artifact_type="SQL",
            content="\n".join(membership.insert_sql)+"\n",
            generator="framework.battlefield:dsp_membership",
            metadata={
                "battlefield_id":membership.battlefield_id,
                "proposal_status":membership.status,
                "table":"bcnm_battlefield",
            },
        ))
    if policy is not None and policy.safe_to_generate and policy.update_sql:
        outputs.append(GeneratedOutput(
            output_id=f"generated:dsp:battlefield-policy:{policy.battlefield_id}",
            relative_path=f"sql-dsp/workbench_bcnm_info_{policy.battlefield_id}.sql",
            artifact_type="SQL",
            content=policy.update_sql+"\n",
            generator="framework.battlefield:dsp_policy",
            metadata={
                "battlefield_id":policy.battlefield_id,
                "proposal_status":policy.status,
                "table":"bcnm_info",
            },
        ))
    return tuple(outputs)


@dataclass(frozen=True)
class DspBattlefieldCallbackAdaptationPlan:
    status: str
    required_callbacks: tuple[str, ...]
    present_callbacks: tuple[str, ...]
    missing_callbacks: tuple[str, ...]
    source_framework_methods: tuple[str, ...]
    safe_to_generate: bool
    notes: tuple[str, ...] = ()


def plan_dsp_battlefield_callback_adaptation(
    target_surface: DspBattlefieldCallbackSurface,
    *,
    source_framework_methods: Sequence[str] = (),
) -> DspBattlefieldCallbackAdaptationPlan:
    """Plan legacy callback structure without inventing callback bodies.

    Callback stubs are not generated because LSB framework orchestration can distribute
    mission, reward, entry and completion semantics across multiple source artifacts.
    """
    missing=target_surface.missing_callbacks
    if not missing:
        status="COVERAGE_ALIGNED"
        notes=("Legacy DSP callback surface already exists; no callback skeleton migration is required.",)
    else:
        status="MANUAL_REQUIRED"
        notes=(
            "Legacy DSP callback functions are missing.",
            "Translate source framework behavior into callback bodies using feature evidence; do not generate empty semantic stubs.",
        )
    return DspBattlefieldCallbackAdaptationPlan(
        status=status,
        required_callbacks=target_surface.expected_callbacks,
        present_callbacks=target_surface.present_callbacks,
        missing_callbacks=missing,
        source_framework_methods=tuple(sorted(set(source_framework_methods))),
        safe_to_generate=False,
        notes=notes,
    )


@dataclass(frozen=True)
class DspBattlefieldRepresentationPlan:
    status: str
    sql_policy_status: str
    sql_membership_status: str
    callback_status: str
    safe_generated_surfaces: tuple[str, ...]
    manual_surfaces: tuple[str, ...]
    notes: tuple[str, ...] = ()


def plan_dsp_battlefield_representation(
    membership: DspBattlefieldMembershipProposal,
    policy: DspBattlefieldPolicyProposal,
    callbacks: DspBattlefieldCallbackAdaptationPlan,
) -> DspBattlefieldRepresentationPlan:
    """Classify how an LSB battlefield should be represented on legacy DSP.

    SQL-backed policy/membership may be generated only when their proposal objects
    explicitly mark generation safe. Callback-body semantics are never invented:
    existing aligned callbacks require no rewrite, while missing callback behavior
    remains manual.
    """
    generated=[]
    manual=[]
    notes=[]

    if membership.safe_to_generate and membership.status in {"ADDITIVE","EQUIVALENT"}:
        if membership.insert_sql:
            generated.append("bcnm_battlefield")
    else:
        manual.append("bcnm_battlefield")
        notes.append("Battlefield membership drift is not safely additive.")

    if policy.safe_to_generate and policy.status in {"UPDATE_PROPOSAL","EQUIVALENT"}:
        if policy.update_sql:
            generated.append("bcnm_info")
    else:
        manual.append("bcnm_info")
        notes.append("Battlefield policy cannot be generated safely.")

    if callbacks.status=="COVERAGE_ALIGNED":
        callback_status="NOT_REQUIRED"
    else:
        callback_status="MANUAL_REQUIRED"
        manual.append("battlefield_callbacks")
        notes.extend(callbacks.notes)

    status="READY" if not manual else "MANUAL_REQUIRED"
    return DspBattlefieldRepresentationPlan(
        status=status,
        sql_policy_status=policy.status,
        sql_membership_status=membership.status,
        callback_status=callback_status,
        safe_generated_surfaces=tuple(sorted(generated)),
        manual_surfaces=tuple(sorted(set(manual))),
        notes=tuple(notes),
    )


def battlefield_representation_finding(
    feature_id: str,
    plan: DspBattlefieldRepresentationPlan,
) -> PluginFinding:
    """Expose a safe domain reshape result to the generic migration planner."""
    if plan.status=="READY":
        return PluginFinding(
            plugin_id="framework.battlefield",
            subject_id=feature_id,
            finding_type="MIGRATION_RESHAPE",
            status="COMPATIBLE",
            message="Legacy DSP already represents the battlefield framework surfaces covered by the verified representation plan.",
            metadata={
                "proposed_action":"NOT_REQUIRED",
                "safe_auto":True,
                "resolved_roles":[
                    "battlefield_script",
                    "level_cap_policy",
                    "entity_registry",
                ],
                "representation_status":plan.status,
                "callback_status":plan.callback_status,
            },
        )
    return PluginFinding(
        plugin_id="framework.battlefield",
        subject_id=feature_id,
        finding_type="MIGRATION_RESHAPE",
        status="MANUAL_REQUIRED",
        message="Battlefield representation still contains unresolved target surfaces.",
        metadata={
            "proposed_action":"MANUAL_REVIEW",
            "safe_auto":False,
            "resolved_roles":[],
            "manual_surfaces":list(plan.manual_surfaces),
            "representation_status":plan.status,
        },
    )
