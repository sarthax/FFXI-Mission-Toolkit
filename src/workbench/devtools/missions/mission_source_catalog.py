"""Source catalog and on-demand structural ingestion for LandSandBoat mission/quest Lua."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .mission_lsb_extract import (
    _balanced_function_blocks,
    chain_event_transitions,
    correlate_lsb_handlers,
)
from .mission_state_machine import MissionStateMachine
from .quest_lsb_extract import (
    chain_quest_event_transitions,
    correlate_lsb_quest_handlers,
    extract_feature_requirement_helpers,
)


_QUEST_ID=re.compile(
    r"Quest:new\(xi\.questLog\.([A-Z0-9_]+),\s*xi\.quest\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+)\)"
)
_MISSION_ID=re.compile(
    r"Mission:new\(xi\.mission\.log_id\.([A-Z0-9_]+),\s*xi\.mission\.id\.[A-Za-z0-9_]+\.([A-Z0-9_]+)\)"
)


@dataclass(frozen=True)
class LsbFeatureSource:
    subject: str
    feature_id: str
    kind: str
    symbol: str
    log_symbol: str
    path: str


class LsbFeatureSourceCatalog:
    """Index literal LSB mission/quest identities and ingest them on demand."""

    def __init__(self, root: str | Path):
        self.root=Path(root)
        self._sources: dict[str,LsbFeatureSource]={}
        self._machines: dict[str,MissionStateMachine]={}
        self._helper_feature_gates={}
        self._scan()

    @staticmethod
    def _feature_id(kind: str, log_symbol: str, symbol: str) -> str:
        return f"{kind}:{log_symbol.casefold()}:{symbol.casefold()}"

    def _scan(self) -> None:
        if not self.root.exists():
            return
        for path in sorted(self.root.rglob("*.lua")):
            try:
                text=path.read_text(encoding="utf-8")
            except (OSError,UnicodeError):
                continue
            self._helper_feature_gates.update(extract_feature_requirement_helpers(text))
            quest=_QUEST_ID.search(text)
            mission=_MISSION_ID.search(text)
            if quest:
                log_symbol,symbol=quest.groups()
                source=LsbFeatureSource(
                    f"quest:{symbol}",
                    self._feature_id("quest",log_symbol,symbol),
                    "quest",symbol,log_symbol,str(path),
                )
                self._sources[source.subject]=source
            elif mission:
                log_symbol,symbol=mission.groups()
                source=LsbFeatureSource(
                    f"mission:{symbol}",
                    self._feature_id("mission",log_symbol,symbol),
                    "mission",symbol,log_symbol,str(path),
                )
                self._sources[source.subject]=source

    def subjects(self) -> tuple[str,...]:
        return tuple(sorted(self._sources))

    def source_for(self, subject: str) -> LsbFeatureSource | None:
        return self._sources.get(subject)

    def _feature_helper_gates_for_source(self, lua: str) -> tuple[dict,...]:
        """Resolve known cross-file helper predicates used by literal section checks."""
        lines=lua.splitlines()
        rows=[]
        seen=set()
        for start,_end,text in _balanced_function_blocks(lua):
            if not re.search(r"^\s*check\s*=\s*function\b",lines[start]):
                continue
            for helper,gate in self._helper_feature_gates.items():
                if not re.search(
                    rf"(?<![A-Za-z0-9_.]){re.escape(helper)}\(\s*player\s*\)",
                    text,
                ):
                    continue
                key=(gate.gate_id,gate.logic,tuple(
                    (condition.subject,condition.operator,repr(condition.value))
                    for condition in gate.conditions
                ))
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "gate_id":gate.gate_id,
                    "logic":gate.logic,
                    "conditions":tuple(
                        {
                            "subject":condition.subject,
                            "operator":condition.operator,
                            "value":condition.value,
                        }
                        for condition in gate.conditions
                    ),
                })
        return tuple(rows)

    def resolve_machine(self, subject: str) -> MissionStateMachine | None:
        """Locate and structurally ingest one cataloged feature symbol."""
        if subject in self._machines:
            return self._machines[subject]
        source=self._sources.get(subject)
        if source is None:
            return None
        try:
            lua=Path(source.path).read_text(encoding="utf-8")
        except (OSError,UnicodeError):
            return None
        if source.kind=="quest":
            machine=chain_quest_event_transitions(
                correlate_lsb_quest_handlers(
                    lua,
                    feature_id=source.feature_id,
                    helper_feature_gates=self._helper_feature_gates,
                )
            )
        else:
            machine=chain_event_transitions(
                correlate_lsb_handlers(lua,feature_id=source.feature_id)
            )
        metadata={
            **machine.metadata,
            "catalog_subject":source.subject,
            "catalog_feature_requirement_gates":self._feature_helper_gates_for_source(lua),
            "catalog_source_path":source.path,
            "catalog_discovered":True,
            "quest_symbol":(
                source.symbol if source.kind=="quest"
                else machine.metadata.get("quest_symbol")
            ),
            "mission_symbol":(
                source.symbol if source.kind=="mission"
                else machine.metadata.get("mission_symbol")
            ),
        }
        machine=MissionStateMachine(
            machine.machine_id,machine.feature_id,machine.states,machine.transitions,
            machine.entry_state_ids,machine.channels,machine.completion_gate,metadata,
        )
        self._machines[subject]=machine
        return machine

    def cached_machine(self, subject: str) -> MissionStateMachine | None:
        return self._machines.get(subject)

    def cached_subjects(self) -> tuple[str,...]:
        return tuple(sorted(self._machines))