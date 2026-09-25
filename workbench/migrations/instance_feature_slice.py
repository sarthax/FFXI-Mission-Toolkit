"""Generic instance-backed feature slice extraction.

This is intentionally not Assault-specific. Any FFXI feature represented by an
instance_list row plus instance_entities membership can use the same logical
slice as input to migration comparison/planning.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from workbench.adapters.servers.base import LogicalRecord, ServerAdapter
from workbench.adapters.servers.sql_extract import extract_logical_records


@dataclass(frozen=True)
class InstanceFeatureSlice:
    instance_id: int
    instance: LogicalRecord | None
    instance_entities: tuple[LogicalRecord, ...]
    npcs: tuple[LogicalRecord, ...]
    mob_spawns: tuple[LogicalRecord, ...]
    mob_groups: tuple[LogicalRecord, ...]
    mob_pools: tuple[LogicalRecord, ...]
    mob_drops: tuple[LogicalRecord, ...]

    def counts(self) -> dict[str,int]:
        return {
            "instance": 1 if self.instance else 0,
            "instance_entities": len(self.instance_entities),
            "npcs": len(self.npcs),
            "mob_spawns": len(self.mob_spawns),
            "mob_groups": len(self.mob_groups),
            "mob_pools": len(self.mob_pools),
            "mob_drops": len(self.mob_drops),
        }


def _identity(record: LogicalRecord) -> dict[str,Any]:
    return dict(record.identity)


def extract_instance_feature_slice(adapter: ServerAdapter, instance_id: int) -> InstanceFeatureSlice:
    instances=extract_logical_records(adapter,"instances")
    instance=next((r for r in instances if r.fields.get("instance_id")==instance_id),None)

    members=tuple(
        r for r in extract_logical_records(adapter,"instance_entities")
        if r.fields.get("instance_id")==instance_id
    )
    entity_ids={r.fields.get("entity_id") for r in members}

    npcs=tuple(
        r for r in extract_logical_records(adapter,"npc")
        if r.fields.get("npc_id") in entity_ids
    )
    spawns=tuple(
        r for r in extract_logical_records(adapter,"mob_spawns")
        if r.fields.get("mob_id") in entity_ids
    )

    group_ids={r.fields.get("group_id") for r in spawns if r.fields.get("group_id") is not None}
    groups=tuple(
        r for r in extract_logical_records(adapter,"mob_groups")
        if r.fields.get("group_id") in group_ids
    )

    pool_ids={r.fields.get("pool_id") for r in groups if r.fields.get("pool_id") is not None}
    pools=tuple(
        r for r in extract_logical_records(adapter,"mob_pools")
        if r.fields.get("pool_id") in pool_ids
    )

    drop_ids={r.fields.get("drop_id") for r in groups if r.fields.get("drop_id") not in (None,0)}
    drops=tuple(
        r for r in extract_logical_records(adapter,"mob_drops")
        if r.fields.get("drop_id") in drop_ids
    )

    return InstanceFeatureSlice(
        instance_id=instance_id,
        instance=instance,
        instance_entities=members,
        npcs=npcs,
        mob_spawns=spawns,
        mob_groups=groups,
        mob_pools=pools,
        mob_drops=drops,
    )
