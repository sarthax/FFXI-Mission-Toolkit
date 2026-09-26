"""Structural fingerprinting for FFXI client event resources.

Event numeric IDs are deliberately excluded from semantic fingerprints. The fingerprint keeps:
- exact bytecode SHA-256 (strong but brittle);
- opcode sequence and instruction lengths (structural, drift-tolerant);
- immediate-data count / event-block shape;
- actor/entity block id as contextual evidence, not semantic identity.

The vendored FFXI-EventsDump parser is used when available so instruction boundaries follow the
known opcode registry rather than treating arbitrary bytes as opcodes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable


@dataclass(frozen=True)
class EventResource:
    entity_id: int
    event_id: int
    byte_code: bytes
    data_count: int = 0
    block_event_count: int = 0
    block_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventFingerprint:
    exact_sha256: str
    structural_sha256: str
    opcode_sequence: tuple[int, ...]
    instruction_lengths: tuple[int, ...]
    bytecode_length: int
    data_count: int
    block_event_count: int
    unknown_opcode_count: int = 0
    parser: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)


def _events_dump_root() -> Path:
    return Path(__file__).resolve().parents[2] / "vendor" / "FFXI-EventsDump"


def _load_event_parser():
    root = _events_dump_root()
    if not root.is_dir():
        return None
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    try:
        from parser.eventcode import EventCodeParser  # type: ignore
        return EventCodeParser
    except Exception:
        return None


def decode_instruction_shape(byte_code: bytes) -> tuple[tuple[int, ...], tuple[int, ...], int, str]:
    parser_cls = _load_event_parser()
    if parser_cls is None:
        # Conservative fallback: do not pretend arbitrary bytes are decoded instructions.
        return (), (), 0, "RAW_ONLY"
    try:
        instructions, _ = parser_cls(use_control_flow=False).parse_event_data(byte_code)
        opcodes = tuple(int(x.opcode) for x in instructions)
        lengths = tuple(len(x.raw_bytes) for x in instructions)
        unknown = sum(1 for x in instructions if getattr(x, "opcode_impl", None) is None)
        return opcodes, lengths, unknown, "FFXI_EVENTS_DUMP"
    except Exception:
        return (), (), 0, "RAW_ONLY"


def fingerprint_event(resource: EventResource) -> EventFingerprint:
    exact = sha256(resource.byte_code).hexdigest()
    opcodes, lengths, unknown, parser_name = decode_instruction_shape(resource.byte_code)
    structural_payload = {
        # Numeric event id and raw actor/entity id are intentionally excluded.
        "opcode_sequence": list(opcodes),
        "instruction_lengths": list(lengths),
        "bytecode_length": len(resource.byte_code),
        "data_count": int(resource.data_count),
        "block_event_count": int(resource.block_event_count),
        "parser": parser_name,
    }
    structural = sha256(
        json.dumps(structural_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return EventFingerprint(
        exact_sha256=exact,
        structural_sha256=structural,
        opcode_sequence=opcodes,
        instruction_lengths=lengths,
        bytecode_length=len(resource.byte_code),
        data_count=int(resource.data_count),
        block_event_count=int(resource.block_event_count),
        unknown_opcode_count=unknown,
        parser=parser_name,
        metadata={
            "entity_id_context": resource.entity_id,
            "block_index": resource.block_index,
        },
    )


def semantic_event_structure_key(zone_key: str, fingerprint: EventFingerprint) -> str:
    return f"EVENT|{str(zone_key).strip().upper()}|STRUCTURE|{fingerprint.structural_sha256}"


def compare_event_fingerprints(
    source: EventFingerprint,
    target: EventFingerprint,
    *,
    source_text_fingerprint: str | None = None,
    target_text_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Compare two event fingerprints while keeping signals independent."""
    exact = source.exact_sha256 == target.exact_sha256
    structure = source.structural_sha256 == target.structural_sha256
    text = (
        source_text_fingerprint is not None
        and target_text_fingerprint is not None
        and source_text_fingerprint == target_text_fingerprint
    )

    decoded_structure = (
        source.parser != "RAW_ONLY"
        and target.parser != "RAW_ONLY"
        and bool(source.opcode_sequence)
        and bool(target.opcode_sequence)
    )

    if exact:
        status, confidence = "EXACT_BYTECODE", "VERIFIED"
    elif structure and decoded_structure and text:
        status, confidence = "STRUCTURE_AND_TEXT_MATCH", "HIGH"
    elif structure and decoded_structure:
        status, confidence = "STRUCTURE_MATCH", "HIGH"
    elif structure:
        status, confidence = "COARSE_SHAPE_MATCH", "LOW"
    elif text:
        # Important safety property: same text alone does not prove event equivalence.
        status, confidence = "TEXT_ONLY_MATCH", "LOW"
    else:
        status, confidence = "NO_MATCH", "UNKNOWN"

    return {
        "status": status,
        "confidence": confidence,
        "signals": {
            "exact_bytecode": exact,
            "structural": structure,
            "text": text,
        },
    }


def parse_event_export(path: Path) -> list[EventResource]:
    """Parse xi-tinkerer's serde-yaml Events export without requiring PyYAML.

    Expected shape is the serde representation of Events { blocks: [EventBlock...] }.
    Only fields needed for identity fingerprints are retained.
    """
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    out: list[EventResource] = []

    current_entity: int | None = None
    current_data_count = 0
    current_events: list[tuple[int, bytes]] = []
    block_index = -1
    in_events = False
    in_data = False

    def flush() -> None:
        nonlocal current_entity, current_data_count, current_events, block_index
        if current_entity is None:
            return
        count = len(current_events)
        for event_id, byte_code in current_events:
            out.append(
                EventResource(
                    entity_id=current_entity,
                    event_id=event_id,
                    byte_code=byte_code,
                    data_count=current_data_count,
                    block_event_count=count,
                    block_index=block_index,
                )
            )

    for line in lines:
        stripped = line.strip()
        m_entity = re.match(r"-?\s*entity_id:\s*(\d+)\s*$", stripped)
        if m_entity:
            flush()
            block_index += 1
            current_entity = int(m_entity.group(1))
            current_data_count = 0
            current_events = []
            in_events = False
            in_data = False
            continue

        if stripped == "events:":
            in_events, in_data = True, False
            continue
        if stripped == "data:":
            in_events, in_data = False, True
            continue

        if in_events:
            m_id = re.match(r"-?\s*id:\s*(\d+)\s*$", stripped)
            if m_id:
                current_events.append((int(m_id.group(1)), b""))
                continue
            m_code = re.match(r"byte_code:\s*['\"]?(0x[0-9A-Fa-f]*)['\"]?\s*$", stripped)
            if m_code and current_events:
                hex_value = m_code.group(1)[2:]
                byte_code = bytes.fromhex(hex_value) if hex_value else b""
                event_id, _ = current_events[-1]
                current_events[-1] = (event_id, byte_code)
                continue

        if in_data and re.match(r"-\s*(?:\d+|0x[0-9A-Fa-f]+)\s*$", stripped):
            current_data_count += 1

    flush()
    return out


def fingerprint_dict(value: EventFingerprint) -> dict[str, Any]:
    return asdict(value)
