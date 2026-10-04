"""Conservative DSP/Topaz mission and quest progression normalization.

Legacy server trees generally spread progression across zone/NPC scripts instead of one
Mission:new/Quest:new definition.  This adapter consumes only files already selected by the
State Surface target scan and projects literal handler guards/effects into MissionStateMachine.
It never executes Lua and intentionally leaves unsupported runtime expressions unresolved.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

from .mission_lsb_extract import _balanced_function_blocks, _handler_paths
from .mission_state_machine import (
    DependencyGate, EventIdentity, MissionState, MissionStateMachine, MissionTransition,
    StateChannel, StateCondition, TransitionEffect,
)

_HANDLER = re.compile(r"(?:function\s+)?(onTrigger|onTrade|onEventFinish|onZoneIn|onMobDeath)\b[^\n]*?(?:=\s*function|\()")
_START_EVENT = re.compile(r"player:startEvent\(\s*(\d+)")
_CSID = re.compile(r"\bcsid\s*==\s*(\d+)")
_CHAR_CMP = re.compile(r"player:get(?:Char)?Var\(\s*['\"]([^'\"]+)['\"]\s*\)\s*(==|~=|<=|>=|<|>)\s*(-?\d+)")
_CHAR_SET = re.compile(r"player:set(?:Char)?Var\(\s*['\"]([^'\"]+)['\"]\s*,\s*(-?\d+)\s*\)")
_HAS_KI = re.compile(r"(?<!not\s)player:hasKeyItem\(\s*(?:tpz\.ki|xi\.keyItem)\.([A-Z0-9_]+)\s*\)")
_LACKS_KI = re.compile(r"not\s+player:hasKeyItem\(\s*(?:tpz\.ki|xi\.keyItem)\.([A-Z0-9_]+)\s*\)")
_ADD_KI = re.compile(r"(?:player:addKeyItem|npcUtil\.giveKeyItem)\(\s*(?:player\s*,\s*)?(?:tpz\.ki|xi\.keyItem)\.([A-Z0-9_]+)")
_DEL_KI = re.compile(r"player:delKeyItem\(\s*(?:tpz\.ki|xi\.keyItem)\.([A-Z0-9_]+)")
_ADD_ITEM = re.compile(r"player:addItem\(\s*((?:tpz|xi)\.item\.[A-Z0-9_]+|\d+)")
_DEL_ITEM = re.compile(r"player:delItem\(\s*((?:tpz|xi)\.item\.[A-Z0-9_]+|\d+)")
_TITLE = re.compile(r"player:addTitle\(\s*(?:tpz\.title|xi\.title)\.([A-Z0-9_]+)")
_COMPLETE_MISSION = re.compile(r"player:completeMission\(([^\)]*)\)")
_ADD_MISSION = re.compile(r"player:addMission\(([^\)]*)\)")
_COMPLETE_QUEST = re.compile(r"player:completeQuest\(([^\)]*)\)")
_ADD_QUEST = re.compile(r"player:addQuest\(([^\)]*)\)")
_OP = {"==":"EQ", "~=":"NE", "<":"LT", "<=":"LE", ">":"GT", ">=":"GE"}
_TRIGGER = {"onTrigger":"NPC_INTERACT", "onTrade":"TRADE", "onEventFinish":"EVENT_FINISH", "onZoneIn":"ZONE_IN", "onMobDeath":"MOB_DEATH"}


def _zone_actor(path: Path) -> tuple[str, str | None]:
    parts = path.parts
    zone = "LEGACY_SCRIPT"
    actor = None
    try:
        idx = parts.index("zones")
        zone = parts[idx + 1].upper()
        if idx + 2 < len(parts) and parts[idx + 2] in {"npcs", "mobs"}:
            actor = path.stem
    except (ValueError, IndexError):
        pass
    return zone, actor


def _conditions(texts: Iterable[str]) -> tuple[StateCondition, ...]:
    joined = "\n".join(texts)
    rows: list[StateCondition] = []
    for key, op, value in _CHAR_CMP.findall(joined):
        rows.append(StateCondition(f"charvar:{key}", _OP[op], int(value)))
    lacked = set(_LACKS_KI.findall(joined))
    for symbol in sorted(lacked):
        rows.append(StateCondition(f"key_item:{symbol}", "LACKS", True))
    for symbol in sorted(set(_HAS_KI.findall(joined)) - lacked):
        rows.append(StateCondition(f"key_item:{symbol}", "HAS", True))
    # Runtime-only event identity is represented by EventIdentity, not as a DB-state condition.
    unique = []
    for row in rows:
        if row not in unique:
            unique.append(row)
    return tuple(unique)


def _effects(body: str) -> tuple[TransitionEffect, ...]:
    rows: list[TransitionEffect] = []
    for key, value in _CHAR_SET.findall(body):
        rows.append(TransitionEffect("SET_VAR", f"charvar:{key}", int(value)))
    for symbol in _ADD_KI.findall(body):
        rows.append(TransitionEffect("GRANT", f"key_item:{symbol}"))
    for symbol in _DEL_KI.findall(body):
        rows.append(TransitionEffect("REMOVE", f"key_item:{symbol}"))
    for item in _ADD_ITEM.findall(body):
        rows.append(TransitionEffect("GRANT", f"item:{item}"))
    for item in _DEL_ITEM.findall(body):
        rows.append(TransitionEffect("REMOVE", f"item:{item}"))
    for symbol in _TITLE.findall(body):
        rows.append(TransitionEffect("GRANT_TITLE", f"title:{symbol}"))
    for args in _ADD_MISSION.findall(body):
        rows.append(TransitionEffect("START", f"mission:{args.strip()}"))
    for args in _COMPLETE_MISSION.findall(body):
        rows.append(TransitionEffect("COMPLETE", f"mission:{args.strip()}"))
    for args in _ADD_QUEST.findall(body):
        rows.append(TransitionEffect("START", f"quest:{args.strip()}"))
    for args in _COMPLETE_QUEST.findall(body):
        rows.append(TransitionEffect("COMPLETE", f"quest:{args.strip()}"))
    unique = []
    for row in rows:
        if row not in unique:
            unique.append(row)
    return tuple(unique)


def extract_legacy_progression(files: Iterable[Path], *, feature_id: str) -> MissionStateMachine | None:
    """Normalize literal DSP/Topaz handlers from target-matched files into one machine."""
    raw: list[MissionTransition] = []
    channels: dict[str, set[int]] = {}
    counter = 0
    for path in files:
        try:
            lua = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        zone, actor = _zone_actor(path)
        lines = lua.splitlines()
        for start, end, block in _balanced_function_blocks(lua):
            first = lines[start] if start < len(lines) else ""
            match = _HANDLER.search(first)
            if not match:
                continue
            handler = match.group(1)
            for path_index, branch in enumerate(_handler_paths(block, start_line=start), 1):
                conditions = _conditions((*branch.guard_texts, *branch.guard_prefix_texts))
                for condition in conditions:
                    if condition.subject.startswith("charvar:") and isinstance(condition.value, int):
                        channels.setdefault(condition.subject, set()).add(condition.value)
                effects = _effects(branch.body)
                for effect in effects:
                    if effect.subject.startswith("charvar:") and isinstance(effect.value, int):
                        channels.setdefault(effect.subject, set()).add(effect.value)
                event_id = None
                if handler == "onEventFinish":
                    csids = _CSID.findall("\n".join((*branch.guard_texts, *branch.guard_prefix_texts)))
                    if csids:
                        event_id = int(csids[-1])
                else:
                    started = _START_EVENT.findall(branch.body)
                    if started:
                        event_id = int(started[-1])
                gate = DependencyGate(
                    f"legacy:{counter}:gate", "ALL", conditions
                ) if conditions else None
                counter += 1
                raw.append(MissionTransition(
                    transition_id=f"legacy:{path.name}:{handler}:{start+1}:{path_index}",
                    from_state="state:legacy", to_state="state:legacy",
                    trigger=_TRIGGER[handler], gate=gate,
                    event=EventIdentity(zone, event_id, actor) if event_id is not None else None,
                    effects=effects, confidence="VERIFIED",
                    metadata={
                        "legacy_adapter": True,
                        "source_path": str(path),
                        "source_lines": (start + 1, end + 1),
                        "section_index": 1,
                        "section_source_lines": (1, max(1, len(lines))),
                        "section_eligibility_status": "LEGACY_HANDLER_SCOPE",
                        "handler": handler,
                    },
                ))

    if not raw:
        return None

    # Attach literal event-finish effects to the interaction that starts the same event.  This makes
    # the admin-facing "next action" describe the persistent result instead of selecting the finish
    # callback as if the cutscene had already happened.
    finishes: dict[int, list[MissionTransition]] = {}
    for row in raw:
        if row.trigger == "EVENT_FINISH" and row.event is not None:
            finishes.setdefault(row.event.event_id, []).append(row)
    chained: list[MissionTransition] = []
    used_finish: set[str] = set()
    for row in raw:
        if row.trigger == "EVENT_FINISH":
            continue
        extra = []
        if row.event is not None:
            for finish in finishes.get(row.event.event_id, ()):
                extra.extend(finish.effects)
                used_finish.add(finish.transition_id)
        meta = dict(row.metadata)
        if extra:
            meta["logical_event_chain"] = True
        chained.append(MissionTransition(
            row.transition_id, row.from_state, row.to_state, row.trigger, row.gate, row.event,
            tuple((*row.effects, *extra)), row.confidence, row.evidence_ids,
            row.implementation_status, meta, row.post_effect_gate,
        ))
    # Keep unmatched finish callbacks visible because their starter may live in a helper/file that
    # the target scan did not select.
    chained.extend(row for row in raw if row.trigger == "EVENT_FINISH" and row.transition_id not in used_finish)

    return MissionStateMachine(
        machine_id=f"legacy:{feature_id}", feature_id=feature_id,
        states=(MissionState("state:legacy", "Legacy script progression"),),
        transitions=tuple(chained), entry_state_ids=("state:legacy",),
        channels=tuple(
            StateChannel(subject, "PERSISTENT", tuple(sorted(values)))
            for subject, values in sorted(channels.items())
        ),
        metadata={"adapter":"legacy_dsp_topaz", "source_layout":"legacy_handler_scripts"},
    )
