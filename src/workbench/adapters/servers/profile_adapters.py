"""Concrete profile-backed server adapters."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence
from .base import LogicalRecord, ServerAdapter, SchemaProfile
from .profiles import DSP, LSB, TOPAZ, TOPAZ_NEXT


class ProfileServerAdapter(ServerAdapter):
    profile: SchemaProfile

    @property
    def schema_profile(self) -> SchemaProfile:
        return self.profile


class TopazAdapter(ProfileServerAdapter):
    adapter_id = "topaz"
    family = "TOPAZ"
    profile = TOPAZ


class TopazNextAdapter(ProfileServerAdapter):
    adapter_id = "topaz-next"
    family = "TOPAZ_NEXT"
    profile = TOPAZ_NEXT


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


class CustomForkAdapter(ProfileServerAdapter):
    """Explicit custom-fork adapter.

    A custom fork must declare the schema profile it is based on. The Workbench
    does not infer a lineage from filenames or directory names because doing so
    can silently hide fork-specific schema drift.
    """

    family = "CUSTOM"

    def __init__(
        self,
        root: Path,
        *,
        fork_id: str,
        base_profile: SchemaProfile,
        table_overrides: Mapping[str, Any] | None = None,
        notes: Sequence[str] = (),
    ):
        super().__init__(root)
        normalized=fork_id.strip()
        if not normalized:
            raise ValueError("fork_id is required for CustomForkAdapter")
        tables=dict(base_profile.tables)
        if table_overrides:
            tables.update(table_overrides)
        self.adapter_id=f"custom:{normalized}"
        self.family=f"CUSTOM:{normalized}"
        self.profile=SchemaProfile(
            profile_id=f"custom:{normalized}",
            family=self.family,
            tables=tables,
            version_hint=base_profile.version_hint,
            notes=(
                f"Custom fork derived explicitly from schema profile {base_profile.profile_id}.",
                *base_profile.notes,
                *tuple(notes),
            ),
        )


def adapter_for(family: str, root: Path) -> ServerAdapter:
    key = family.strip().lower()
    if key == "topaz":
        return TopazAdapter(root)
    if key in {"topaz-next", "topaz_next"}:
        return TopazNextAdapter(root)
    if key in {"dsp", "darkstar", "darkstarproject"}:
        return DSPAdapter(root)
    if key in {"lsb", "landsandboat", "land-sand-boat"}:
        return LSBAdapter(root)
    raise ValueError(f"Unsupported server family: {family}")
