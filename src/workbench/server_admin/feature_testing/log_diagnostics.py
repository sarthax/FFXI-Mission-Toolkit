"""Bounded, allowlisted, read-only log diagnostics for the local supervisor."""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import re

SOURCES = {"dsp": "MISSION_TOOLKIT_SUPERVISOR_DSP_LOG",
           "headless": "MISSION_TOOLKIT_SUPERVISOR_HEADLESS_LOG",
           "toolkit": "MISSION_TOOLKIT_SUPERVISOR_TOOLKIT_LOG"}
SECRET = re.compile(r"(?i)(password|authorization|bearer|api[_-]?key|token|secret)(\\s*[:=]\\s*|\\s+)([^\\s,;]+)")
ERROR = re.compile(r"(?i)\\b(error|exception|fatal|traceback|failed)\\b")


def redact(line: str) -> str:
    return SECRET.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", line)


def read_log(source: str, *, errors_only: bool = True, lines: int = 80) -> dict:
    if source not in SOURCES:
        raise ValueError("unknown log source")
    if not isinstance(lines, int) or not 1 <= lines <= 200:
        raise ValueError("invalid line limit")
    configured = os.environ.get(SOURCES[source], "")
    if not configured:
        return {"source": source, "configured": False, "lines": []}
    file = Path(configured)
    if not file.is_absolute() or file.is_symlink() or not file.is_file():
        raise ValueError("configured log must be an absolute regular non-symlink file")
    # Read a bounded tail from binary stream; do not load multi-gigabyte logs.
    with file.open("rb") as handle:
        handle.seek(0, 2)
        end = handle.tell()
        size = min(end, 262144)
        handle.seek(end - size)
        raw = handle.read(size)
    chunk = raw.decode("utf-8", errors="replace")
    if end > size:
        chunk = chunk.partition("\\n")[2]
    candidates = deque(maxlen=lines)
    for entry in chunk.splitlines():
        if not errors_only or ERROR.search(entry):
            candidates.append(redact(entry[:1000]))
    return {"source": source, "configured": True, "truncated_tail": end > size,
            "lines": list(candidates)}
