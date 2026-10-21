"""Bounded, URL-only breadcrumbs for read-only Feature Trace navigation.

These IDs are browser navigation history, NOT source-verified graph paths.
No SQLite writes, persistent server state, identity joins or inferred edges.
"""
from __future__ import annotations

import json
from typing import Sequence

MAX_TRAIL_ITEMS = 8
MAX_TRAIL_CHARS = 2600
MAX_NODE_CHARS = 240


def _valid_node_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= MAX_NODE_CHARS
        and value == value.strip()
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def parse_trail(raw: str | None) -> tuple[str, ...]:
    """Untrusted URL input is either a bounded sequence of IDs or no trail."""
    if not raw or not isinstance(raw, str) or len(raw) > MAX_TRAIL_CHARS:
        return ()
    try:
        ids = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(ids, list) or not all(_valid_node_id(value) for value in ids):
        return ()
    return tuple(ids[-MAX_TRAIL_ITEMS:])


def encode_trail(ids: Sequence[str]) -> str:
    """Return compact JSON; Jinja must URL-encode when placing it in a link."""
    if not all(_valid_node_id(value) for value in ids):
        raise ValueError("A breadcrumb must be a valid exact node ID")
    return json.dumps(list(ids)[-MAX_TRAIL_ITEMS:], ensure_ascii=False, separators=(",", ":"))


def trail_for_next_root(history: Sequence[str], current_root: str) -> str:
    """Append only the current *selected* trace root for the next navigation."""
    valid = list(history[-MAX_TRAIL_ITEMS:])
    if _valid_node_id(current_root) and (not valid or valid[-1] != current_root):
        valid.append(current_root)
    return encode_trail(valid[-MAX_TRAIL_ITEMS:])


def breadcrumb_links(history: Sequence[str]) -> list[dict]:
    """Each ancestor link carries only the entries preceding that ancestor."""
    return [
        {"node_id": node_id, "trail": encode_trail(history[:position])}
        for position, node_id in enumerate(history)
    ]
