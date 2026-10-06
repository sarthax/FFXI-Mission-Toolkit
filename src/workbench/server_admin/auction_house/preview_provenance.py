"""Normalized provenance for read-only Auction House previews across LSB, DSP, and Topaz."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import os
from typing import Any
from uuid import uuid4

PROVENANCE_VERSION = "ah-preview-provenance-v2"
DEFAULT_PREVIEW_TTL_SECONDS = 300
MIN_PREVIEW_TTL_SECONDS = 30
MAX_PREVIEW_TTL_SECONDS = 86400
PREVIEW_TTL_ENV = "FFXI_MISSION_TOOLKIT_AH_PREVIEW_TTL_SECONDS"


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
        return {
            "preview": None if self.preview is None else dict(self.preview),
            "issues": [asdict(issue) for issue in self.issues],
            "binding_ready": self.binding_ready,
            "executor_enabled": False,
            "executable": False,
        }


def preview_ttl_seconds() -> int:
    """Return the configured validation lifetime, clamped to a bounded safety range."""
    raw = str(os.environ.get(PREVIEW_TTL_ENV, "")).strip()
    if not raw:
        try:
            import settings as _settings
            raw = _settings.get_ah_flag("ah_preview_ttl_seconds")
        except Exception:
            raw = str(DEFAULT_PREVIEW_TTL_SECONDS)
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_PREVIEW_TTL_SECONDS
    return max(MIN_PREVIEW_TTL_SECONDS, min(value, MAX_PREVIEW_TTL_SECONDS))


def _environment_identity(environment: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": environment.get("profile_id"),
        "name": str(environment.get("name") or ""),
        "environment": str(environment.get("environment") or ""),
        "family": str(environment.get("family") or "").strip().lower(),
    }


def _policy_identity(policy_binding: dict[str, Any] | None) -> dict[str, Any]:
    policy = dict(policy_binding or {})
    return {
        "family": str(policy.get("family") or "").strip().lower(),
        "source_kind": policy.get("source_kind"),
        "source_path": policy.get("source_path"),
        "policy_fingerprint": policy.get("policy_fingerprint"),
        "policy_ready": bool(policy.get("policy_ready", False)),
    }


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def make_preview_provenance(
    *,
    environment: dict[str, Any],
    schema_family_hint: str,
    policy_binding: dict[str, Any] | None,
    action: str,
    adapter: str,
    now: datetime | None = None,
    ttl_seconds: int | None = None,
) -> dict[str, Any]:
    """Create the immutable common provenance envelope attached to every AH preview response."""
    created = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    ttl = preview_ttl_seconds() if ttl_seconds is None else max(MIN_PREVIEW_TTL_SECONDS, min(int(ttl_seconds), MAX_PREVIEW_TTL_SECONDS))
    expires = created + timedelta(seconds=ttl)
    return {
        "version": PROVENANCE_VERSION,
        "preview_id": str(uuid4()),
        "audit_id": str(uuid4()),
        "replay_id": str(uuid4()),
        "replay_protection": "consume-on-execute",
        "created_at_utc": created.isoformat().replace("+00:00", "Z"),
        "expires_at_utc": expires.isoformat().replace("+00:00", "Z"),
        "ttl_seconds": ttl,
        "action": str(action or ""),
        "adapter": str(adapter or "unknown"),
        "environment": _environment_identity(environment),
        "schema_family_hint": str(schema_family_hint or "unknown"),
        "policy": _policy_identity(policy_binding),
        "executor_enabled": False,
        "executable": False,
    }


def validate_preview_provenance(
    preview: dict[str, Any],
    *,
    environment: dict[str, Any],
    schema_family_hint: str,
    active_policy_binding: dict[str, Any] | None,
    now: datetime | None = None,
) -> PreviewProvenanceCheck:
    provenance = preview.get("preview_provenance")
    if not isinstance(provenance, dict):
        return PreviewProvenanceCheck(None, [
            PreviewProvenanceIssue("preview_provenance_missing", "Preview has no normalized provenance envelope; regenerate the preview."),
        ])

    env = dict(provenance.get("environment") or {})
    policy = dict(provenance.get("policy") or {})
    issues: list[PreviewProvenanceIssue] = [
        PreviewProvenanceIssue(
            "preview_provenance_snapshot",
            f"Preview {provenance.get('preview_id') or 'unknown'} / audit {provenance.get('audit_id') or 'unknown'} created {provenance.get('created_at_utc') or 'at an unknown time'} for {env.get('name') or 'unknown environment'} / {provenance.get('schema_family_hint') or 'unknown schema'} / policy {str(policy.get('policy_fingerprint') or 'none')[:12]}.",
            False,
        )
    ]
    if provenance.get("version") != PROVENANCE_VERSION:
        issues.append(PreviewProvenanceIssue("preview_provenance_version_mismatch", "Preview provenance version is unsupported; regenerate the preview."))
    for key, code, message in (
        ("preview_id", "preview_id_missing", "Preview provenance is missing its unique preview ID."),
        ("audit_id", "preview_audit_id_missing", "Preview provenance is missing its durable audit ID."),
        ("replay_id", "preview_replay_id_missing", "Preview provenance is missing its one-time replay ID."),
    ):
        if not provenance.get(key):
            issues.append(PreviewProvenanceIssue(code, message))
    if provenance.get("replay_protection") != "consume-on-execute":
        issues.append(PreviewProvenanceIssue("preview_replay_contract_invalid", "Preview replay contract is invalid; regenerate the preview."))

    created = _parse_utc(provenance.get("created_at_utc"))
    expires = _parse_utc(provenance.get("expires_at_utc"))
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if created is None:
        issues.append(PreviewProvenanceIssue("preview_timestamp_invalid", "Preview creation timestamp is missing or invalid."))
    if expires is None:
        issues.append(PreviewProvenanceIssue("preview_expiry_invalid", "Preview expiry timestamp is missing or invalid."))
    elif current >= expires:
        issues.append(PreviewProvenanceIssue("preview_expired", "Preview validation lifetime has expired; generate a fresh preview."))
    if created is not None and expires is not None and expires <= created:
        issues.append(PreviewProvenanceIssue("preview_expiry_window_invalid", "Preview expiry must be later than its creation time."))

    ttl = provenance.get("ttl_seconds")
    if not isinstance(ttl, int) or ttl < MIN_PREVIEW_TTL_SECONDS or ttl > MAX_PREVIEW_TTL_SECONDS:
        issues.append(PreviewProvenanceIssue("preview_ttl_invalid", "Preview validation lifetime is outside the allowed safety range."))
    elif created is not None and expires is not None and abs((expires - created).total_seconds() - ttl) > 1:
        issues.append(PreviewProvenanceIssue("preview_ttl_mismatch", "Preview expiry does not match its declared validation lifetime."))

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
