"""Translate unsupported-route probes into conservative migration actions."""
from __future__ import annotations

from workbench.core.schema import MigrationAction
from workbench.migrations.backend_probe import LuaRouteProbe


def plan_lsb_dsp_lua_probe(
    probe: LuaRouteProbe,
    migration_id: str,
    *,
    artifact_id: str | None = None,
    source_path: str | None = None,
) -> MigrationAction:
    metadata={
        "route":probe.route,
        "probe_status":probe.status,
        "flagged_count":probe.flagged_count,
        "leftover_count":probe.leftover_count,
        "source_path":source_path,
    }
    if probe.method_surface is not None:
        metadata.update({
            "framework_methods":list(probe.method_surface.framework_methods),
            "binding_candidate_methods":list(probe.method_surface.binding_candidate_methods),
            "method_definitions":list(probe.method_surface.method_definitions),
        })

    if probe.status=="FRAMEWORK_ADAPTATION_REQUIRED":
        reason=(
            "LSB framework-object orchestration must be represented using the target fork's "
            "legacy callback/script structure; this is not a simple binding rename."
        )
        adaptation="STRUCTURAL_FRAMEWORK_ADAPTATION"
    elif probe.status=="GAPS_FOUND":
        reason="The deterministic converter probe found flagged or unresolved source constructs."
        adaptation="CONVERTER_GAP"
    else:
        reason=(
            "The probe found no immediate textual gaps, but LSB->DSP Lua conversion is not yet "
            "a registered verified backend."
        )
        adaptation="UNVERIFIED_ROUTE"

    metadata["adaptation_type"]=adaptation
    return MigrationAction(
        action_id=f"probe:{migration_id}:{artifact_id or source_path or 'lua'}",
        migration_id=migration_id,
        action="MANUAL_REVIEW",
        artifact_id=artifact_id,
        status="MANUAL_REQUIRED",
        reason=reason,
        metadata=metadata,
    )
