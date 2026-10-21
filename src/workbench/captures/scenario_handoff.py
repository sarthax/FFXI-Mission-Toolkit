"""Synthetic-only handoff: indexed OBSERVED capture -> reviewer scenario candidate.

Depends on the separate #1265 read-only capture preview. This module never
imports packet decoders, authenticates source bytes, validates an oracle, saves
a test specification, invokes a runner, or mutates the capture index.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from .scenario_draft import reconstruct_observed_draft, _source_locator

_CONTRACT = "reverse_capture_preview_v0_NONCANONICAL"
_TYPES = {"capture_events", "capture_eventview", "capture_ki_events", "capture_raw_packets", "capture_structured_records"}
_DECISIONS = {"ACCEPT", "EDIT", "REJECT"}
_UNKNOWN = "UNKNOWN — normative expected behavior requires independent source-backed review"
_ORDER = ("capture_events", "capture_eventview", "capture_ki_events", "capture_structured_records", "capture_raw_packets")

# Indexed metadata only: never re-emit raw packet hex or opaque JSON payload.
_RECORDED_METADATA = {
    "capture_events": ("direction", "opcode", "opcode_name", "event_hex", "option", "message_id"),
    "capture_eventview": ("direction", "opcode", "packet_class", "gp_command", "mes_num", "message_number"),
    "capture_ki_events": ("event_type", "keyitem_id"),
    "capture_structured_records": ("family", "record_type", "item_id", "item_name"),
    "capture_raw_packets": ("direction", "opcode", "zone_id", "is_injected", "is_blocked",
                            "source_format", "source_native_id"),
}


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:20]


def _text(value: object) -> str:
    return str(value) if value is not None else "unrecorded"


def _row_ref(capture_id: int, table: str, event: dict) -> dict:
    key = event["row_key"]
    reference = "capture-row:" + _digest([capture_id, table, key])
    return {
        "ref_id": reference,
        "capture_id": capture_id,
        "table": table,
        "row_key": deepcopy(key),
        "source": deepcopy(event["source"]),
        "record_class": ("INDEXED_PACKET_METADATA" if table == "capture_raw_packets"
                         else "PARSED_CAPTURE_RECORD"),
        "native_timestamp": event["native_timestamp"],
        "time_basis": event["time_basis"],
        "confidence": event["confidence"],
        "recorded_metadata": {
            key: deepcopy(event["observed_fields"][key])
            for key in _RECORDED_METADATA[table]
            if key in event["observed_fields"]
        },
    }


def _binding(step_id: str, kind: str, value: object, evidence_refs: list[str], *,
             zone: object = None, classification: str = "DECODED", note: str = "") -> dict:
    return {
        "binding_id": "candidate:" + _digest([step_id, kind, value, zone]),
        "step_id": step_id,
        "kind": kind,
        "observed_value": deepcopy(value),
        "scope": {"zone_db": zone},
        "classification": classification,
        "authority": "UNVERIFIED_CAPTURE_IDENTITY",
        "evidence_refs": sorted(set(evidence_refs)),
        "basis": note or "Parser-recorded field, not an independently verified gameplay identity",
        "review": {"decision": "PENDING", "edited_value": None, "note": None},
    }


def _candidate_values(rows: list[dict], key: str) -> list:
    """Unique source values in original order; never infer absent values."""
    values = []
    for row in rows:
        value = row.get(key)
        if value is not None and value not in values:
            values.append(value)
    return values


def _summary(table: str, rows: list[dict], *, grouped: bool = False) -> str:
    first = rows[0]
    if table == "capture_events":
        actor = _candidate_values(rows, "entity_name")
        event_ids = _candidate_values(rows, "event_hex")
        dialogs = _candidate_values(rows, "message_id")
        options = _candidate_values(rows, "option")
        parts = ["Captured " + ("interaction candidate" if grouped else "event record"),
                 "in zone " + _text(first.get("zone_db"))]
        if actor:
            parts.append("recorded actor name(s): " + ", ".join(map(str, actor)))
        if event_ids:
            parts.append("event field(s): " + ", ".join(map(str, event_ids)))
        if dialogs:
            parts.append("message ID(s): " + ", ".join(map(str, dialogs)))
        if options:
            parts.append("option field(s): " + ", ".join(map(str, options)))
        return "; ".join(parts) + ". No gameplay result confirmed."
    if table == "capture_eventview":
        return ("EventView parsed record in zone " + _text(first.get("zone_db"))
                + "; recorded command " + _text(first.get("gp_command"))
                + "; MesNum " + _text(first.get("mes_num"))
                + " (message/event meaning unresolved).")
    if table == "capture_structured_records":
        return ("Structured source family " + _text(first.get("family"))
                + " recorded item field " + _text(first.get("item_id"))
                + " with source label " + _text(first.get("item_name"))
                + "; item ownership, acquisition or gameplay effects not proven.")
    if table == "capture_ki_events":
        return ("Key-item logger recorded event label " + _text(first.get("event_type"))
                + " with key-item field " + _text(first.get("keyitem_id"))
                + "; no independent inventory-state proof.")
    return ("Raw packet metadata recorded " + _text(first.get("direction"))
            + " opcode " + _text(first.get("opcode"))
            + " (not decoded; dispatch/injection cannot prove gameplay completion).")


def _make_step(step_id: str, table: str, events: list[dict], *,
               grouped: bool = False) -> dict:
    rows = [e["observed_fields"] for e in events]
    evidence = [e["reference"]["ref_id"] for e in events]
    zone = (rows[0].get("zone_db") if table in {"capture_events", "capture_eventview"}
            else rows[0].get("zone") if table == "capture_structured_records"
            else rows[0].get("zone_name") if table == "capture_ki_events"
            else rows[0].get("zone_id"))
    bindings = []
    gaps = []
    uncertain = False

    fields = {
        "capture_events": [("zone", "zone_db"), ("npc", "entity_id"),
                           ("npc_name", "entity_name"), ("event", "event_hex"),
                           ("dialog", "message_id")],
        "capture_eventview": [("zone", "zone_db"), ("npc", "entity_id"),
                              ("message_or_event", "mes_num")],
        "capture_ki_events": [("zone", "zone_name"), ("key_item", "keyitem_id")],
        "capture_structured_records": [("zone", "zone"), ("item", "item_id"),
                                       ("item_name", "item_name"), ("npc", "entity_id")],
        "capture_raw_packets": [("zone", "zone_id"), ("packet", "opcode")],
    }[table]
    for kind, field in fields:
        values = _candidate_values(rows, field)
        if not values:
            # Absence is a recorded gap, never a replacement ID.
            if kind in {"npc", "event", "message_or_event"} and table != "capture_raw_packets":
                gaps.append("NO_RECORDED_" + kind.upper() + "_FIELD")
            continue
        status = "AMBIGUOUS" if len(values) > 1 else "DECODED"
        basis = "Parser-recorded value; canonical identity not established"
        if kind == "message_or_event":
            status = "AMBIGUOUS"
            basis = "MesNum is not definitively an event or message/CSID identity"
        if kind == "packet":
            status = "UNSUPPORTED"
            basis = "Raw opcode metadata only: packet fields were not decoded"
        if kind == "npc_name" and len(values) > 1:
            gaps.append("CONTRADICTORY_NPC_NAMES_FOR_INTERACTION")
        if status in {"AMBIGUOUS", "UNSUPPORTED"}:
            uncertain = True
        bindings.append(_binding(step_id, kind, values if len(values) > 1 else values[0],
                                 evidence, zone=zone, classification=status, note=basis))
    for event in events:
        source_state = event["source"]["status"]
        if source_state not in {"LOCATED_SOURCE_SPAN", "FILE_LEVEL_ONLY"}:
            gaps.append("SOURCE_" + source_state)
            uncertain = True
        if table == "capture_raw_packets" and (
            event["observed_fields"].get("is_injected") or event["observed_fields"].get("is_blocked")
        ):
            gaps.append("PACKET_INJECTED_OR_BLOCKED_NOT_RECEIPT")
            uncertain = True
    if zone in (None, "", "__UNKNOWN__"):
        gaps.append("ZONE_CONTEXT_UNSUPPORTED")
        uncertain = True
    if grouped:
        gaps.append("GROUPED_BY_ADJACENCY_NOT_PROVEN_TRANSACTION")
    return {
        "step_id": step_id,
        "lane": table,
        "zone_db": zone,
        "order_basis": ("ZONE_SEQUENCE" if table in {"capture_events", "capture_eventview"}
                        else "SOURCE_SCOPED_STRUCTURED_KEY" if table == "capture_structured_records"
                        else "CAPTURE_TABLE_SEQUENCE"),
        "observed_summary": _summary(table, rows, grouped=grouped),
        "evidence_refs": evidence,
        "bindings": bindings,
        "record_class": "INDEXED_RAW" if table == "capture_raw_packets" else "DECODED_BY_EXISTING_PARSER",
        "relationship": (
            {"classification": "INFERRED", "basis": "contiguous, compatible indexed capture_events",
             "proof": "NOT_A_CONFIRMED_GAMEPLAY_TRANSACTION"} if grouped else None
        ),
        "review_gaps": sorted(set(gaps)),
        "interpretation": "AMBIGUOUS" if uncertain else ("INFERRED" if grouped else "OBSERVED"),
        "normative_expected": None,
        "verdict": "UNKNOWN",
        "review_required": True,
    }


def build_scenario_handoff(preview: dict, *, max_steps: int = 100) -> dict:
    """Project #1265 evidence into a bounded, *non-importable* authoring scaffold."""
    if not isinstance(preview, dict) or preview.get("contract") != _CONTRACT:
        raise ValueError("only #1265 indexed observed previews are supported")
    if (preview.get("classification") != "OBSERVED_ONLY" or
            preview.get("scenario_status") != "DRAFT_REVIEW_REQUIRED" or
            preview.get("normative_expected") is not None or
            preview.get("verdict") != "UNKNOWN" or
            preview.get("execution_enabled") is not False or
            preview.get("approved_for_execution") is not False):
        raise ValueError("unsafe capture preview: observed-only invariants violated")
    if type(max_steps) is not int or not 1 <= max_steps <= 100:
        raise ValueError("max_steps must be 1..100")
    capture_id = preview.get("capture_id")
    if type(capture_id) is not int or capture_id < 1:
        raise ValueError("capture_id missing")
    streams = preview.get("streams")
    groups = preview.get("interaction_candidates")
    if not isinstance(streams, list) or not isinstance(groups, list):
        raise ValueError("streams/interactions missing")
    if len(streams) > 4000 or len(groups) > 4000:
        raise ValueError("unbounded preview")

    # Source-table ordering is a display grouping, never cross-source chronology.
    events_by_key: dict[str, dict] = {}
    all_streams: list[tuple[str, list[dict]]] = []
    references: dict[str, dict] = {}
    for table in _ORDER:
        for stream in streams:
            if not isinstance(stream, dict):
                raise ValueError("malformed stream")
            if stream.get("table") not in _TYPES:
                raise ValueError("unsupported capture stream")
            if stream.get("table") != table:
                continue
            items = stream.get("events")
            if not isinstance(items, list) or len(items) > 1000:
                raise ValueError("invalid stream length")
            indexed = []
            for entry in items:
                if not isinstance(entry, dict) or not isinstance(entry.get("observed_fields"), dict) or not isinstance(entry.get("source"), dict) or not isinstance(entry.get("row_key"), dict):
                    raise ValueError("malformed indexed event")
                row = dict(entry)
                row["reference"] = _row_ref(capture_id, table, entry)
                ref = row["reference"]
                if ref["ref_id"] in references:
                    raise ValueError("duplicate indexed evidence identity")
                references[ref["ref_id"]] = ref
                indexed.append(row)
                if table == "capture_events":
                    events_by_key[json.dumps(entry["row_key"], sort_keys=True)] = row
            all_streams.append((table, indexed))

    units: list[tuple[str, list[dict], bool]] = []
    consumed: set[str] = set()
    for candidate in groups:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("row_keys"), list):
            raise ValueError("invalid interaction candidate")
        found = []
        for key in candidate["row_keys"]:
            identity = json.dumps(key, sort_keys=True)
            row = events_by_key.get(identity)
            if row is None or identity in consumed:
                raise ValueError("interaction refers to missing or overlapping capture row")
            consumed.add(identity)
            found.append(row)
        if found:
            units.append(("capture_events", found, len(found) > 1))
    for table, events in all_streams:
        if table == "capture_events":
            for entry in events:
                k = json.dumps(entry["row_key"], sort_keys=True)
                if k not in consumed:
                    units.append((table, [entry], False))
        else:
            units.extend((table, [entry], False) for entry in events)
    steps = []
    for table, entries, grouped in units[:max_steps]:
        step_id = "OBS-S" + str(len(steps) + 1).zfill(3)
        steps.append(_make_step(step_id, table, entries, grouped=grouped))
    gaps = set(preview.get("review_gaps", []))
    gaps.update(g for step in steps for g in step["review_gaps"])
    if len(units) > max_steps:
        gaps.add("DRAFT_STEP_PREVIEW_TRUNCATED")
    gaps.update({"NORMATIVE_EXPECTED_UNKNOWN", "CANONICAL_IDENTITY_AND_ASSERTION_BINDINGS_MISSING",
                 "SOURCE_AND_DECODER_REVISION_ATTESTATION_REQUIRED"})
    gaps = sorted(gaps)
    # #1263 compatible field names/shape, deliberately *not* validate_spec-ready:
    # no known feature/case identity or supported observation/assertion oracle.
    # Do not fill those fields with fabricated placeholders just to pass validation.
    scaffold = {
        "schema_version": 1, "feature_id": None, "case_id": None,
        "name": "Observed capture review (" + str(capture_id) + ")",
        "runner": "unassigned", "execution_status": "design_only",
        "preconditions": [], "observations": [], "assertions": [], "cleanup": [],
        "purpose": "Review captured interactions and independently author a normative scenario",
        "rationale": "Captured behavior is evidence of observation, not proof of expected gameplay",
        "behavior": {
            "given": ["An indexed capture contains unverified, source-local evidence"],
            "when": ["A reviewer inspects suggested observed steps and source references"],
            "then": ["UNKNOWN: normative outcomes and independent readbacks remain unestablished"],
        },
        "steps": [{
            "id": step["step_id"], "title": step["observed_summary"][:500],
            "intent": "observation", "expected": _UNKNOWN,
            "assertion_ids": [], "evidence_refs": [],
            "confidence_note": "Observed-only; original source references remain in handoff evidence_map",
        } for step in steps],
        "authoring": {
            "state": "reverse_capture_review_required",
            "execution_policy": "disabled",
            "evidence_provenance": "unverified_indexed_capture",
            "blocking_gaps": gaps[:30],
            "review_required": True,
        },
    }
    return {
        "contract": "evidence_to_scenario_review_v0_NONCANONICAL",
        "capture_id": capture_id,
        "scenario_status": "DRAFT_REVIEW_REQUIRED",
        "observation_verdict": "UNKNOWN",
        "normative_expected": None,
        "execution_enabled": False,
        "approved_for_execution": False,
        "canonical_validation_status": "BLOCKED_REQUIRES_HUMAN_SOURCE_BACKED_AUTHORING",
        "canonical_specification_seed": scaffold,
        "canonical_step_evidence_map": {s["step_id"]: s["evidence_refs"] for s in steps},
        "steps": steps,
        "evidence_map": references,
        "missing_tables": deepcopy(preview.get("missing_tables", [])),
        "truncated_tables": deepcopy(preview.get("truncated_tables", [])),
        "omitted_step_count": len(units) - len(steps),
        "review_gaps": gaps,
        "review_decisions": ("ACCEPT", "EDIT", "REJECT"),
        "review_complete": False,
        "review_note": ("Binding acceptance acknowledges a proposed label; it does not "
                        "authenticate source files, establish expected behavior, or authorize execution"),
    }



