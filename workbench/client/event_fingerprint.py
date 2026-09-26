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
import ast
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
    data_values: tuple[int, ...] = ()
    block_event_count: int = 0
    block_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventFingerprint:
    exact_sha256: str
    structural_sha256: str
    composite_sha256: str
    opcode_sequence: tuple[int, ...]
    instruction_lengths: tuple[int, ...]
    bytecode_length: int
    data_count: int
    block_event_count: int
    unknown_opcode_count: int = 0
    message_ids: tuple[int, ...] = ()
    message_text_fingerprints: tuple[str, ...] = ()
    entity_roles: tuple[str, ...] = ()
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


def _load_opcode_source_table() -> dict[int, dict[str, Any]]:
    """Read opcode shapes from vendored Python source via AST, including inherited args."""
    root = _events_dump_root() / "parser" / "opcodes"
    if not root.is_dir():
        return {}

    classes: dict[str, dict[str, Any]] = {}

    def parse_arg_call(node: ast.AST) -> dict[str, Any] | None:
        if not isinstance(node, ast.Call):
            return None
        func_name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if func_name != "OpcodeArg" or len(node.args) < 3:
            return None
        name_node, type_node, size_node = node.args[:3]
        if not isinstance(name_node, ast.Constant) or not isinstance(name_node.value, str):
            return None
        if not isinstance(size_node, ast.Constant) or not isinstance(size_node.value, int):
            return None
        arg_type = getattr(type_node, "attr", None) or getattr(type_node, "id", None) or "UNKNOWN"
        return {"name": name_node.value, "arg_type": str(arg_type), "size": int(size_node.value)}

    for path in root.glob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            opcode: int | None = None
            own_args: list[dict[str, Any]] | None = None
            own_variable = False
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "opcode":
                            try:
                                value = ast.literal_eval(item.value)
                                if isinstance(value, int):
                                    opcode = int(value)
                            except Exception:
                                pass
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name == "calculate_length" and node.name != "BaseOpcode":
                        own_variable = True
                    if item.name == "get_args":
                        own_args = []
                        for stmt in ast.walk(item):
                            if isinstance(stmt, ast.Return) and isinstance(stmt.value, (ast.List, ast.Tuple)):
                                parsed = [parse_arg_call(x) for x in stmt.value.elts]
                                own_args = [x for x in parsed if x is not None]
                                break
            bases = [
                getattr(base, "id", None) or getattr(base, "attr", None)
                for base in node.bases
            ]
            classes[node.name] = {
                "opcode": opcode,
                "own_args": own_args,
                "own_variable": own_variable,
                "bases": [b for b in bases if b],
            }

    resolving: set[str] = set()
    resolved: dict[str, tuple[list[dict[str, Any]], bool]] = {}

    def resolve_class(name: str) -> tuple[list[dict[str, Any]], bool]:
        if name in resolved:
            return resolved[name]
        if name in resolving:
            return [], False
        spec = classes.get(name)
        if spec is None:
            return [], False
        resolving.add(name)
        inherited_args: list[dict[str, Any]] = []
        inherited_variable = False
        for base in spec["bases"]:
            if base in classes:
                inherited_args, inherited_variable = resolve_class(base)
                break
        args = spec["own_args"] if spec["own_args"] is not None else inherited_args
        variable = bool(spec["own_variable"] or inherited_variable)
        resolving.discard(name)
        resolved[name] = (list(args), variable)
        return resolved[name]

    table: dict[int, dict[str, Any]] = {}
    for class_name, spec in classes.items():
        opcode = spec["opcode"]
        if opcode is None:
            continue
        args, variable = resolve_class(class_name)
        table[int(opcode)] = {
            "length": 1 + sum(int(a["size"]) for a in args),
            "args": args,
            "variable": variable,
        }
    return table


