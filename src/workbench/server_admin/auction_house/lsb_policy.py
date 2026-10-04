"""Read-only LandSandBoat Auction House policy discovery and preview binding."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import re
from typing import Any

_KEYS = (
    "AH_BASE_FEE_SINGLE",
    "AH_BASE_FEE_STACKS",
    "AH_TAX_RATE_SINGLE",
    "AH_TAX_RATE_STACKS",
    "AH_MAX_FEE",
    "AH_LIST_LIMIT",
)


@dataclass(frozen=True)
class LSBPolicyIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass(frozen=True)
class LSBPolicy:
    source_path: str | None
    values: dict[str, float | int]
    issues: tuple[LSBPolicyIssue, ...]
    policy_fingerprint: str | None

    @property
    def policy_ready(self) -> bool:
        return not any(issue.blocking for issue in self.issues) and all(key in self.values for key in _KEYS)

    @property
    def binding_ready(self) -> bool:
        return self.policy_ready

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": "lsb",
            "source_path": self.source_path,
            "source_kind": "lsb-map-settings",
            "values": dict(self.values),
            "issues": [asdict(issue) for issue in self.issues],
            "policy_fingerprint": self.policy_fingerprint,
            "policy_ready": self.policy_ready,
            "binding_ready": self.binding_ready,
            "executor_enabled": False,
            "executable": False,
        }


@dataclass(frozen=True)
class LSBPolicyBinding:
    preview: dict[str, Any] | None
    active: LSBPolicy
    issues: tuple[LSBPolicyIssue, ...]

    @property
    def binding_ready(self) -> bool:
        return self.active.policy_ready and not any(issue.blocking for issue in self.issues)

    @property
    def policy_ready(self) -> bool:
        return self.binding_ready

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": "lsb",
            "source_kind": "lsb-map-settings",
            "preview": None if self.preview is None else dict(self.preview),
            "active": self.active.as_dict(),
            "issues": [asdict(issue) for issue in self.issues],
            "binding_ready": self.binding_ready,
            "policy_ready": self.policy_ready,
            "executor_enabled": False,
            "executable": False,
        }


def _fingerprint(values: dict[str, float | int], source_path: str) -> str:
    raw = json.dumps({"source_path": source_path, "values": values}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_lsb_policy(server_root: Path | str) -> LSBPolicy:
    path = Path(server_root) / "settings" / "default" / "map.lua"
    if not path.is_file():
        return LSBPolicy(None, {}, (LSBPolicyIssue("lsb_policy_missing", "LSB settings/default/map.lua was not found."),), None)
    text = path.read_text(encoding="utf-8", errors="replace")
    values: dict[str, float | int] = {}
    issues: list[LSBPolicyIssue] = []
    for key in _KEYS:
        match = re.search(rf"(?m)^\s*{re.escape(key)}\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*,?", text)
        if not match:
            issues.append(LSBPolicyIssue("lsb_policy_setting_missing", f"Required LSB setting {key} was not found."))
            continue
        raw = match.group(1)
        values[key] = float(raw) if "." in raw else int(raw)
    source = str(path)
    return LSBPolicy(source, values, tuple(issues), _fingerprint(values, source) if not issues else None)


def preview_lsb_policy_binding(policy: LSBPolicy) -> dict[str, Any]:
    """Return the immutable policy provenance attached to an LSB preview."""
    return {
        "family": "lsb",
        "source_kind": "lsb-map-settings",
        "source_path": policy.source_path,
        "policy_fingerprint": policy.policy_fingerprint,
        "policy_ready": policy.policy_ready,
        "issues": [asdict(issue) for issue in policy.issues],
        "executor_enabled": False,
        "executable": False,
    }


def validate_lsb_policy_binding(preview_binding: Any, active: LSBPolicy) -> LSBPolicyBinding:
    """Fail closed when a preview is missing its LSB policy provenance or the active policy drifted."""
    preview = dict(preview_binding) if isinstance(preview_binding, dict) else None
    issues: list[LSBPolicyIssue] = []
    if preview is None:
        issues.append(LSBPolicyIssue("lsb_policy_binding_missing", "The LSB preview is not bound to an Auction House policy fingerprint."))
    else:
        if str(preview.get("family") or "").strip().lower() != "lsb":
            issues.append(LSBPolicyIssue("lsb_policy_family_mismatch", "The preview policy binding does not identify LandSandBoat."))
        if str(preview.get("source_kind") or "") != "lsb-map-settings":
            issues.append(LSBPolicyIssue("lsb_policy_source_kind_mismatch", "The preview policy binding uses a different policy source kind."))
        if preview.get("source_path") != active.source_path:
            issues.append(LSBPolicyIssue("lsb_policy_source_changed", "The active LSB Auction House policy source changed after preview creation."))
        if preview.get("policy_fingerprint") != active.policy_fingerprint:
            issues.append(LSBPolicyIssue("lsb_policy_drift", "The active LSB Auction House fee/listing policy changed after preview creation."))
    if not active.policy_ready:
        issues.append(LSBPolicyIssue("lsb_active_policy_unavailable", "The active LSB Auction House policy cannot currently be validated."))
    return LSBPolicyBinding(preview, active, tuple(issues))


def listing_fee(policy: LSBPolicy, *, price: int, stack: bool) -> int | None:
    if not policy.policy_ready:
        return None
    base = float(policy.values["AH_BASE_FEE_STACKS" if stack else "AH_BASE_FEE_SINGLE"])
    rate = float(policy.values["AH_TAX_RATE_STACKS" if stack else "AH_TAX_RATE_SINGLE"])
    maximum = int(policy.values["AH_MAX_FEE"])
    return max(0, min(int(base + (int(price) * rate / 100.0)), maximum))