def _structured_item_streams(con, capture_id: int, limit: int) -> tuple[list[dict], str | None]:
    """Project indexed ordinary-item references; no raw payloads or new parsing.

    Source format keys and original locators are retained. Native record keys
    are stable *within their source file/family*, never globally chronologic.
    """
    if not con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='capture_structured_records'"
    ).fetchone():
        return [], "STRUCTURED_ITEM_INDEX_UNAVAILABLE"
    cursor = con.execute(
        """SELECT source_file,family,record_key,record_type,ts,zone,
                  entity_id,entity_name,item_id,item_name
           FROM capture_structured_records
           WHERE capture_id=? AND item_id IS NOT NULL
           ORDER BY source_file,family,record_key LIMIT ?""",
        (capture_id, limit + 1),
    )
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    truncated = len(rows) > limit
    streams = {}
    for values in rows[:limit]:
        record = dict(zip(columns, values))
        key = {k: record[k] for k in ("source_file", "family", "record_key")}
        source = _source_locator(con, capture_id, "capture_structured_records", key)
        partition = (record["source_file"], record["family"], record["zone"])
        if partition not in streams:
            streams[partition] = {
                "table": "capture_structured_records", "zone_db": record["zone"],
                "order_basis": "SOURCE_SCOPED_STRUCTURED_KEY",
                "clock_status": "NOT_ALIGNED_WITH_OTHER_STREAMS", "events": [],
            }
        streams[partition]["events"].append({
            "row_key": key, "observation_kind": "capture_structured_records",
            "observed_fields": record, "native_timestamp": record["ts"],
            "time_basis": "SOURCE_NATIVE_UNVERIFIED" if record["ts"] is not None else "NO_TIMESTAMP",
            "source": source, "confidence": "INDEXED_OBSERVATION_ONLY",
            "identity_status": "UNRESOLVED",
        })
    return list(streams.values()), "STRUCTURED_ITEM_RECORDS_TRUNCATED" if truncated else None

