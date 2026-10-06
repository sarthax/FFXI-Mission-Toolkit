"""Read-only active-server Auction House policy discovery for legacy DSP/Topaz.

The loader only reads configuration files. It deliberately distinguishes active config from
source-tree defaults/templates so a future executor cannot silently run on assumed values.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

from .invariants import LegacyAuctionPolicy


_REQUIRED_KEYS = (
    "ah_base_fee_single",
    "ah_base_fee_stacks",
    "ah_tax_rate_single",
    "ah_tax_rate_stacks",
    "ah_max_fee",
    "ah_list_limit",
)
_ACTIVE_CANDIDATES = {
    "topaz": ("conf/map.conf",),
    "dsp": ("conf/map_darkstar.conf", "conf/map.conf"),
}
_TEMPLATE_CANDIDATES = {
    "topaz": ("conf/default/map.conf",),
    "dsp": (),
}


@dataclass(frozen=True)
class ConfigPolicyIssue:
    code: str
    message: str
    blocking: bool = True


@dataclass
class ConfigPolicyLoad:
    family: str
    server_root: str
    source_path: str | None = None
    source_kind: str = "missing"
    policy: LegacyAuctionPolicy | None = None
    raw_values: dict[str, str] = field(default_factory=dict)
    policy_fingerprint: str | None = None
    template_paths: tuple[str, ...] = ()
    issues: list[ConfigPolicyIssue] = field(default_factory=list)
    executor_enabled: bool = False

    @property
    def policy_ready(self) -> bool:
        return self.policy is not None and not any(issue.blocking for issue in self.issues)

    @property
    def executable(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "server_root": self.server_root,
            "source_path": self.source_path,
            "source_kind": self.source_kind,
            "policy": None if self.policy is None else asdict(self.policy),
            "raw_values": dict(self.raw_values),
            "policy_fingerprint": self.policy_fingerprint,
            "template_paths": list(self.template_paths),
            "issues": [asdict(issue) for issue in self.issues],
            "policy_ready": self.policy_ready,
            "executor_enabled": False,
            "executable": False,
        }


def _normalize_root(value: Path | str) -> Path:
    path = Path(value).expanduser()
    if path.name.lower() in {"map.conf", "map_darkstar.conf"} and path.parent.name.lower() == "conf":
        return path.parent.parent.resolve()
    if path.name.lower() == "conf":
        return path.parent.resolve()
    return path.resolve()


def _parse_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in _REQUIRED_KEYS:
        match = re.search(rf"(?m)^\s*{re.escape(key)}\s*[:=]\s*([^#;\r\n]+)", text)
        if match:
            values[key] = match.group(1).strip().strip('"').strip("'")
    return values


def _to_policy(values: dict[str, str]) -> LegacyAuctionPolicy:
    policy = LegacyAuctionPolicy(
        base_fee_single=int(values["ah_base_fee_single"]),
        base_fee_stacks=int(values["ah_base_fee_stacks"]),
        tax_rate_single=float(values["ah_tax_rate_single"]),
        tax_rate_stacks=float(values["ah_tax_rate_stacks"]),
        max_fee=int(values["ah_max_fee"]),
        list_limit=int(values["ah_list_limit"]),
    )
    if policy.base_fee_single < 0 or policy.base_fee_stacks < 0:
        raise ValueError("Auction House base fees cannot be negative")
    if policy.tax_rate_single < 0 or policy.tax_rate_stacks < 0:
        raise ValueError("Auction House tax rates cannot be negative")
    if policy.max_fee < 0:
        raise ValueError("Auction House maximum fee cannot be negative")
    if policy.list_limit < 0:
        raise ValueError("Auction House listing limit cannot be negative")
    return policy


def _fingerprint(values: dict[str, str]) -> str:
    canonical = "\n".join(f"{key}={values[key]}" for key in sorted(_REQUIRED_KEYS))
    return sha256(canonical.encode("utf-8")).hexdigest()


def load_active_legacy_policy(*, server_root: Path | str, family: str) -> ConfigPolicyLoad:
    """Load the exact active DSP/Topaz AH policy, failing closed on uncertainty."""
    normalized_family = str(family or "").strip().lower()
    root = _normalize_root(server_root)
    result = ConfigPolicyLoad(family=normalized_family or "unknown", server_root=str(root))

    if normalized_family not in _ACTIVE_CANDIDATES:
        result.issues.append(ConfigPolicyIssue(
            "config_family_unsupported",
            "Active legacy Auction House policy loading requires an explicit DSP or Topaz family.",
        ))
        return result

    templates = tuple(
        str(root / rel) for rel in _TEMPLATE_CANDIDATES[normalized_family] if (root / rel).is_file()
    )
    result.template_paths = templates

    present = [root / rel for rel in _ACTIVE_CANDIDATES[normalized_family] if (root / rel).is_file()]
    if not present:
        detail = ""
        if templates:
            detail = " A source-tree default/template exists, but it is not accepted as active configuration."
        result.issues.append(ConfigPolicyIssue(
            "active_ah_config_missing",
            f"No active {normalized_family.upper()} map configuration was found under {root}.{detail}",
        ))
        return result

    parsed: list[tuple[Path, dict[str, str]]] = []
    for path in present:
        text = path.read_text(encoding="utf-8", errors="ignore")
        values = _parse_values(text)
        if values:
            parsed.append((path, values))

    if not parsed:
        result.issues.append(ConfigPolicyIssue(
            "ah_policy_keys_missing",
            "Active map configuration exists but contains none of the required Auction House policy keys.",
        ))
        return result

    if len(parsed) > 1:
        fingerprints = {tuple(sorted(values.items())) for _, values in parsed}
        if len(fingerprints) > 1:
            result.issues.append(ConfigPolicyIssue(
                "active_ah_config_ambiguous",
                "Multiple active-looking DSP map configurations contain different Auction House policy values.",
            ))
            return result

    source, values = parsed[0]
    result.source_path = str(source)
    result.source_kind = "active"
    if normalized_family == "dsp" and "ah_list_limit" not in values:
        # Stock DSP's map server has no ah_list_limit setting (it exists only in LSB/Topaz), so it
        # enforces no per-seller listing cap; 0 means unlimited in this policy.
        values["ah_list_limit"] = "0"
    result.raw_values = dict(values)
    missing = [key for key in _REQUIRED_KEYS if key not in values]
    if missing:
        result.issues.append(ConfigPolicyIssue(
            "ah_policy_incomplete",
            "Active Auction House policy is missing required setting(s): " + ", ".join(missing),
        ))
        return result

    try:
        result.policy = _to_policy(values)
    except (TypeError, ValueError) as exc:
        result.issues.append(ConfigPolicyIssue("ah_policy_invalid", str(exc)))
        return result

    result.policy_fingerprint = _fingerprint(values)
    return result
