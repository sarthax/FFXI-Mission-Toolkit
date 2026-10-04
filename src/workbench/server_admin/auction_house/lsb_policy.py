"""Read-only LandSandBoat Auction House policy discovery."""
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

def listing_fee(policy: LSBPolicy, *, price: int, stack: bool) -> int | None:
    if not policy.policy_ready:
        return None
    base = float(policy.values["AH_BASE_FEE_STACKS" if stack else "AH_BASE_FEE_SINGLE"])
    rate = float(policy.values["AH_TAX_RATE_STACKS" if stack else "AH_TAX_RATE_SINGLE"])
    maximum = int(policy.values["AH_MAX_FEE"])
    return max(0, min(int(base + (int(price) * rate / 100.0)), maximum))
