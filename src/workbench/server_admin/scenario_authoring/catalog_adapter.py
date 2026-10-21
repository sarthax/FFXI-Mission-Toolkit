"""Read-only, DSP-source-only candidate lookup for future manual scenario pickers.

This module never issues a GM command, starts a runner, writes a draft, or
certifies agreement with client DAT/catalog IDs. The caller must provide an
already-configured, trusted local DSP checkout path, never an HTTP user path.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from workbench.server_admin.gm_commands.catalog import catalog_commands
from workbench.server_admin.gm_commands.lookup import lookup


# Deliberate subset of the existing lookup providers. Quest/mission identifiers
# require a second, scoped log key; event/CSID requires zone + entity context.
_SOURCE_FILES = {
    "item": "sql/item_basic.sql",
    "keyitem": "scripts/globals/keyitems.lua",
    "npc": "sql/npc_list.sql",
    "mob": "sql/mob_spawn_points.sql",
    "zone": "sql/zone_settings.sql",
}
_GM_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class CatalogUnavailable(ValueError):
    """The requested source could not be read or returned malformed data."""


def _search_bounds(query: str, limit: int) -> str:
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 64:
        raise ValueError("catalog query must contain 1-64 characters")
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("catalog limit must be 1-50")
    if any(ord(c) < 32 or ord(c) == 127 for c in query):
        raise ValueError("control characters are not allowed in catalog queries")
    return query.strip()


def _safe_name(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 240:
        raise CatalogUnavailable("catalog source has invalid descriptive metadata")
    # The source is displayed as untrusted text, never evaluated or rendered as HTML.
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise CatalogUnavailable("catalog source contains control characters")
    return value.strip()


def search_catalog(server_root: str | Path, kind: str, query: str, *, limit: int = 20) -> dict:
    """Return bounded, unreconciled *source candidates*, never executable bindings.

    No local/client matching, permission inference, or global completeness is
    claimed. Missing source must fail closed, not masquerade as zero matches.
    """
    if kind not in (*_SOURCE_FILES, "gm"):
        raise ValueError("unsupported scenario catalog kind")
    q = _search_bounds(query, limit)
    if kind == "gm":
        choices = _gm_candidates(server_root, q, limit)
    else:
        choices = _id_candidates(server_root, kind, q, limit)
    return {
        "kind": kind,
        "query": q,
        "choices": choices,
        "source_lineage": "configured_local_dsp",
        "source_revision": None,  # version/digest must be attached by caller later
        "completeness": "bounded_catalog_query_not_full_inventory",
        "binding_verified": False,
        "execution_enabled": False,
        "operator_review_required": True,
    }


def _id_candidates(server_root: str | Path, kind: str, query: str, limit: int) -> list[dict]:
    try:
        rows = lookup(server_root, kind, query, limit=limit)
    except (OSError, UnicodeError, ValueError) as exc:
        raise CatalogUnavailable("configured DSP lookup source unavailable") from exc
    if not isinstance(rows, list):
        raise CatalogUnavailable("DSP lookup returned malformed rows")
    counts: Counter[int] = Counter()
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get("id")) is not int or row["id"] < 0:
            raise CatalogUnavailable("DSP lookup returned invalid identifier")
        item_id = row["id"]
        name = _safe_name(row.get("name"))
        counts[item_id] += 1
        cleaned.append((item_id, name))
    return [
        {
            "kind": kind,
            "id": item_id,
            "name": name,
            "source_path": _SOURCE_FILES[kind],
            "identity_status": "unreconciled_source_candidate",
            "duplicate_id_in_results": counts[item_id] > 1,
            "binding_verified": False,
            "execution_enabled": False,
            "operator_review_required": True,
        }
        for item_id, name in cleaned
    ]


def _gm_candidates(server_root: str | Path, query: str, limit: int) -> list[dict]:
    try:
        # Reuse the existing descriptor parser; intentionally do not call
        # command_preview(), any transport, or a permission/authorization API.
        rows = catalog_commands(server_root)
    except (OSError, UnicodeError, ValueError) as exc:
        raise CatalogUnavailable("configured DSP GM command source unavailable") from exc
    if not isinstance(rows, list):
        raise CatalogUnavailable("GM catalog returned malformed rows")
    matches = []
    search = query.casefold()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            raise CatalogUnavailable("GM catalog returned malformed command")
        name = row["name"]
        if not _GM_NAME.fullmatch(name):
            raise CatalogUnavailable("GM catalog returned invalid command identity")
        description = row.get("description") or ""
        if not isinstance(description, str):
            raise CatalogUnavailable("GM catalog returned invalid description")
        if search not in name.casefold() and search not in description.casefold():
            continue
        declared_permission = row.get("permission")
        if declared_permission is not None and (
            type(declared_permission) is not int or declared_permission < 0
        ):
            raise CatalogUnavailable("GM catalog returned invalid permission metadata")
        # Never forward command/usage/params as a runnable expression.
        matches.append({
            "kind": "gm",
            "name": name,
            "description": _safe_name(description) if description else "",
            "category": _safe_name(row.get("category")),
            "source_path": "scripts/commands/" + name + ".lua",
            "permission_declared": declared_permission,
            "catalog_classification": row.get("classification", "unreviewed")
                if row.get("classification") in {"unreviewed", "diagnostic_candidate"}
                else "unreviewed",
            "identity_status": "unreconciled_source_candidate",
            "binding_verified": False,
            "execution_enabled": False,
            "operator_review_required": True,
        })
        if len(matches) >= limit:
            break
    return matches
