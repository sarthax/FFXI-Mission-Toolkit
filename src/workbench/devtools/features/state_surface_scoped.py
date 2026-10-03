"""Mission/quest state-surface adapter with exact LSB feature scoping.

Modern LandSandBoat mission/quest sources are definition-oriented (`Mission:new` / `Quest:new`).
For those sources, Character Editor trace should inspect the exact feature definition rather than
all files that happen to mention the same symbol. Legacy DSP/Topaz layouts still fall back to the
older checkout-wide scanner in :mod:`state_surface`.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from workbench.devtools.features.state_surface import (
    StateReference,
    _edit_class,
    _line_refs,
    _state_flow_refs,
    build_state_surface as build_legacy_state_surface,
)
from workbench.devtools.missions.mission_source_catalog import LsbFeatureSourceCatalog


_FEATURE_VAR_ALIAS = re.compile(
    r"local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(quest|mission):getVar\(\s*player\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
)
_FEATURE_VAR_COMPARE = re.compile(
    r"(quest|mission):getVar\(\s*player\s*,\s*['\"]([^'\"]+)['\"]\s*\)\s*"
    r"(==|~=|>=|<=|>|<)\s*(-?\d+)"
)
_FEATURE_VAR_SET = re.compile(
    r"(quest|mission):setVar\(\s*player\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*([^\)]+)\)"
)
_SECTION_VAR_COMPARE = re.compile(
    r"\bvars\.([A-Za-z_][A-Za-z0-9_]*)\s*(==|~=|>=|<=|>|<)\s*(-?\d+)"
)
_QUEST_STATUS_COMPARE = re.compile(
    r"\bstatus\s*(==|~=)\s*xi\.questStatus\.([A-Z0-9_]+)"
)
_DSL_EVENT = re.compile(
    r"(quest|mission):(progressEvent|event|progressCutscene)\(\s*(\d+)"
)
_DSL_LIFECYCLE = re.compile(r"(quest|mission):(begin|complete)\(\s*player\s*\)")
_EVENT_FINISH = re.compile(r"\[(\d+)\]\s*=\s*function\(\s*player\s*,\s*csid")


def _clean_lines(text: str) -> list[str]:
    """Remove ordinary line comments while retaining string literals needed by DSL regexes."""
    return [raw.split("--", 1)[0] for raw in text.splitlines()]


def _dsl_refs(
    text: str,
    source_path: str,
    *,
    kind: str,
    symbol: str | None,
) -> list[StateReference]:
    refs: list[StateReference] = []
    lines = _clean_lines(text)
    aliases: dict[str, tuple[str, str]] = {}
    for line in lines:
        for match in _FEATURE_VAR_ALIAS.finditer(line):
            alias, owner, key = match.groups()
            aliases[alias] = (owner, key)

    for line_no, (raw, line) in enumerate(zip(text.splitlines(), lines), 1):
        if not line.strip():
            continue

        for match in _FEATURE_VAR_COMPARE.finditer(line):
            owner, key, operator, expected = match.groups()
            state_type = f"{owner}_var"
            refs.append(StateReference(
                state_type, key, "require", None, source_path, line_no, raw.strip(),
                scope="FEATURE_STATE", edit_class="derived_runtime",
                expectation_operator=operator, expectation_value=expected,
            ))

        for alias, (owner, key) in aliases.items():
            match = re.search(rf"\b{re.escape(alias)}\s*(==|~=|>=|<=|>|<)\s*(-?\d+)", line)
            if match:
                refs.append(StateReference(
                    f"{owner}_var", key, "require", None, source_path, line_no, raw.strip(),
                    scope="FEATURE_STATE", edit_class="derived_runtime",
                    expectation_operator=match.group(1), expectation_value=match.group(2),
                ))

        for match in _SECTION_VAR_COMPARE.finditer(line):
            key, operator, expected = match.groups()
            state_type = "quest_var" if kind == "quest" else "mission_var"
            refs.append(StateReference(
                state_type, key, "require", None, source_path, line_no, raw.strip(),
                scope="FEATURE_STATE", edit_class="derived_runtime",
                expectation_operator=operator, expectation_value=expected,
            ))

        for match in _FEATURE_VAR_SET.finditer(line):
            owner, key, value = match.groups()
            refs.append(StateReference(
                f"{owner}_var", key, "set", value.strip(), source_path, line_no, raw.strip(),
                scope="FEATURE_STATE", edit_class="derived_runtime",
            ))

        if kind == "quest":
            for match in _QUEST_STATUS_COMPARE.finditer(line):
                operator, expected = match.groups()
                refs.append(StateReference(
                    "quest_status", "status", "require", None, source_path, line_no, raw.strip(),
                    scope="FEATURE_STATE", edit_class="derived_runtime",
                    expectation_operator=operator, expectation_value=expected,
                ))

        for match in _DSL_EVENT.finditer(line):
            owner, method, event_id = match.groups()
            if owner != kind:
                continue
            refs.append(StateReference(
                "event", event_id, "start", method, source_path, line_no, raw.strip(),
                scope="FEATURE_EVENT", edit_class="derived_runtime",
            ))

        # Event-finish keys are part of the target feature's own lifecycle even when the event was
        # entered by a bare integer return from onZoneIn rather than quest:event/mission:event.
        for match in _EVENT_FINISH.finditer(line):
            refs.append(StateReference(
                "event", match.group(1), "finish", None, source_path, line_no, raw.strip(),
                scope="FEATURE_EVENT", edit_class="derived_runtime",
            ))

        for match in _DSL_LIFECYCLE.finditer(line):
            owner, method = match.groups()
            if owner != kind:
                continue
            operation = "activate" if method == "begin" else "complete"
            refs.append(StateReference(
                kind, symbol or "SELF", operation, None, source_path, line_no, raw.strip(),
                scope="FEATURE_STATE", edit_class=_edit_class(kind, operation),
            ))

    return refs


def _dedupe(refs: list[StateReference]) -> list[StateReference]:
    unique: dict[tuple[Any, ...], StateReference] = {}
    for ref in refs:
        key = (
            ref.state_type,
            ref.key,
            ref.operation,
            ref.value,
            ref.source_path,
            ref.source_line,
            ref.expectation_operator,
            ref.expectation_value,
        )
        unique[key] = ref
    return sorted(
        unique.values(),
        key=lambda row: (row.state_type, row.key, row.source_path, row.source_line, row.operation),
    )


def _surface_from_exact_lsb_source(
    root: Path,
    *,
    kind: str,
    area_id: int,
    entry_id: int,
    symbol: str,
    label: str | None,
) -> dict[str, Any] | None:
    scripts = root / "scripts"
    if not scripts.is_dir():
        return None

    catalog = LsbFeatureSourceCatalog(scripts)
    subject = f"{kind}:{symbol}"
    source = catalog.source_for(subject)
    if source is None or source.kind != kind:
        return None

    path = Path(source.path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    try:
        rel = str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        rel = str(path).replace("\\", "/")

    feature_id = f"{kind}:{area_id}:{entry_id}"
    refs = _state_flow_refs(text, rel, feature_id, label or symbol)
    refs.extend(_line_refs(text, rel))
    refs.extend(_dsl_refs(text, rel, kind=kind, symbol=symbol))
    refs = _dedupe(refs)

    groups: dict[str, list[dict[str, Any]]] = {}
    for ref in refs:
        groups.setdefault(ref.state_type, []).append(ref.as_dict())

    return {
        "target": {
            "kind": kind,
            "area_id": int(area_id),
            "entry_id": int(entry_id),
            "symbol": symbol,
            "label": label or symbol,
        },
        "source_root": str(root),
        "files": [{"path": rel, "reference_count": len(refs), "role": "feature_definition"}],
        "references": [ref.as_dict() for ref in refs],
        "groups": groups,
        "summary": {
            "scripts_scanned": 1,
            "scripts_matched": 1,
            "scripts_returned": 1,
            "reference_count": len(refs),
            "state_type_count": len(groups),
            "verified_editor_count": sum(1 for ref in refs if ref.edit_class == "verified_editor"),
            "advanced_editable_count": sum(1 for ref in refs if ref.edit_class == "advanced_editable"),
            "derived_runtime_count": sum(1 for ref in refs if ref.edit_class == "derived_runtime"),
            "truncated": False,
            "selection_mode": "exact_lsb_definition",
            "catalog_subject": subject,
        },
        "limitations": [
            "Exact LSB definition scope is used; files that merely mention this mission/quest are excluded from the primary surface.",
            "Static source references do not prove runtime ordering beyond structurally modeled mission/quest transitions.",
            "Dynamic variable names and helper-generated IDs may not be discovered.",
            "Editing a persisted flag may not reproduce scripted rewards, variables, or side effects.",
        ],
    }


def build_state_surface(
    server_root: Path | str,
    *,
    kind: str,
    area_id: int,
    entry_id: int,
    symbol: str | None = None,
    label: str | None = None,
    max_files: int = 200,
) -> dict[str, Any]:
    """Build a mission/quest surface, preferring exact modern-LSB feature definitions."""
    root = Path(server_root).resolve()
    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind not in {"mission", "quest"}:
        raise ValueError("kind must be mission or quest")

    if symbol:
        exact = _surface_from_exact_lsb_source(
            root,
            kind=normalized_kind,
            area_id=area_id,
            entry_id=entry_id,
            symbol=str(symbol),
            label=label,
        )
        if exact is not None:
            return exact

    fallback = build_legacy_state_surface(
        root,
        kind=normalized_kind,
        area_id=area_id,
        entry_id=entry_id,
        symbol=symbol,
        label=label,
        max_files=max_files,
    )
    fallback.setdefault("summary", {})["selection_mode"] = "legacy_reference_scan"
    return fallback
