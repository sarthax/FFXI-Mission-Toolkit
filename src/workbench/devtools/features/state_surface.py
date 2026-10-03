"""Mission/quest state-surface extraction for Feature Trace.

This module is intentionally source-evidence driven.  It never executes Lua and it does not claim
that a textual reference proves runtime ordering.  A surface contains only checkout-local scripts
that explicitly reference the requested mission/quest symbol (or an exact numeric API reference),
then classifies the state/API accesses found inside those files.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import re
from typing import Any, Iterable

from workbench.devtools.behavior.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior


@dataclass(frozen=True)
class StateReference:
    state_type: str
    key: str
    operation: str
    value: str | None
    source_path: str
    source_line: int
    source_text: str
    hook: str | None = None
    scope: str | None = None
    edit_class: str = "derived_runtime"
    expectation_operator: str | None = None
    expectation_value: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_CHAR_COMPARE = re.compile(
    r"player:get(?:Char)?Var\(\s*['\"]([^'\"]+)['\"]\s*\)\s*(==|~=|>=|<=|>|<)\s*"
    r"(-?\d+|true|false|['\"][^'\"]+['\"])"
)
_KEY_ITEM = re.compile(
    r"player:(hasKeyItem|addKeyItem|delKeyItem)\(\s*(?:xi\.keyItem|tpz\.ki)\.([A-Z0-9_]+)"
)
_KEY_ITEM_NPCUTIL = re.compile(
    r"npcUtil\.(giveKeyItem)\(\s*player\s*,\s*(?:xi\.keyItem|tpz\.ki)\.([A-Z0-9_]+)"
)
_ITEM = re.compile(
    r"player:(hasItem|addItem|delItem)\(\s*((?:xi|tpz)\.item\.([A-Z0-9_]+)|\d+)"
)
_ITEM_NPCUTIL = re.compile(r"npcUtil\.(giveItem)\(\s*player\s*,\s*([^,\)]+)")
_MISSION_CALL = re.compile(r"player:(getCurrentMission|addMission|completeMission)\(([^\)]*)\)")
_QUEST_CALL = re.compile(r"player:(getQuestStatus|addQuest|completeQuest|hasCompletedQuest)\(([^\)]*)\)")
_EVENT = re.compile(r"player:(startEvent|updateEvent|updateEventString)\(\s*([^\)]*)\)")
_TITLE = re.compile(r"player:(addTitle|delTitle|hasTitle)\(\s*([^\)]*)\)")
_GIL = re.compile(r"player:(addGil|delGil)\(\s*([^\)]*)\)")
_FAME = re.compile(r"player:(getFameLevel|getFame|addFame)\(\s*([^\)]*)\)")


def _edit_class(state_type: str, operation: str) -> str:
    if state_type in {"mission", "quest", "key_item", "title"}:
        return "verified_editor"
    if state_type == "charvar":
        return "advanced_editable"
    if state_type == "item" and operation in {"grant", "remove", "require"}:
        return "verified_editor"
    return "derived_runtime"


def _op(method: str) -> str:
    mapping = {
        "getCharVar": "read", "getVar": "read", "setCharVar": "set", "setVar": "set",
        "hasKeyItem": "require", "addKeyItem": "grant", "delKeyItem": "remove", "giveKeyItem": "grant",
        "hasItem": "require", "addItem": "grant", "delItem": "remove", "giveItem": "grant",
        "getCurrentMission": "read", "addMission": "activate", "completeMission": "complete",
        "getQuestStatus": "read", "hasCompletedQuest": "read", "addQuest": "activate", "completeQuest": "complete",
        "startEvent": "start", "updateEvent": "update", "updateEventString": "update",
        "addTitle": "grant", "delTitle": "remove", "hasTitle": "require",
        "addGil": "grant", "delGil": "remove", "getFame": "read", "getFameLevel": "read", "addFame": "grant",
    }
    return mapping.get(method, method)


def _state_flow_refs(text: str, source_path: str, feature_id: str, subject: str) -> list[StateReference]:
    refs: list[StateReference] = []
    try:
        behavior = extract_lsb_scripted_behavior(
            text,
            feature_id=feature_id,
            subject=subject,
            zone="STATE_SURFACE",
            source_path=source_path,
        )
    except Exception:
        return refs
    for rule in behavior.rules:
        if rule.kind != "state_flow":
            continue
        for condition in rule.conditions:
            if condition.operator != "READS_STATE":
                continue
            meta = dict(condition.metadata or {})
            scope = str(meta.get("scope") or "")
            state_id = str(condition.subject or "")
            key = state_id.rsplit(":", 1)[-1]
            state_type = "charvar" if scope == "PLAYER_CHAR" else "runtime_state"
            refs.append(StateReference(
                state_type=state_type,
                key=key,
                operation="read",
                value=str(condition.value) if condition.value is not None else None,
                source_path=source_path,
                source_line=int(meta.get("source_line") or 0),
                source_text=str(meta.get("source_line_text") or ""),
                hook=rule.hook,
                scope=scope or None,
                edit_class=_edit_class(state_type, "read"),
            ))
        for effect in rule.effects:
            if effect.effect != "WRITE_STATE":
                continue
            meta = dict(effect.metadata or {})
            scope = str(meta.get("scope") or "")
            state_id = str(effect.target or "")
            key = state_id.rsplit(":", 1)[-1]
            state_type = "charvar" if scope == "PLAYER_CHAR" else "runtime_state"
            refs.append(StateReference(
                state_type=state_type,
                key=key,
                operation="set",
                value=str(effect.value) if effect.value is not None else None,
                source_path=source_path,
                source_line=int(meta.get("source_line") or 0),
                source_text=str(meta.get("source_line_text") or ""),
                hook=rule.hook,
                scope=scope or None,
                edit_class=_edit_class(state_type, "set"),
            ))
    return refs


def _line_refs(text: str, source_path: str) -> list[StateReference]:
    refs: list[StateReference] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.split("--", 1)[0]
        if not line.strip():
            continue

        for match in _CHAR_COMPARE.finditer(line):
            key, operator, expected = match.groups()
            refs.append(StateReference(
                "charvar", key, "require", None, source_path, line_no, raw.strip(),
                scope="PLAYER_CHAR", edit_class="advanced_editable",
                expectation_operator=operator, expectation_value=expected.strip("'\""),
            ))

        for match in _KEY_ITEM.finditer(line):
            method, symbol = match.groups()
            refs.append(StateReference("key_item", symbol, _op(method), None, source_path, line_no, raw.strip(), edit_class="verified_editor"))
        for match in _KEY_ITEM_NPCUTIL.finditer(line):
            method, symbol = match.groups()
            refs.append(StateReference("key_item", symbol, _op(method), None, source_path, line_no, raw.strip(), edit_class="verified_editor"))

        for match in _ITEM.finditer(line):
            method, raw_key, symbol = match.groups()
            key = symbol or raw_key
            refs.append(StateReference("item", key, _op(method), None, source_path, line_no, raw.strip(), edit_class="verified_editor"))
        for match in _ITEM_NPCUTIL.finditer(line):
            method, raw_key = match.groups()
            refs.append(StateReference("item", raw_key.strip(), _op(method), None, source_path, line_no, raw.strip(), edit_class="verified_editor"))

        for regex, state_type in ((_MISSION_CALL, "mission"), (_QUEST_CALL, "quest"), (_EVENT, "event"), (_TITLE, "title"), (_GIL, "gil"), (_FAME, "fame")):
            for match in regex.finditer(line):
                method, args = match.groups()
                refs.append(StateReference(
                    state_type, args.strip(), _op(method), None, source_path, line_no, raw.strip(),
                    edit_class=_edit_class(state_type, _op(method)),
                ))
    return refs


def _matches_target(text: str, *, kind: str, area_id: int, entry_id: int, symbol: str | None) -> bool:
    if symbol and re.search(rf"\b{re.escape(symbol)}\b", text):
        return True
    # Numeric matching is intentionally narrow: require a mission/quest API call on the same line.
    api = "Mission" if kind == "mission" else "Quest"
    for line in text.splitlines():
        if str(entry_id) not in line:
            continue
        if re.search(rf"(?:getCurrent{api}|add{api}|complete{api}|get{api}Status|hasCompleted{api})\s*\(", line):
            return True
    return False


def _candidate_lua_files(root: Path) -> Iterable[Path]:
    scripts = root / "scripts"
    if not scripts.is_dir():
        return ()
    return scripts.rglob("*.lua")


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
    """Discover checkout-local state/API references for one mission or quest."""
    root = Path(server_root).resolve()
    kind = str(kind or "").strip().lower()
    if kind not in {"mission", "quest"}:
        raise ValueError("kind must be mission or quest")

    files: list[dict[str, Any]] = []
    references: list[StateReference] = []
    scanned = 0
    matched = 0
    truncated = False

    for path in _candidate_lua_files(root):
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _matches_target(text, kind=kind, area_id=area_id, entry_id=entry_id, symbol=symbol):
            continue
        matched += 1
        if len(files) >= max_files:
            truncated = True
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        feature_id = f"{kind}:{area_id}:{entry_id}"
        refs = _state_flow_refs(text, rel, feature_id, label or symbol or feature_id)
        refs.extend(_line_refs(text, rel))
        references.extend(refs)
        files.append({"path": rel, "reference_count": len(refs)})

    # Deduplicate exact source facts; the generic behavior extractor and explicit patterns can
    # intentionally overlap for charvars.
    unique: dict[tuple[Any, ...], StateReference] = {}
    for ref in references:
        key = (
            ref.state_type, ref.key, ref.operation, ref.value, ref.source_path, ref.source_line,
            ref.expectation_operator, ref.expectation_value,
        )
        unique[key] = ref
    refs = sorted(unique.values(), key=lambda row: (row.state_type, row.key, row.source_path, row.source_line, row.operation))

    state_groups: dict[str, list[dict[str, Any]]] = {}
    for ref in refs:
        state_groups.setdefault(ref.state_type, []).append(ref.as_dict())

    return {
        "target": {
            "kind": kind,
            "area_id": int(area_id),
            "entry_id": int(entry_id),
            "symbol": symbol,
            "label": label or symbol or f"{kind.title()} {entry_id}",
        },
        "source_root": str(root),
        "files": files,
        "references": [ref.as_dict() for ref in refs],
        "groups": state_groups,
        "summary": {
            "scripts_scanned": scanned,
            "scripts_matched": matched,
            "scripts_returned": len(files),
            "reference_count": len(refs),
            "state_type_count": len(state_groups),
            "verified_editor_count": sum(1 for ref in refs if ref.edit_class == "verified_editor"),
            "advanced_editable_count": sum(1 for ref in refs if ref.edit_class == "advanced_editable"),
            "derived_runtime_count": sum(1 for ref in refs if ref.edit_class == "derived_runtime"),
            "truncated": truncated,
        },
        "limitations": [
            "Static source references do not prove runtime ordering or reachability.",
            "Dynamic variable names and helper-generated IDs may not be discovered.",
            "Editing a persisted flag may not reproduce scripted rewards, variables, or side effects.",
        ],
    }