def _special_entity_role(value: int) -> str | None:
    """Return only portable special-entity semantics; ordinary raw entity ids are excluded."""
    if value in {0x7FFFFFC0, 0x7FFFFFF0, 0x7FFFFFF9}:
        return "LOCAL_PLAYER"
    if value == 0x7FFFFFF8:
        return "EVENT_ENTITY"
    if 0x7FFFFFC1 <= value <= 0x7FFFFFC5:
        return f"PARTY_MEMBER_{value - 0x7FFFFFC0}"
    if 0x7FFFFFC6 <= value <= 0x7FFFFFCB:
        return f"ALLIANCE_MEMBER_{value - 0x7FFFFFC5}"
    if 0x7FFFFFCC <= value <= 0x7FFFFFD1:
        return f"ALLIANCE_MEMBER_{value - 0x7FFFFFCB + 6}"
    if 0x7FFFFFF1 <= value <= 0x7FFFFFF5:
        return f"PARTY_REF_{value - 0x7FFFFFF0}"
    return None


def _decode_from_opcode_sources(
    byte_code: bytes,
    data_values: tuple[int, ...],
) -> tuple[tuple[int, ...], tuple[int, ...], int, tuple[int, ...], tuple[str, ...], str]:
    table = _load_opcode_source_table()
    if not table:
        return (), (), 0, (), (), "RAW_ONLY"

    opcodes: list[int] = []
    lengths: list[int] = []
    messages: list[int] = []
    entity_roles: list[str] = []
    unknown = 0
    offset = 0
    while offset < len(byte_code):
        opcode = byte_code[offset]
        spec = table.get(opcode)
        if spec is None:
            unknown += 1
            opcodes.append(opcode)
            lengths.append(1)
            offset += 1
            continue
        if spec["variable"]:
            # Without executing the opcode's custom length calculation we cannot safely
            # find the next instruction boundary. Refuse to manufacture structure.
            return (), (), 0, (), "RAW_ONLY"
        length = int(spec["length"])
        if offset + length > len(byte_code):
            return (), (), 0, (), "RAW_ONLY"

        opcodes.append(opcode)
        lengths.append(length)
        arg_offset = offset + 1
        for arg in spec["args"]:
            size = int(arg["size"])
            raw_value = byte_code[arg_offset:arg_offset + size]
            name = str(arg["name"]).lower()
            arg_type = str(arg["arg_type"]).lower()
            if size in {1, 2, 4}:
                value = int.from_bytes(raw_value, "little")
                if ("message" in name or arg_type == "message_id"):
                    message_value = value
                    if 0x8000 <= message_value <= 0x8FFF:
                        ref_index = message_value & 0x7FFF
                        if ref_index < len(data_values):
                            message_value = int(data_values[ref_index])
                    messages.append(message_value)
                if arg_type == "entity_id" or "entity" in name or "actor" in name or "target" in name:
                    role = _special_entity_role(value)
                    if role:
                        entity_roles.append(role)
            arg_offset += size
        offset += length

    return tuple(opcodes), tuple(lengths), unknown, tuple(messages), tuple(entity_roles), "OPCODE_SOURCE_TABLE"


def decode_instruction_shape(
    byte_code: bytes,
    data_values: tuple[int, ...] = (),
) -> tuple[tuple[int, ...], tuple[int, ...], int, tuple[int, ...], tuple[str, ...], str]:
    parser_cls = _load_event_parser()
    if parser_cls is None:
        return _decode_from_opcode_sources(byte_code, data_values)
    try:
        instructions, _ = parser_cls(use_control_flow=False).parse_event_data(byte_code)
        opcodes = tuple(int(x.opcode) for x in instructions)
        lengths = tuple(len(x.raw_bytes) for x in instructions)
        unknown = sum(1 for x in instructions if getattr(x, "opcode_impl", None) is None)
        message_ids: list[int] = []
        entity_roles: list[str] = []
        for instruction in instructions:
            impl = getattr(instruction, "opcode_impl", None)
            args = getattr(instruction, "args", {}) or {}
            arg_defs = getattr(impl, "_args", ()) if impl is not None else ()
            for arg_def in arg_defs:
                name = str(getattr(arg_def, "name", "")).lower()
                arg_type = str(getattr(getattr(arg_def, "arg_type", None), "value", "")).lower()
                value = args.get(getattr(arg_def, "name", ""))
                if not isinstance(value, int):
                    continue
                if "message" in name or arg_type == "message_id":
                    message_value = value
                    if 0x8000 <= message_value <= 0x8FFF:
                        ref_index = message_value & 0x7FFF
                        if ref_index < len(data_values):
                            message_value = int(data_values[ref_index])
                    message_ids.append(int(message_value))
                if arg_type == "entity_id" or "entity" in name or "actor" in name or "target" in name:
                    role = _special_entity_role(value)
                    if role:
                        entity_roles.append(role)
        return opcodes, lengths, unknown, tuple(message_ids), tuple(entity_roles), "FFXI_EVENTS_DUMP"
    except Exception:
        return _decode_from_opcode_sources(byte_code, data_values)


