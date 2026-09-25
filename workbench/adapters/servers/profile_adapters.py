"""Concrete profile-backed server adapters."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence
from .base import LogicalRecord, ServerAdapter, SchemaProfile
from .profiles import DSP, LSB, TOPAZ


class ProfileServerAdapter(ServerAdapter):
    profile: SchemaProfile

    @property
    def schema_profile(self) -> SchemaProfile:
        return self.profile


class TopazAdapter(ProfileServerAdapter):
    adapter_id = "topaz"
    family = "TOPAZ"
    profile = TOPAZ


class DSPAdapter(ProfileServerAdapter):
    adapter_id = "dsp"
    family = "DSP"
    profile = DSP

    def normalize_rows(
        self,
        logical_name: str,
        rows: Sequence[Mapping[str, Any]],
        related_records: Mapping[str, Sequence[LogicalRecord]] | None = None,
    ) -> list[LogicalRecord]:
        records=super().normalize_rows(logical_name,rows,related_records)
        if logical_name!="mob_groups" or not related_records:
            return records
        pools=related_records.get("mob_pools",())
        pool_names={record.fields.get("pool_id"):record.fields.get("name") for record in pools}
        enriched=[]
        for record in records:
            if record.fields.get("name") is not None:
                enriched.append(record)
                continue
            pool_id=record.fields.get("pool_id")
            name=pool_names.get(pool_id)
            if name is None:
                enriched.append(record)
                continue
            fields=dict(record.fields); fields["name"]=name
            enriched.append(replace(
                record,
                fields=fields,
                notes=record.notes+("Derived logical mob-group name from normalized DSP mob_pools via pool_id.",),
            ))
        return enriched


class LSBAdapter(ProfileServerAdapter):
    adapter_id = "landsandboat"
    family = "LSB"
    profile = LSB


def adapter_for(family: str, root: Path) -> ServerAdapter:
    key = family.strip().lower()
    if key in {"topaz", "topaz-next", "topaz_next"}:
        return TopazAdapter(root)
    if key in {"dsp", "darkstar", "darkstarproject"}:
        return DSPAdapter(root)
    if key in {"lsb", "landsandboat", "land-sand-boat"}:
        return LSBAdapter(root)
    raise ValueError(f"Unsupported server family: {family}")