def reconstruct_review_draft(con, capture_id: int, *, max_rows_per_table: int = 200, max_steps: int = 100) -> dict:
    """Read only: build an observed preview then a non-executable review handoff."""
    preview = reconstruct_observed_draft(con, capture_id, max_rows_per_table=max_rows_per_table)
    # Separate optional source family: ordinary items live in structured capture
    # records, not in the #1265 baseline observation tables. Never read payload_json.
    streams, gap = _structured_item_streams(con, capture_id, max_rows_per_table)
    preview["streams"].extend(streams)
    if gap:
        preview["review_gaps"].append(gap)
    return build_scenario_handoff(preview, max_steps=max_steps)


def apply_binding_decisions(draft: dict, decisions: list[dict]) -> dict:
    """Pure reviewer annotation. Never alters observed values, source refs or execution gates."""
    if not isinstance(draft, dict) or draft.get("contract") != "evidence_to_scenario_review_v0_NONCANONICAL" or draft.get("execution_enabled") is not False:
        raise ValueError("only nonexecutable handoff drafts may be reviewed")
    if not isinstance(decisions, list) or len(decisions) > 100:
        raise ValueError("invalid reviewer decisions")
    result = deepcopy(draft)
    candidates = {b["binding_id"]: b for s in result["steps"] for b in s["bindings"]}
    if len(candidates) != sum(len(s["bindings"]) for s in result["steps"]):
        raise ValueError("duplicate binding IDs")
    seen = set()
    for item in decisions:
        if not isinstance(item, dict) or set(item) - {"binding_id", "decision", "note", "edited_value"}:
            raise ValueError("unexpected reviewer decision fields")
        bid, decision = item.get("binding_id"), item.get("decision")
        if bid not in candidates or bid in seen or decision not in _DECISIONS:
            raise ValueError("invalid or duplicate binding review")
        note = item.get("note")
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 500:
            raise ValueError("explicit reviewer note required")
        if decision == "EDIT":
            edited = item.get("edited_value")
            if not isinstance(edited, (str, int)) or isinstance(edited, bool) or len(str(edited)) > 120 or not str(edited).strip():
                raise ValueError("edited value must be bounded and reviewer-supplied")
        elif "edited_value" in item:
            raise ValueError("edited_value only allowed for EDIT")
        candidates[bid]["review"] = {
            "decision": decision,
            "edited_value": item.get("edited_value") if decision == "EDIT" else None,
            "note": note.strip(),
        }
        # Reviewer edits are unverified suggestions, never an overwrite of raw value.
        seen.add(bid)
    result["review_complete"] = bool(candidates) and all(
        b["review"]["decision"] != "PENDING" for b in candidates.values()
    )
    result["scenario_status"] = "DRAFT_REVIEW_REQUIRED"
    result["canonical_validation_status"] = "BLOCKED_REQUIRES_HUMAN_SOURCE_BACKED_AUTHORING"
    result["normative_expected"] = None
    result["execution_enabled"] = False
    result["approved_for_execution"] = False
    return result
