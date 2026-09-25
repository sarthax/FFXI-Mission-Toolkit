"""Conservative extraction of symbolic entity identities from server source files."""
from __future__ import annotations
import re
from pathlib import Path

_LUA_ASSIGN_RE=re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*,?\s*$")
_YAML_ID_RE=re.compile(r"^\s{2}(\d+):\s*$")
_YAML_SCRIPT_RE=re.compile(r"^\s+script:\s+([^#\s]+)\s*$")


def lua_numeric_symbols(path: Path) -> dict[str,int]:
    """Extract simple SYMBOL = integer assignments; ignores expressions/GetFirstID."""
    result={}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
        m=_LUA_ASSIGN_RE.match(line)
        if m:
            result[m.group(1)]=int(m.group(2))
    return result


def yaml_npc_script_symbols(path: Path) -> dict[str,int]:
    """Map npc YAML script names to IDs only when the script name is unique."""
    candidates: dict[str,list[int]]={}
    current_id=None
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8",errors="ignore").splitlines():
        mid=_YAML_ID_RE.match(line)
        if mid:
            current_id=int(mid.group(1))
            continue
        ms=_YAML_SCRIPT_RE.match(line)
        if ms and current_id is not None:
            candidates.setdefault(ms.group(1),[]).append(current_id)
    return {symbol:ids[0] for symbol,ids in candidates.items() if len(ids)==1}
