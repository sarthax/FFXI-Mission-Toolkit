"""Advisory R8 scenario catalog and deterministic NON-EXECUTING preflight.

Published canonical v1 specifications are the *only* scenario entries.
Readiness/domain planning entries are never registered as runners.
All caller-supplied evidence is an unverified preview claim, not authorization.
No environment, SQL, MCP, process, file writes or privileged calls occur.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from workbench.runtime.paths import repo_path
from .scenario_contract_v2 import compatibility_report, source_attribution_report
from .test_specifications import specifications, validate_spec

_SHA40 = re.compile(r"[0-9a-fA-F]{40}\Z")
_FIXED_LOCAL_RUNNER = ("moghancement", "MOG-09", "xiheadless_observation_v1")


def _identity(spec: dict) -> dict:
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False)
    return {"feature_id": spec["feature_id"], "scenario_id": spec["case_id"],
            "schema_version": spec["schema_version"],
            "contract_version": (spec.get("contract_v2") or {}).get("contract_version"),
            "local_definition_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "digest_authority": "LOCAL_SERIALIZATION_ONLY"}


def _entry(spec: dict) -> dict:
    validate_spec(spec)
    v2 = spec.get("contract_v2") or {}
    attribution = source_attribution_report(spec)
    fixed = (spec["feature_id"], spec["case_id"], spec["runner"]) == _FIXED_LOCAL_RUNNER
    runner = "FIXED_LOCAL_OPERATOR_OBSERVATION" if fixed else "UNASSIGNED_DESIGN_ONLY"
    source_claims = [
        {"ref": s["ref"], "classification": s["classification"],
         "revision": s["revision"], "sha256": s["sha256"]}
        for s in v2.get("sources", [])
    ]
    required_permissions = {"operator_approval", "disposable_character"} if fixed else set()
    requested_mutation = False
    for req in v2.get("step_requirements", []):
        required_permissions.update(req["required_permissions"])
        if req["operation_class"] == "mutating":
            requested_mutation = True
    return {
        **_identity(spec), "name": spec["name"],
        "runner": spec["runner"], "runner_classification": runner,
        "published_execution_status": spec["execution_status"],
        "required_observation_capabilities": list(spec["observations"]),
        "required_preconditions": list(spec["preconditions"]),
        "required_permissions": sorted(required_permissions),
        "required_authorization_class": ("LOCAL_OPERATOR_DISPOSABLE_CHARACTER"
                                        if fixed else "UNASSIGNED"),
        "required_oracle_ids": [a["id"] for a in spec["assertions"]],
        "oracle_approval": "NOT_ESTABLISHED",
        "source_provenance": {"declarations": source_claims,
                              "case": attribution["case"], "steps": attribution["steps"],
                              "independent_verification": "NOT_ESTABLISHED"},
        "deployment_pins": dict(v2.get("fingerprints", {})),
        "compatibility_state": compatibility_report(spec)["state"],
        "operation_class": "MUTATING_UNSUPPORTED" if requested_mutation else "UNKNOWN_UNVERIFIED",
        "unknown_fields": ["character", "zone", "roles", "deployed_server_revision",
                           "deployed_client_revision", "runner_binary_digest",
                           "independent_oracle_authority", "observation_completeness",
                           "authorization_effective", "lease_ownership"],
        "execution_status": "NOT_AUTHORIZED",
        "execution_enabled": False,
        "task_admission_supported": False,
    }


def _published(specs: list[dict] | None) -> list[dict]:
    candidates = specifications() if specs is None else specs
    if not isinstance(candidates, list):
        raise ValueError("scenario catalog must be a list")
    entries = []
    for spec in candidates:
        entries.append(_entry(spec))
    ids = [(e["feature_id"], e["scenario_id"]) for e in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate published scenario identity")
    return sorted(entries, key=lambda x: (x["feature_id"], x["scenario_id"]))


def catalog_preview(specs: list[dict] | None = None) -> dict:
    """Read only published specs plus links to planning *features*, not staged cases."""
    entries = _published(specs)
    planned = json.loads(Path(repo_path("data", "testing", "feature_test_readiness.json"))
                         .read_text(encoding="utf-8"))
    feature_links = []
    for feature in planned["features"]:
        published = [e["scenario_id"] for e in entries if e["feature_id"] == feature["id"]]
        feature_links.append({
            "feature_id": feature["id"], "feature_name": feature["name"],
            "published_scenario_ids": published,
            "catalog_state": "PUBLISHED_DECLARATIONS_ONLY" if published
                             else "NO_PUBLISHED_SCENARIO",
            "planned_cases_registered_as_runner": False,
        })
    return {
        "catalog_schema": "toolkit-r8-readonly-catalog/1",
        "scenarios": entries,
        "feature_links": feature_links,
        "unknown_policy": "FAIL_CLOSED",
        "execution_status": "NOT_AUTHORIZED",
        "execution_enabled": False,
        "task_admission_supported": False,
        "note": "Advisory metadata only. A matching preview does not authorize or invoke execution.",
    }


def preflight_preview(feature_id: str, scenario_id: str, *,
                      claims: dict | None = None,
                      specs: list[dict] | None = None) -> dict:
    """Pure comparison of UNTRUSTED preview claims to declarations.

    claims has deliberately narrow optional keys. Even fully matching claims
    are not independently authenticated; state never becomes executable.
    """
    supplied = {} if claims is None else claims
    allowed = {"schema_version", "deployed_commits", "observation_capabilities",
               "oracle_ids", "source_attribution_confirmed", "authorization_claimed",
               "character_zone_claimed", "lease_claimed", "mutation_requested"}
    if not isinstance(supplied, dict) or set(supplied) - allowed:
        raise ValueError("unsupported preview claim fields")
    catalog = _published(specs)
    matched = next((e for e in catalog if
                    (e["feature_id"], e["scenario_id"]) == (feature_id, scenario_id)), None)
    checks: list[dict] = []

    def check(name: str, state: str, detail: str) -> None:
        checks.append({"id": name, "state": state, "detail": detail})

    if matched is None:
        check("published_identity", "BLOCKED", "No published canonical specification")
    else:
        check("published_identity", "DECLARED", "Published canonical specification found")
        version = supplied.get("schema_version")
        check("scenario_version",
              "UNKNOWN" if version is None else
              "DECLARED" if type(version) is int and version == matched["schema_version"] else "BLOCKED",
              "Caller version is an unverified claim; required for stable binding")
        fixed = matched["runner_classification"] == "FIXED_LOCAL_OPERATOR_OBSERVATION"
        check("runner", "DECLARED" if fixed else "BLOCKED",
              "Existing MOG-09 fixed local runner only; no generic Headless execution")
        commits = supplied.get("deployed_commits")
        full = (isinstance(commits, dict) and set(commits) ==
                {"dsp_commit", "headless_commit", "toolkit_commit"} and
                all(isinstance(v, str) and _SHA40.fullmatch(v) for v in commits.values()))
        check("deployment_identity", "UNKNOWN" if commits is None else
              "DECLARED" if full else "BLOCKED",
              "Commit shapes are unverified claims; deployed source/binary not attested")
        capabilities = supplied.get("observation_capabilities")
        valid_caps = (isinstance(capabilities, list) and
                      all(isinstance(c, str) for c in capabilities))
        missing = ([v for v in matched["required_observation_capabilities"]
                    if v not in capabilities] if valid_caps else list(matched["required_observation_capabilities"]))
        check("observation_capabilities", "UNKNOWN" if capabilities is None else
              "DECLARED" if valid_caps and not missing else "BLOCKED",
              "Missing/unverified observation capabilities: " + ", ".join(missing))
        oracle_ids = supplied.get("oracle_ids")
        valid_oracles = (isinstance(oracle_ids, list) and
                         all(isinstance(x, str) for x in oracle_ids))
        lacking = ([v for v in matched["required_oracle_ids"] if v not in oracle_ids]
                   if valid_oracles else list(matched["required_oracle_ids"]))
        check("oracle_authority", "UNKNOWN" if oracle_ids is None else
              "DECLARED" if valid_oracles and not lacking else "BLOCKED",
              "Oracle IDs are candidates, never independent approval; missing: " + ", ".join(lacking))
        attribution = matched["source_provenance"]
        has_scope = attribution["case"]["state"] == "EXPLICIT_CITATION_CLAIM" or any(
            x["state"] == "EXPLICIT_CITATION_CLAIM" for x in attribution["steps"].values())
        check("source_attribution", "UNKNOWN" if has_scope and
              supplied.get("source_attribution_confirmed") is None else
              "DECLARED" if has_scope and supplied.get("source_attribution_confirmed") is True
              else "BLOCKED",
              "Missing links are UNKNOWN; citations and confirmed flags are not independent source-byte proof")
        check("authorization", "UNKNOWN" if supplied.get("authorization_claimed") is None
              else "DECLARED" if supplied["authorization_claimed"] is True else "BLOCKED",
              "Operator authorization must be verified by a separate local gate")
        check("character_zone", "UNKNOWN" if supplied.get("character_zone_claimed") is None
              else "DECLARED" if supplied["character_zone_claimed"] is True else "BLOCKED",
              "Character/zone claims do not prove deployed conditions")
        check("lease_ownership", "UNKNOWN" if supplied.get("lease_claimed") is None
              else "DECLARED" if supplied["lease_claimed"] is True else "BLOCKED",
              "Lease identity/cleanup cannot be granted by metadata")
        check("mutation", "BLOCKED" if supplied.get("mutation_requested") is True or
              matched["operation_class"] == "MUTATING_UNSUPPORTED" else "DECLARED",
              "Mutation unsupported; no operation is dispatched")
        # A bad canonical base fingerprint is a hard block. Absent source bytes
        # remain UNKNOWN even if all optional caller claims happen to match.
        check("source_revision", "BLOCKED" if matched["compatibility_state"] == "BLOCKED"
              else "UNKNOWN", "No independently rehashed source or deployed revision")
    state = "BLOCKED" if any(x["state"] == "BLOCKED" for x in checks) else "UNKNOWN"
    return {"feature_id": feature_id, "scenario_id": scenario_id,
            "scenario": matched, "preflight_state": state,
            "checks": checks, "missing_dependencies":
                [x["id"] for x in checks if x["state"] != "DECLARED"],
            "claims_authority": "UNVERIFIED_PREVIEW_ONLY",
            "oracle_authority": "NOT_ESTABLISHED",
            "execution_status": "NOT_AUTHORIZED", "execution_enabled": False,
            "task_admission_supported": False, "persisted": False,
            "note": "Advisory only. No result grants execution; #105/#47 approval and local operator checks remain separate."}
