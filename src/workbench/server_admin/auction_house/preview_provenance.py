"""Normalized provenance for read-only Auction House previews across LSB, DSP, and Topaz."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

PROVENANCE_VERSION = "ah-preview-provenance-v1"


@dataclass(frozen=True)
class PreviewProvenanceIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class PreviewProvenanceCheck:
    preview: dict[str, Any] | None
    issues: list[PreviewProvenanceIssue] = field(default_factory=list)

    @property
    def binding_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {"preview": None if self.preview is None else dict(self.preview), "issues": [asdict(issue) for issue in self.issues], "binding_ready": self.binding_ready, "executor_enabled": False, "executable": False}


def _environment_identity(environment: dict[str, Any]) -> dict[str, Any]:
    return {"profile_id": environment.get("profile_id"), "name": str(environment.get("name") or ""), "environment": str(environment.get("environment") or ""), "family": str(environment.get("family") or "").strip().lower()}


def _policy_identity(policy_binding: dict[str, Any] | None) -> dict[str, Any]:
    policy = dict(policy_binding or {})
    return {"family": str(policy.get("family") or "").strip().lower(), "source_kind": policy.get("source_kind"), "source_path": policy.get("source_path"), "policy_fingerprint": policy.get("policy_fingerprint"), "policy_ready": bool(policy.get("policy_ready", False))}


def make_preview_provenance(*, environment: dict[str, Any], schema_family_hint: str, policy_binding: dict[str, Any] | None, action: str, adapter: str) -> dict[str, Any]:
    return {
        "version": PROVENANCE_VERSION,
        "preview_id": str(uuid4()),
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": str(action or ""),
        "adapter": str(adapter or "unknown"),
        "environment": _environment_identity(environment),
        "schema_family_hint": str(schema_family_hint or "unknown"),
        "policy": _policy_identity(policy_binding),
        "executor_enabled": False,
        "executable": False,
    }


def validate_preview_provenance(preview: dict[str, Any], *, environment: dict[str, Any], schema_family_hint: str, active_policy_binding: dict[str, Any] | None) -> PreviewProvenanceCheck:
    provenance = preview.get("preview_provenance")
    if not isinstance(provenance, dict):
        return PreviewProvenanceCheck(None, [PreviewProvenanceIssue("preview_provenance_missing", "Preview has no normalized provenance envelope; regenerate the preview.")])

    env = dict(provenance.get("environment") or {})
    policy = dict(provenance.get("policy") or {})
    issues: list[PreviewProvenanceIssue] = [
        PreviewProvenanceIssue(
            "preview_provenance_snapshot",
            f"Preview {provenance.get('preview_id') or 'unknown'} created {provenance.get('created_at_utc') or 'at an unknown time'} for {env.get('name') or 'unknown environment'} / {provenance.get('schema_family_hint') or 'unknown schema'} / policy {str(policy.get('policy_fingerprint') or 'none')[:12]}.",
            False,
        )
    ]
    if provenance.get("version") != PROVENANCE_VERSION:
        issues.append(PreviewProvenanceIssue("preview_provenance_version_mismatch", "Preview provenance version is unsupported; regenerate the preview."))
    if not provenance.get("preview_id"):
        issues.append(PreviewProvenanceIssue("preview_id_missing", "Preview provenance is missing its unique preview ID."))
    if not provenance.get("created_at_utc"):
        issues.append(PreviewProvenanceIssue("preview_timestamp_missing", "Preview provenance is missing its creation timestamp."))
    if str(provenance.get("action") or "") != str(preview.get("action") or ""):
        issues.append(PreviewProvenanceIssue("preview_action_mismatch", "Preview provenance action does not match the preview payload."))
    if str(provenance.get("adapter") or "") != str(preview.get("adapter") or ""):
        issues.append(PreviewProvenanceIssue("preview_adapter_mismatch", "Preview provenance adapter does not match the preview payload."))
    if env != _environment_identity(environment):
        issues.append(PreviewProvenanceIssue("preview_environment_provenance_mismatch", "Preview provenance was created against a different server environment."))
    if str(provenance.get("schema_family_hint") or "") != str(schema_family_hint or ""):
        issues.append(PreviewProvenanceIssue("preview_schema_provenance_mismatch", "Preview provenance was created against a different Auction House schema family."))

    expected_policy = _policy_identity(active_policy_binding)
    for key in ("family", "source_kind", "source_path", "policy_fingerprint"):
        if policy.get(key) != expected_policy.get(key):
            issues.append(PreviewProvenanceIssue("preview_policy_provenance_mismatch", "Preview provenance policy snapshot no longer matches the active Auction House policy."))
            break
    return PreviewProvenanceCheck(dict(provenance), issues)
