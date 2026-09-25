"""Conservative extraction of modern LSB battlefield policy surfaces."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class LsbBattlefieldPolicySurface:
    resolved_fields: dict[str, Any]
    unresolved_fields: dict[str, str]


_INT_FIELD_PATTERNS={
    "party_size":re.compile(r"\bmaxPlayers\s*=\s*(\d+)\s*,"),
}
_BOOL_FIELD_PATTERNS={
    "is_mission":re.compile(r"\bisMission\s*=\s*(true|false)\s*,",re.I),
}
_TIME_MINUTES_RE=re.compile(r"\btimeLimit\s*=\s*utils\.minutes\(\s*(\d+)\s*\)\s*,")
_LEVEL_CAP_RE=re.compile(r"\blevelCap\s*=\s*([^,\n]+)\s*,")


def extract_lsb_battlefield_policy(lua_text: str) -> LsbBattlefieldPolicySurface:
    resolved={}
    unresolved={}

    for logical_name,pattern in _INT_FIELD_PATTERNS.items():
        match=pattern.search(lua_text)
        if match:
            resolved[logical_name]=int(match.group(1))

    for logical_name,pattern in _BOOL_FIELD_PATTERNS.items():
        match=pattern.search(lua_text)
        if match:
            resolved[logical_name]=match.group(1).lower()=="true"

    match=_TIME_MINUTES_RE.search(lua_text)
    if match:
        resolved["time_limit"]=int(match.group(1))*60

    match=_LEVEL_CAP_RE.search(lua_text)
    if match:
        expression=match.group(1).strip()
        if re.fullmatch(r"\d+",expression):
            resolved["level_cap"]=int(expression)
        else:
            unresolved["level_cap"]=expression

    return LsbBattlefieldPolicySurface(
        resolved_fields=resolved,
        unresolved_fields=unresolved,
    )


def extract_lsb_mission_level_cap(policy_text: str, battlefield_symbol: str) -> int | None:
    """Resolve the era mission-level-cap table for one explicit battlefield symbol."""
    symbol=re.escape(battlefield_symbol)
    pattern=re.compile(rf"\b{symbol}\s*,\s*(\d+)\b")
    match=pattern.search(policy_text)
    return int(match.group(1)) if match else None
