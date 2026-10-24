"""Synthetic-only, non-executing R4 multi-role preflight projection.

The JSON model here is *not* the unapproved XIHeadless #105 protocol, and its
claims do not authorize a real pool lease, observation oracle, or task launch.
No network, database, filesystem, runtime adapter, or game-client entry point.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

FORMAT = "toolkit-r4-synthetic-role-preflight/1"
_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_ROLE_KINDS = frozenset({"leader", "healer", "dps", "tank", "support"})
_DEFINITION_KEYS = frozenset({
    "schema", "feature_id", "scenario_id", "roles", "checkpoints",
    "required_role_kinds",
})
_ROLE_KEYS = frozenset({"id", "kind", "required_capabilities"})
_CHECKPOINT_KEYS = frozenset({
    "id", "required_role_ids", "depends_on", "oracle_id",
})
_CLAIM_KEYS = frozenset({
    "available_role_kinds", "available_pool_slots", "observed_capabilities",
    "lease_status", "cleanup_status", "oracle_statuses",
})
_LEASE_STATES = frozenset({"UNKNOWN", "REPORTED_AVAILABLE", "REPORTED_UNAVAILABLE"})
_CLEANUP_STATES = frozenset({"UNKNOWN", "REPORTED_COMPLETE", "REPORTED_INCOMPLETE"})
_ORACLE_STATES = frozenset({"UNKNOWN", "REPORTED_COVERED", "MISSING"})


def _fail(message: str) -> None:
    raise ValueError(message)


def _ident(value: Any) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        _fail("invalid symbolic identifier")
    return value


def _ids(value: Any, maximum: int = 24, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum or (
        not allow_empty and not value
    ):
        _fail("invalid symbolic id list")
    entries = [_ident(v) for v in value]
    if len(entries) != len(set(entries)):
        _fail("duplicate symbolic id")
    return entries


def _json_bound(value: Any, limit: int) -> bytes:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         allow_nan=False, ensure_ascii=True).encode("ascii")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("non-JSON preflight input") from exc
    if len(raw) > limit:
        _fail("preflight input exceeds offline size limit")
    return raw


def _definition(value: Any) -> tuple[dict, bytes]:
    raw = _json_bound(value, 32768)
    if not isinstance(value, dict) or set(value) != _DEFINITION_KEYS:
        _fail("unsupported multi-role schema fields")
    if value["schema"] != FORMAT:
        _fail("unsupported multi-role schema version")
    _ident(value["feature_id"])
    _ident(value["scenario_id"])
    roles = value["roles"]
    checkpoints = value["checkpoints"]
    if not isinstance(roles, list) or not 1 <= len(roles) <= 6:
        _fail("requires 1–6 synthetic roles")
    if not isinstance(checkpoints, list) or not 1 <= len(checkpoints) <= 24:
        _fail("requires 1–24 synthetic checkpoints")
    role_by_id = {}
    for role in roles:
        if not isinstance(role, dict) or set(role) != _ROLE_KEYS:
            _fail("invalid role fields")
        rid = _ident(role["id"])
        kind = role["kind"]
        if not isinstance(kind, str) or kind not in _ROLE_KINDS:
            _fail("unsupported symbolic role")
        _ids(role["required_capabilities"], allow_empty=True)
        if rid in role_by_id:
            _fail("duplicate role id")
        role_by_id[rid] = kind
    required = _ids(value["required_role_kinds"], maximum=6)
    if not set(required).issubset(_ROLE_KINDS):
        _fail("unsupported required role kind")
    if not set(required).issubset(set(role_by_id.values())):
        _fail("required role missing from synthetic role graph")
    checkpoint_by_id = {}
    for check in checkpoints:
        if not isinstance(check, dict) or set(check) != _CHECKPOINT_KEYS:
            _fail("invalid checkpoint fields")
        cid = _ident(check["id"])
        needed = _ids(check["required_role_ids"], maximum=6)
        dependencies = _ids(check["depends_on"], maximum=24, allow_empty=True)
        _ident(check["oracle_id"])
        if not set(needed).issubset(role_by_id):
            _fail("checkpoint references unknown role")
        if cid in checkpoint_by_id:
            _fail("duplicate checkpoint")
        checkpoint_by_id[cid] = dependencies
    for cid, deps in checkpoint_by_id.items():
        if cid in deps or not set(deps).issubset(checkpoint_by_id):
            _fail("invalid checkpoint dependency")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(cid: str) -> None:
        if cid in visiting:
            _fail("cyclic checkpoint dependencies")
        if cid in visited:
            return
        visiting.add(cid)
        for dep in checkpoint_by_id[cid]:
            visit(dep)
        visiting.remove(cid)
        visited.add(cid)

    for cid in sorted(checkpoint_by_id):
        visit(cid)
    return value, raw


def _claims(value: Any, required_oracles: set[str]) -> dict:
    if value is None:
        return {}
    _json_bound(value, 16384)
    if not isinstance(value, dict) or not set(value).issubset(_CLAIM_KEYS):
        _fail("unsupported or malformed preflight claims")
    if "available_role_kinds" in value:
        if not set(_ids(value["available_role_kinds"], maximum=5,
                        allow_empty=True)).issubset(_ROLE_KINDS):
            _fail("unknown available role kind")
    if "available_pool_slots" in value:
        slots = value["available_pool_slots"]
        if type(slots) is not int or not 0 <= slots <= 64:
            _fail("invalid claimed pool capacity")
    if "observed_capabilities" in value:
        _ids(value["observed_capabilities"], maximum=64, allow_empty=True)
    if "lease_status" in value and value["lease_status"] not in _LEASE_STATES:
        _fail("invalid lease status")
    if "cleanup_status" in value and value["cleanup_status"] not in _CLEANUP_STATES:
        _fail("invalid cleanup status")
    if "oracle_statuses" in value:
        oracles = value["oracle_statuses"]
        if not isinstance(oracles, dict) or len(oracles) > 24:
            _fail("invalid oracle status map")
        for oid, state in oracles.items():
            if _ident(oid) not in required_oracles or state not in _ORACLE_STATES:
                _fail("unrecognized oracle claim")
    return value


def offline_role_preflight(definition: object, claims: object = None) -> dict:
    """Project a never-executable role graph and fail-closed preflight checks."""
    result: dict = {
        "schema": FORMAT,
        "preflight_state": "BLOCKED",
        "checks": [], "blockers": [], "unknowns": [],
        "role_graph": {"nodes": [], "edges": []},
        "checkpoints": [],
        "role_needs": [],
        "feature_link": None, "scenario_link": None,
        "definition_digest_authority": "LOCAL_SYNTHETIC_SERIALIZATION_ONLY",
        "execution_status": "NOT_AUTHORIZED",
        "execution_enabled": False, "task_admission_supported": False,
        "lease_acquisition_supported": False, "persisted": False,
        "claims_authority": "UNVERIFIED_PREVIEW_ONLY",
        "oracle_authority": "NOT_ESTABLISHED",
        "observed_gameplay_verdict": "UNKNOWN",
    }

    def check(cid: str, state: str, detail: str) -> None:
        result["checks"].append({"id": cid, "state": state, "detail": detail})
        if state == "BLOCKED":
            result["blockers"].append(cid)
        elif state == "UNKNOWN":
            result["unknowns"].append(cid)

    try:
        model, raw = _definition(definition)
        oracle_ids = {c["oracle_id"] for c in model["checkpoints"]}
        supplied = _claims(claims, oracle_ids)
    except (ValueError, TypeError, RecursionError) as exc:
        check("offline_schema", "BLOCKED", str(exc))
        return result

    result["feature_link"] = {
        "feature_id": model["feature_id"],
        "kind": "FEATURE_CATALOG_REFERENCE_ONLY",
    }
    result["scenario_link"] = {
        "feature_id": model["feature_id"],
        "scenario_id": model["scenario_id"],
        "kind": "SCENARIO_SPECIFICATION_REFERENCE_ONLY",
    }
    result["local_definition_sha256"] = hashlib.sha256(raw).hexdigest()
    check("offline_schema", "DECLARED", "Toolkit-local synthetic contract only")
    roles = sorted(model["roles"], key=lambda v: v["id"])
    checkpoints = sorted(model["checkpoints"], key=lambda v: v["id"])
    result["role_needs"] = [
        {"role_id": role["id"], "role_kind": role["kind"],
         "lease_units_requested": 1,
         "required_capabilities": sorted(role["required_capabilities"])}
        for role in roles
    ]
    nodes = [
        {"id": r["id"], "kind": "ROLE", "role_kind": r["kind"]}
        for r in roles
    ] + [
        {"id": c["id"], "kind": "CHECKPOINT"}
        for c in checkpoints
    ]
    edges = [
        {"from": role_id, "to": c["id"], "kind": "REQUIRED_ROLE"}
        for c in checkpoints for role_id in c["required_role_ids"]
    ] + [
        {"from": dependency, "to": c["id"], "kind": "CHECKPOINT_DEPENDENCY"}
        for c in checkpoints for dependency in c["depends_on"]
    ]
    result["role_graph"] = {"nodes": nodes, "edges": sorted(
        edges, key=lambda e: (e["to"], e["kind"], e["from"]))}
    required_kinds = set(model["required_role_kinds"])
    have_roles = supplied.get("available_role_kinds")
    missing_roles = sorted(required_kinds - set(have_roles)) if have_roles is not None else []
    check("role_coverage", "UNKNOWN" if have_roles is None else
          "BLOCKED" if missing_roles else "DECLARED",
          "Missing claimed role kinds: " + ", ".join(missing_roles) if missing_roles
          else "Role availability is unverified, even when declared")
    pool = supplied.get("available_pool_slots")
    need = len(roles)
    check("pool_capacity", "UNKNOWN" if pool is None else
          "BLOCKED" if pool < need else "DECLARED",
          f"Needs {need} distinct disposable role lease(s); capacity is an unverified claim")
    required_capabilities = set().union(*(set(r["required_capabilities"]) for r in roles))
    caps = supplied.get("observed_capabilities")
    missing_caps = sorted(required_capabilities - set(caps)) if caps is not None else []
    check("capability_coverage", "UNKNOWN" if caps is None else
          "BLOCKED" if missing_caps else "DECLARED",
          "Missing symbolic capabilities: " + ", ".join(missing_caps)
          if missing_caps else "Symbolic capability claims require actual observation")
    lease = supplied.get("lease_status", "UNKNOWN")
    check("lease_ownership", "BLOCKED" if lease == "REPORTED_UNAVAILABLE" else
          "DECLARED" if lease == "REPORTED_AVAILABLE" else "UNKNOWN",
          "No pool lease tokens or quarantine state are independently verified")
    cleanup = supplied.get("cleanup_status", "UNKNOWN")
    check("cleanup", "BLOCKED" if cleanup == "REPORTED_INCOMPLETE" else
          "DECLARED" if cleanup == "REPORTED_COMPLETE" else "UNKNOWN",
          "No observed logout, disband, cooldown or cleanup authority")
    reported_oracles = supplied.get("oracle_statuses", {})
    for c in checkpoints:
        oid = c["oracle_id"]
        claimed = reported_oracles.get(oid, "UNKNOWN")
        state = "BLOCKED" if claimed == "MISSING" else (
            "DECLARED" if claimed == "REPORTED_COVERED" else "UNKNOWN")
        check("oracle:" + oid, state,
              "Claim is not independent oracle approval or observed PASS")
        result["checkpoints"].append({
            "id": c["id"], "oracle_id": oid, "oracle_check_state": state,
            "required_role_ids": sorted(c["required_role_ids"]),
            "depends_on": sorted(c["depends_on"]),
            "assertion_verdict": "UNKNOWN",
            "source_authenticated": False,
        })
    # All claims are advisory, so even every DECLARED check is never READY.
    result["preflight_state"] = (
        "BLOCKED" if result["blockers"] else "UNKNOWN"
    )
    return result
