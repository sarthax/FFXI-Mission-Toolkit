"""Compare generic instance feature slices across server adapters."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from workbench.adapters.servers.base import LogicalRecord
from workbench.adapters.servers.logical import LogicalComparison, compare_records
from workbench.core.schema import MigrationAction
from workbench.migrations.instance_feature_slice import InstanceFeatureSlice
from workbench.migrations.logical_planner import plan_logical_comparison


@dataclass(frozen=True)
class SliceComparison:
    migration_id: str
    source_instance_id: int
    target_instance_id: int
    actions: tuple[MigrationAction, ...]
    comparisons: tuple[LogicalComparison, ...]


def _key(record: LogicalRecord):
    return (record.logical_type, record.identity)


def _records(slice_: InstanceFeatureSlice) -> list[LogicalRecord]:
    rows=[]
    if slice_.instance is not None:
        rows.append(slice_.instance)
    rows.extend(slice_.instance_entities)
    rows.extend(slice_.npcs)
    rows.extend(slice_.mob_spawns)
    rows.extend(slice_.mob_groups)
    rows.extend(slice_.mob_pools)
    rows.extend(slice_.mob_drops)
    return rows


def compare_instance_slices(source: InstanceFeatureSlice, target: InstanceFeatureSlice, migration_id: str) -> SliceComparison:
    source_map={_key(r):r for r in _records(source)}
    target_map={_key(r):r for r in _records(target)}
    actions=[]
    comparisons=[]

    for key,source_record in sorted(source_map.items(),key=lambda item:str(item[0])):
        target_record=target_map.get(key)
        if target_record is None:
            actions.append(MigrationAction(
                action_id=f"missing-target:{source_record.logical_type}:{hash(str(key)) & 0xffffffff:08x}",
                migration_id=migration_id,
                action="IMPLEMENT",
                status="MANUAL_REQUIRED",
                reason="Source logical record is required by the feature slice but no target logical record with the same identity exists.",
                metadata={
                    "logical_type":source_record.logical_type,
                    "identity":list(source_record.identity),
                    "source_family":source_record.source_family,
                    "target_instance_id":target.instance_id,
                },
            ))
            continue
        comparison=compare_records(source_record,target_record)
        comparisons.append(comparison)
        actions.extend(plan_logical_comparison(comparison,migration_id))

    return SliceComparison(
        migration_id=migration_id,
        source_instance_id=source.instance_id,
        target_instance_id=target.instance_id,
        actions=tuple(actions),
        comparisons=tuple(comparisons),
    )