def fingerprint_event(
    resource: EventResource,
    *,
    dialog_entries: dict[int, str] | None = None,
) -> EventFingerprint:
    exact = sha256(resource.byte_code).hexdigest()
    opcodes, lengths, unknown, message_ids, entity_roles, parser_name = decode_instruction_shape(
        resource.byte_code,
        resource.data_values,
    )
    structural_payload = {
        "opcode_sequence": list(opcodes),
        "instruction_lengths": list(lengths),
        "bytecode_length": len(resource.byte_code),
        "entity_roles": list(entity_roles),
    }
    structural = sha256(
        json.dumps(structural_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    text_fingerprints: list[str] = []
    if dialog_entries:
        from workbench.core.services.identity_resolver import text_fingerprint
        for message_id in message_ids:
            text = dialog_entries.get(int(message_id))
            if text is not None:
                text_fingerprints.append(text_fingerprint(text))

    composite_payload = {
        "structural_sha256": structural,
        # Message numeric IDs are intentionally excluded; resolved text survives ID drift.
        "message_text_fingerprints": text_fingerprints,
    }
    composite = sha256(
        json.dumps(composite_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return EventFingerprint(
        exact_sha256=exact,
        structural_sha256=structural,
        composite_sha256=composite,
        opcode_sequence=opcodes,
        instruction_lengths=lengths,
        bytecode_length=len(resource.byte_code),
        data_count=int(resource.data_count),
        block_event_count=int(resource.block_event_count),
        unknown_opcode_count=unknown,
        message_ids=message_ids,
        message_text_fingerprints=tuple(text_fingerprints),
        entity_roles=entity_roles,
        parser=parser_name,
        metadata={
            "entity_id_context": resource.entity_id,
            "block_index": resource.block_index,
        },
    )


def semantic_event_structure_key(zone_key: str, fingerprint: EventFingerprint) -> str:
    basis = fingerprint.composite_sha256 if fingerprint.message_text_fingerprints else fingerprint.structural_sha256
    label = "COMPOSITE" if fingerprint.message_text_fingerprints else "STRUCTURE"
    return f"EVENT|{str(zone_key).strip().upper()}|{label}|{basis}"


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
    composite = (
        bool(source.message_text_fingerprints)
        and bool(target.message_text_fingerprints)
        and source.composite_sha256 == target.composite_sha256
    )
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
    elif composite and decoded_structure:
        status, confidence = "COMPOSITE_STRUCTURE_TEXT_MATCH", "HIGH"
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
            "composite": composite,
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
    current_data_values: list[int] = []
    current_events: list[tuple[int, bytes]] = []
    block_index = -1
    in_events = False
    in_data = False

    def flush() -> None:
        nonlocal current_entity, current_data_count, current_data_values, current_events, block_index
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
                    data_values=tuple(current_data_values),
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
            current_data_values = []
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

        if in_data:
            m_data = re.match(r"-\s*(\d+|0x[0-9A-Fa-f]+)\s*$", stripped)
            if m_data:
                value = int(m_data.group(1), 0)
                current_data_values.append(value)
                current_data_count += 1

    flush()
    return out


def fingerprint_dict(value: EventFingerprint) -> dict[str, Any]:
    return asdict(value)
