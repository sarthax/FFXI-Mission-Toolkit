"""Unified read-only Auction House validation reporting.

Combines environment, lineage, live schema prerequisites, database reread freshness, active policy
freshness, and invariant checks into one fail-closed status payload. This module cannot execute or
commit Auction House mutations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

from .lineage_semantics import evaluate_lineage_semantics
from .lsb_validation import prepare_lsb_preview_validation
from .validation_pipeline import prepare_validate_from_active_config
from .write_probe import probe_write_readiness


@dataclass(frozen=True)
class ValidationBlocker:
    stage: str
    code: str
    message: str


def _issues(value: Any) -> list[dict[str, Any]]:
    raw = getattr(value, "issues", None)
    if raw is None and isinstance(value, dict):
        raw = value.get("issues")
    out: list[dict[str, Any]] = []
    for item in raw or []:
        if isinstance(item, dict):
            out.append(dict(item))
        elif is_dataclass(item):
            out.append(asdict(item))
        else:
            out.append({
                "code": getattr(item, "code", "unknown"),
                "message": getattr(item, "message", "Blocked"),
                "blocking": getattr(item, "blocking", True),
            })
    return out


def _blocking(stage: str, issues: list[dict[str, Any]]) -> list[ValidationBlocker]:
    return [
        ValidationBlocker(stage, str(item.get("code") or "unknown"), str(item.get("message") or "Blocked"))
        for item in issues
        if bool(item.get("blocking", True))
    ]


def build_validation_report(
    *,
    environment: dict[str, Any],
    schema_family_hint: str,
    readiness: dict[str, Any],
    prepared: Any,
    evidence: Any,
    invariants: Any | None,
    policy_load: Any,
    policy_binding: Any,
) -> dict[str, Any]:
    family = str(environment.get("family") or "").strip().lower()
    operation = str(getattr(prepared, "operation", "") or "unknown")
    lineage = evaluate_lineage_semantics(profile_family=family, schema_family_hint=schema_family_hint)

    blockers: list[ValidationBlocker] = []
    env_issues: list[dict[str, Any]] = []
    if not environment.get("is_active"):
        env_issues.append({"code": "environment_not_active", "message": "The selected server environment is not active.", "blocking": True})
    if family not in {"dsp", "topaz", "lsb"}:
        env_issues.append({"code": "environment_lineage_unknown", "message": "The active environment must explicitly identify DSP, Topaz, or LSB.", "blocking": True})
    blockers.extend(_blocking("environment", env_issues))

    lineage_issues = list(lineage.get("issues") or [])
    blockers.extend(_blocking("lineage", lineage_issues))

    readiness_issues: list[dict[str, Any]] = []
    if family in {"dsp", "topaz"}:
        if operation == "list_item" and not readiness.get("legacy_listing_shape_present"):
            readiness_issues.append({"code": "legacy_listing_shape_missing", "message": "Required legacy Auction House listing tables/schema shape are not present.", "blocking": True})
        if operation in {"purchase_item", "admin_cleanup"} and not readiness.get("legacy_purchase_prerequisites_present"):
            readiness_issues.append({"code": "legacy_purchase_prerequisites_missing", "message": "Required legacy purchase tables/triggers are not present.", "blocking": True})
    elif family == "lsb":
        key = "lsb_listing_ready" if operation == "list_item" else "lsb_purchase_ready"
        if operation in {"list_item", "purchase_item", "admin_cleanup"} and not readiness.get(key):
            readiness_issues.append({"code": "lsb_write_prerequisites_missing", "message": "Required LSB Auction House tables/triggers are not present.", "blocking": True})
    blockers.extend(_blocking("schema_readiness", readiness_issues))

    prepared_issues = _issues(prepared)
    blockers.extend(_blocking("database_freshness", prepared_issues))
    if str(getattr(evidence, "transaction_mode", "")) != "read_only_rolled_back":
        blockers.append(ValidationBlocker("database_freshness", "reread_not_read_only", "Database validation evidence was not collected in a read-only rolled-back transaction."))

    policy_issues = _issues(policy_load)
    blockers.extend(_blocking("policy", policy_issues))
    binding_issues = _issues(policy_binding)
    blockers.extend(_blocking("policy_binding", binding_issues))

    invariant_issues = _issues(invariants) if invariants is not None else []
    if invariants is None:
        blockers.append(ValidationBlocker("invariants", "invariants_not_evaluated", "Semantic invariants were not evaluated because an earlier validation gate failed."))
    else:
        blockers.extend(_blocking("invariants", invariant_issues))

    evidence_blockers = [
        blocker for blocker in blockers
        if not (blocker.stage == "lineage" and blocker.code == "lineage_execution_contract_incomplete")
    ]
    read_only_validation_ready = not evidence_blockers

    stages = {
        "environment": {"ready": not _blocking("environment", env_issues), "issues": env_issues},
        "lineage": {"ready": not _blocking("lineage", lineage_issues), "issues": lineage_issues, "details": lineage},
        "schema_readiness": {"ready": not readiness_issues, "issues": readiness_issues, "details": readiness},
        "database_freshness": {
            "ready": bool(getattr(prepared, "validation_ready", False)) and str(getattr(evidence, "transaction_mode", "")) == "read_only_rolled_back",
            "issues": prepared_issues,
            "details": getattr(prepared, "as_dict", lambda: {})(),
        },
        "policy": {"ready": bool(getattr(policy_load, "policy_ready", False)), "issues": policy_issues, "details": getattr(policy_load, "as_dict", lambda: {})()},
        "policy_binding": {"ready": bool(getattr(policy_binding, "binding_ready", False)), "issues": binding_issues, "details": getattr(policy_binding, "as_dict", lambda: {})()},
        "invariants": {"ready": bool(invariants is not None and getattr(invariants, "invariants_ready", False)), "issues": invariant_issues, "details": None if invariants is None else invariants.as_dict()},
    }

    return {
        "status": "ready" if read_only_validation_ready else "blocked",
        "read_only_validation_ready": read_only_validation_ready,
        "execution_ready": False,
        "executor_enabled": False,
        "write_enabled": False,
        "operation": operation,
        "environment": dict(environment),
        "schema_family_hint": schema_family_hint,
        "stages": stages,
        "blockers": [asdict(item) for item in blockers],
    }


def run_legacy_preview_validation(*, service, environment: dict[str, Any], preview: dict[str, Any], server_root: Path | str) -> dict[str, Any]:
    family = str(environment.get("family") or "").strip().lower()
    if family not in {"dsp", "topaz"}:
        return {"status":"blocked","read_only_validation_ready":False,"execution_ready":False,"executor_enabled":False,"write_enabled":False,"operation":str(preview.get("action") or "unknown"),"environment":dict(environment),"schema_family_hint":service.schema.family_hint,"stages":{},"blockers":[{"stage":"environment","code":"legacy_validation_scope_unsupported","message":"This validation orchestrator supports explicit DSP and Topaz environments only."}]}
    operation = str(preview.get("action") or "").strip().lower()
    prepared, evidence, invariants, policy_load, policy_binding = prepare_validate_from_active_config(service=service, family=family, operation=operation, environment=environment, preview=preview, server_root=server_root, preview_environment=preview.get("environment") if isinstance(preview.get("environment"), dict) else None)
    readiness = probe_write_readiness(service.connection).as_dict()
    return build_validation_report(environment=environment, schema_family_hint=service.schema.family_hint, readiness=readiness, prepared=prepared, evidence=evidence, invariants=invariants, policy_load=policy_load, policy_binding=policy_binding)


def run_lsb_preview_validation(*, service, environment: dict[str, Any], preview: dict[str, Any], server_root: Path | str) -> dict[str, Any]:
    if str(environment.get("family") or "").strip().lower() != "lsb":
        return {"status":"blocked","read_only_validation_ready":False,"execution_ready":False,"executor_enabled":False,"write_enabled":False,"operation":str(preview.get("action") or "unknown"),"environment":dict(environment),"schema_family_hint":service.schema.family_hint,"stages":{},"blockers":[{"stage":"environment","code":"lsb_validation_scope_unsupported","message":"The LSB validation orchestrator requires an explicit LandSandBoat environment."}]}
    operation = str(preview.get("action") or "").strip().lower()
    prepared, evidence, invariants, policy_load, policy_binding = prepare_lsb_preview_validation(service=service, operation=operation, environment=environment, preview=preview, server_root=server_root)
    readiness = probe_write_readiness(service.connection).as_dict()
    report = build_validation_report(environment=environment, schema_family_hint=service.schema.family_hint, readiness=readiness, prepared=prepared, evidence=evidence, invariants=invariants, policy_load=policy_load, policy_binding=policy_binding)
    report["validation_model"] = "lsb-source-settings-and-trigger"
    return report


def run_preview_validation(*, service, environment: dict[str, Any], preview: dict[str, Any], server_root: Path | str) -> dict[str, Any]:
    family = str(environment.get("family") or "").strip().lower()
    if family == "lsb":
        return run_lsb_preview_validation(service=service, environment=environment, preview=preview, server_root=server_root)
    if family in {"dsp", "topaz"}:
        return run_legacy_preview_validation(service=service, environment=environment, preview=preview, server_root=server_root)
    return {"status":"blocked","read_only_validation_ready":False,"execution_ready":False,"executor_enabled":False,"write_enabled":False,"operation":str(preview.get("action") or "unknown"),"environment":dict(environment),"schema_family_hint":service.schema.family_hint,"stages":{},"blockers":[{"stage":"environment","code":"validation_lineage_unsupported","message":"Preview validation requires an explicit LSB, DSP, or Topaz environment."}]}
