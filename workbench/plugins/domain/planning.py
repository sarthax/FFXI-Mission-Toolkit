"""Translate domain-plugin migration findings into generic MigrationAction records."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Iterable

from workbench.core.schema import MigrationAction
from .base import PluginFinding


def _action_id(migration_id: str, finding: PluginFinding) -> str:
    payload=json.dumps({
        "migration_id":migration_id,
        "plugin_id":finding.plugin_id,
        "subject_id":finding.subject_id,
        "finding_type":finding.finding_type,
        "message":finding.message,
        "metadata":dict(finding.metadata),
    },sort_keys=True,default=str).encode("utf-8")
    return "plugin:"+hashlib.sha256(payload).hexdigest()[:16]


def plugin_findings_to_actions(
    findings: Iterable[PluginFinding],
    migration_id: str,
) -> tuple[MigrationAction, ...]:
    actions=[]
    for finding in findings:
        if finding.finding_type not in {"MIGRATION_RULE","MIGRATION_RESHAPE"}:
            continue
        proposed=str(finding.metadata.get("proposed_action") or "MANUAL_REVIEW")
        status=finding.status or "MANUAL_REQUIRED"
        actions.append(MigrationAction(
            action_id=_action_id(migration_id,finding),
            migration_id=migration_id,
            action=proposed,
            status=status,
            reason=finding.message,
            metadata={
                "plugin_id":finding.plugin_id,
                "subject_id":finding.subject_id,
                "finding_type":finding.finding_type,
                **dict(finding.metadata),
            },
        ))
    return tuple(actions)


def apply_plugin_reshape_findings(
    actions: Iterable[MigrationAction],
    findings: Iterable[PluginFinding],
) -> tuple[MigrationAction, ...]:
    """Apply only explicitly safe role-scoped plugin reshape findings.

    The generic planner reads role metadata but does not know what a battlefield,
    mission, Assault, or other domain object means.
    """
    safe_roles=set()
    for finding in findings:
        if finding.finding_type!="MIGRATION_RESHAPE":
            continue
        if finding.metadata.get("safe_auto") is not True:
            continue
        if finding.metadata.get("proposed_action")!="NOT_REQUIRED":
            continue
        safe_roles.update(str(role) for role in finding.metadata.get("resolved_roles",[]))

    refined=[]
    for action in actions:
        role=str(action.metadata.get("source_role") or "")
        if role and role in safe_roles:
            refined.append(replace(
                action,
                action="NOT_REQUIRED",
                status="COMPATIBLE",
                reason="Domain plugin verified an equivalent target representation for this source role.",
                metadata={
                    **dict(action.metadata),
                    "plugin_reshape_applied":True,
                },
            ))
        else:
            refined.append(action)
    return tuple(refined)
