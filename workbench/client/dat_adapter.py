"""Generic read-only Workbench model over existing FFXI item DAT tooling.

This module does not write DAT files. It normalizes client item records for graph,
comparison, and capability workflows while preserving the mature item_dat_tools
reader/writer as the low-level implementation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Callable

import item_dat_tools
from workbench.adapters.servers.base import LogicalRecord
from workbench.core import graph
from workbench.core.schema import Capability, CapabilityObservation, Evidence


@dataclass(frozen=True)
class ClientDatRecord:
    item_id: int
    snapshot_id: str
    category: str
    layout: str
    format: str
    source_path: str | None
    record_index: int | None
    fields: dict[str,Any]


@dataclass(frozen=True)
class ClientServerFieldBinding:
    logical_type: str
    server_field: str
    client_field: str
    relation: str = "EQUAL"
    notes: str = ""


@dataclass(frozen=True)
class ClientServerFieldComparison:
    logical_type: str
    item_id: int
    server_field: str
    client_field: str
    status: str
    server_value: Any
    client_value: Any
    notes: str = ""


ITEM_FIELD_BINDINGS=(
    ClientServerFieldBinding("item_basic","item_id","id",notes="Shared item identity."),
    ClientServerFieldBinding("item_basic","flags","flags",notes="Shared item flags bitfield."),
    ClientServerFieldBinding("item_basic","stack_size","stack",notes="Server stackSize maps to client stack."),
    ClientServerFieldBinding("item_basic","item_type","type",notes="LSB item_basic explicit type maps to client item type where present."),
    ClientServerFieldBinding("item_equipment","level","level",notes="Equip level must agree client/server."),
    ClientServerFieldBinding("item_equipment","jobs","jobs",notes="Equip-job bitmask must agree client/server."),
    ClientServerFieldBinding("item_equipment","slot","slots",notes="Server equipment slot mask maps to client slot mask."),
    ClientServerFieldBinding("item_weapon","skill","skill",notes="Weapon skill category."),
    ClientServerFieldBinding("item_weapon","delay","delay",notes="Weapon delay."),
    ClientServerFieldBinding("item_weapon","damage","dmg",notes="Weapon base damage."),
    ClientServerFieldBinding("item_usable","valid_targets","targets",notes="Usable-item target mask."),
)


def _slug(value: Any) -> str:
    raw=json.dumps(value,sort_keys=True,default=str,separators=(",",":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class ItemDatAdapter:
    """Read-only adapter over item_dat_tools with injectable readers for tests."""

    adapter_id="ffxi-item-dat"

    def __init__(
        self,
        snapshot_id: str,
        *,
        reader: Callable[[int],Any] | None = None,
        serializer: Callable[[Any],dict[str,Any]] | None = None,
    ):
        if not snapshot_id:
            raise ValueError("snapshot_id is required")
        self.snapshot_id=snapshot_id
        self._reader=reader or item_dat_tools.read_client_item
        self._serializer=serializer or item_dat_tools.item_to_dict

    def read(self,item_id: int) -> ClientDatRecord | None:
        raw=self._reader(int(item_id))
        if raw is None:
            return None
        fields=dict(self._serializer(raw))
        category=str(getattr(raw,"category","") or fields.get("category") or "")
        item_type=int(fields.get("type",getattr(raw,"type",0)) or 0)
        return ClientDatRecord(
            item_id=int(item_id),
            snapshot_id=self.snapshot_id,
            category=category,
            layout=item_dat_tools.layout_for_type(item_type),
            format=str(getattr(raw,"format",fields.get("format","")) or ""),
            source_path=str(getattr(raw,"dat","") or "") or None,
            record_index=getattr(raw,"record_index",None),
            fields=fields,
        )


def bindings_for(logical_type: str) -> tuple[ClientServerFieldBinding,...]:
    return tuple(binding for binding in ITEM_FIELD_BINDINGS if binding.logical_type==logical_type)


def compare_server_record_to_client(
    server_record: LogicalRecord,
    client_record: ClientDatRecord,
) -> tuple[ClientServerFieldComparison,...]:
    """Compare only explicitly bound fields; unbound fields are not inferred."""
    identity=dict(server_record.identity)
    server_item_id=identity.get("item_id")
    if server_item_id is not None and int(server_item_id)!=client_record.item_id:
        raise ValueError("server/client item identities differ")

    rows=[]
    for binding in bindings_for(server_record.logical_type):
        server_value=server_record.fields.get(binding.server_field)
        client_value=client_record.fields.get(binding.client_field)
        if server_value is None or client_value is None:
            status="UNKNOWN"
        elif server_value==client_value:
            status="VERIFIED"
        else:
            status="CONTRADICTED"
        rows.append(ClientServerFieldComparison(
            logical_type=server_record.logical_type,
            item_id=client_record.item_id,
            server_field=binding.server_field,
            client_field=binding.client_field,
            status=status,
            server_value=server_value,
            client_value=client_value,
            notes=binding.notes,
        ))
    return tuple(rows)


def persist_client_dat_record_capability(con, record: ClientDatRecord) -> dict[str,int]:
    """Persist client-record presence/layout as snapshot-scoped capability evidence."""
    evidence_id=f"evidence:client-dat:{record.snapshot_id}:{record.item_id}"
    capability_id=f"capability:client-dat-record:{record.item_id}"
    observation_id=f"capability-observation:{record.snapshot_id}:{_slug(capability_id)}"

    graph.insert_record(con,Evidence(
        evidence_id=evidence_id,
        evidence_type="CLIENT_SOURCE",
        source="item_dat_tools",
        location=record.source_path,
        snapshot=record.snapshot_id,
        notes="Readable client item DAT record.",
    ))
    graph.insert_record(con,Capability(
        capability_id=capability_id,
        name=f"client_dat_record:{record.item_id}",
        capability_type="CLIENT_DAT_RECORD",
        subject_id=f"item:{record.item_id}",
        source_snapshot_id=None,
        status="UNKNOWN",
        value={"snapshot_scoped":True},
        evidence_id=None,
        notes=["Logical client item-record capability; state is snapshot-specific."],
    ))
    graph.insert_record(con,CapabilityObservation(
        observation_id=observation_id,
        capability_id=capability_id,
        source_snapshot_id=record.snapshot_id,
        status="VERIFIED",
        value={
            "item_id":record.item_id,
            "category":record.category,
            "layout":record.layout,
            "format":record.format,
            "source_path":record.source_path,
            "record_index":record.record_index,
        },
        evidence_id=evidence_id,
        notes=["Client DAT record was decoded successfully; server availability remains separate."],
    ))
    con.commit()
    return {"capabilities":1,"observations":1,"evidence":1}


def record_to_dict(record: ClientDatRecord) -> dict[str,Any]:
    return asdict(record)
