"""Bounded read-only command-token evidence for client DAT and executable files.

Exact token boundaries are observations, not proof of parsing or container support.
"""
from __future__ import annotations

import re

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_HITS = 200
COMMAND = re.compile(rb"(?<![A-Za-z0-9_/])/[A-Za-z][A-Za-z0-9_]{1,39}(?![A-Za-z0-9_])")


def command_evidence(data: bytes, query: str = "wardrobe", limit: int = 80) -> dict:
    """Return bounded ASCII slash-command candidates with reproducible offsets.

    Hex context is raw file bytes. No attempt is made to infer a command table,
    executable xrefs, packet support, or a DAT's semantic format.
    """
    if len(data) > MAX_FILE_BYTES:
        return {"status": "skipped", "reason": "file exceeds 64 MiB evidence-scan bound",
                "hits": [], "total": 0}
    if not isinstance(query, str) or len(query) > 40 or not query.isascii():
        raise ValueError("query must be an ASCII string of at most 40 characters")
    limit = max(1, min(int(limit), MAX_HITS))
    term = query.lower().encode("ascii")
    hits = []
    total = 0
    for match in COMMAND.finditer(data):
        token = match.group().decode("ascii")
        if term not in token.lower().encode("ascii"):
            continue
        total += 1
        if len(hits) >= limit:
            continue
        start, end = match.span()
        left, right = max(0, start - 12), min(len(data), end + 12)
        hits.append({
            "token": token,
            "offset": start,
            "offset_hex": f"0x{start:X}",
            "context_start": left,
            "context_hex": data[left:right].hex(" "),
            "terminated_nul": end < len(data) and data[end] == 0,
        })
    return {"status": "scanned", "query": query, "total": total, "hits": hits,
            "truncated": total > len(hits),
            "caution": "Exact bytes only; misses are UNKNOWN, not proof that a command is unsupported."}


def exact_command_probe(data: bytes, command: str) -> dict:
    """Probe a complete slash-command token rather than a substring prefix."""
    if not re.fullmatch(r"/[A-Za-z][A-Za-z0-9_]{1,39}", command):
        raise ValueError("command must be an ASCII slash-command")
    needle = command.encode("ascii")
    hits = []
    pos = 0
    while len(hits) < MAX_HITS:
        pos = data.find(needle, pos)
        if pos == -1:
            break
        before = data[pos - 1] if pos else None
        after_at = pos + len(needle)
        after = data[after_at] if after_at < len(data) else None
        if (before is None or before not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_/") and (
            after is None or after not in b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
        ):
            hits.append({"offset": pos, "offset_hex": f"0x{pos:X}"})
        pos += 1
    return {"found": bool(hits), "count": len(hits), "sample": hits[:5],
            "capped": len(hits) == MAX_HITS}
