"""Bind preview-only Auction House actions to an exact active legacy AH policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .config_policy import ConfigPolicyLoad


@dataclass(frozen=True)
class PolicyBindingIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class PolicyBindingCheck:
    preview_fingerprint: str | None
    active_fingerprint: str | None
    preview_source_path: str | None
    active_source_path: str | None
    issues: list[PolicyBindingIssue] = field(default_factory=list)
    executor_enabled: bool = False

    @property
    def binding_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues)

    @property
    def executable(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "preview_fingerprint": self.preview_fingerprint,
            "active_fingerprint": self.active_fingerprint,
            "preview_source_path": self.preview_source_path,
            "active_source_path": self.active_source_path,
            "issues": [asdict(issue) for issue in self.issues],
            "binding_ready": self.binding_ready,
            "executor_enabled": False,
            "executable": False,
        }


def preview_policy_binding(policy_load: ConfigPolicyLoad) -> dict[str, Any]:
    """Return serializable policy provenance for a preview response."""
    return {
        "family": policy_load.family,
        "source_path": policy_load.source_path,
        "source_kind": policy_load.source_kind,
        "policy_fingerprint": policy_load.policy_fingerprint,
        "policy_ready": policy_load.policy_ready,
        "issues": [asdict(issue) for issue in policy_load.issues],
        "executor_enabled": False,
        "executable": False,
    }


def validate_preview_policy_binding(preview: dict[str, Any], active: ConfigPolicyLoad) -> PolicyBindingCheck:
    """Reject a preview when its bound AH policy no longer matches the active config."""
    binding = dict(preview.get("policy_binding") or {})
    preview_fingerprint = binding.get("policy_fingerprint")
    preview_source_path = binding.get("source_path")
    issues: list[PolicyBindingIssue] = []

    if not binding:
        issues.append(PolicyBindingIssue(
            "preview_policy_binding_missing",
            "Preview is not bound to an active Auction House policy fingerprint; regenerate the preview.",
        ))
    if not active.policy_ready or not active.policy_fingerprint:
        issues.append(PolicyBindingIssue(
            "active_policy_unavailable",
            "Active Auction House policy cannot be verified; preview validation is blocked.",
        ))
    elif preview_fingerprint and preview_fingerprint != active.policy_fingerprint:
        issues.append(PolicyBindingIssue(
            "auction_policy_drift",
            "Active Auction House policy changed after the preview was generated; regenerate the preview.",
        ))

    if preview_source_path and active.source_path and preview_source_path != active.source_path:
        issues.append(PolicyBindingIssue(
            "auction_policy_source_changed",
            "Active Auction House configuration source changed after preview generation.",
        ))

    preview_family = str(binding.get("family") or "").strip().lower()
    if preview_family and preview_family != str(active.family or "").strip().lower():
        issues.append(PolicyBindingIssue(
            "auction_policy_family_changed",
            "Auction House lineage family changed after preview generation.",
        ))

    return PolicyBindingCheck(
        preview_fingerprint=preview_fingerprint,
        active_fingerprint=active.policy_fingerprint,
        preview_source_path=preview_source_path,
        active_source_path=active.source_path,
        issues=issues,
        executor_enabled=False,
    )
