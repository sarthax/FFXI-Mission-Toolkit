"""Concrete profile-backed server adapters."""
from __future__ import annotations
from pathlib import Path
from .base import ServerAdapter, SchemaProfile
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
