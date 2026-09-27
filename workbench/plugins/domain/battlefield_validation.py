"""Validation of generated legacy-DSP battlefield SQL against a target snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .battlefield_dsp import (
    DspBattlefieldMembershipProposal,
    DspBattlefieldPolicyProposal,
)


@dataclass(frozen=True)
class GeneratedSqlValidation:
    validation_type: str
    status: str
    subject: str
    notes: tuple[str, ...] = ()


def validate_dsp_battlefield_proposals(
    membership: DspBattlefieldMembershipProposal | None = None,
    policy: DspBattlefieldPolicyProposal | None = None,
) -> tuple[GeneratedSqlValidation, ...]:
    results=[]

    if membership is not None:
        if membership.status=="EQUIVALENT":
            status="NOT_REQUIRED"
        elif membership.status=="ADDITIVE" and membership.safe_to_generate and membership.insert_sql:
            status="READY"
        else:
            status="MANUAL_REQUIRED"
        results.append(GeneratedSqlValidation(
            validation_type="DSP_BATTLEFIELD_MEMBERSHIP_PROPOSAL",
            status=status,
            subject=f"battlefield:{membership.battlefield_id}",
            notes=(
                f"missing_rows={len(membership.missing_rows)}",
                f"extra_rows={len(membership.extra_rows)}",
                f"generated_inserts={len(membership.insert_sql)}",
            ),
        ))

    if policy is not None:
        if policy.status=="EQUIVALENT":
            status="NOT_REQUIRED"
        elif policy.status=="UPDATE_PROPOSAL" and policy.safe_to_generate and policy.update_sql:
            status="READY"
        else:
            status="MANUAL_REQUIRED"
        results.append(GeneratedSqlValidation(
            validation_type="DSP_BATTLEFIELD_POLICY_PROPOSAL",
            status=status,
            subject=f"battlefield:{policy.battlefield_id}",
            notes=(
                f"differences={len(policy.differences)}",
                f"generated_update={policy.update_sql is not None}",
            ),
        ))

    return tuple(results)
