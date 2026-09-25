"""Generic migration backend registry.

Backends advertise exact source/target/language support. Existing specialized
converters are wrapped without widening their authority beyond combinations they
were built and tested for.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import backport_lua_convert as legacy_lua
import backport_sql_convert as legacy_sql
from workbench.migrations.backend_probe import classify_lsb_lua_methods


@dataclass(frozen=True)
class BackendResult:
    backend_id: str
    status: str
    output: str
    issues: tuple[dict[str, Any], ...] = ()


class MigrationBackend(Protocol):
    backend_id: str
    support_level: str
    def supports(self, source_family: str, target_family: str, artifact_type: str) -> bool: ...


class LegacyTopazDspLuaBackend:
    backend_id="legacy.topaz_to_dsp.lua"
    support_level="SUPPORTED"

    def supports(self, source_family: str, target_family: str, artifact_type: str) -> bool:
        return (
            source_family.upper()=="TOPAZ"
            and target_family.upper()=="DSP"
            and artifact_type.upper()=="LUA"
        )

    def convert(self, text: str, **options: Any) -> BackendResult:
        result=legacy_lua.convert(
            text,
            zone_table=options.get("zone_table"),
            id_shape=options.get("id_shape"),
            id_file_hint=options.get("id_file_hint"),
            target="old_dsp_reference",
        )
        return BackendResult(
            backend_id=self.backend_id,
            status="MANUAL_REQUIRED" if result.flagged else "CONVERTED",
            output=result.converted,
            issues=tuple(result.flagged),
        )


class LegacyTopazDspSqlBackend:
    backend_id="legacy.topaz_to_dsp.sql"
    support_level="SUPPORTED"

    def supports(self, source_family: str, target_family: str, artifact_type: str) -> bool:
        return (
            source_family.upper()=="TOPAZ"
            and target_family.upper()=="DSP"
            and artifact_type.upper()=="SQL"
        )

    def convert(self, table: str, rows: list[list[str]], **options: Any) -> BackendResult:
        schema_map=options.get("schema_map") or legacy_sql.load_schema_map()
        result=legacy_sql.convert_table(table,rows,schema_map)
        return BackendResult(
            backend_id=self.backend_id,
            status="MANUAL_REQUIRED" if result.warnings else "CONVERTED",
            output=result.converted_sql,
            issues=tuple(result.warnings),
        )


class ConditionalLsbDspLuaBackend:
    """First conservative LSB->DSP Lua backend.

    This backend is route-aware but content-gated. It refuses modern xi.* namespaces
    and LSB framework-object orchestration until dedicated, evidence-backed reshape
    rules exist. Only the proven-safe residual subset is passed through the legacy
    deterministic Lua converter.
    """
    backend_id="conditional.lsb_to_dsp.lua"
    support_level="CONDITIONAL"

    def supports(self, source_family: str, target_family: str, artifact_type: str) -> bool:
        return (
            source_family.upper()=="LSB"
            and target_family.upper()=="DSP"
            and artifact_type.upper()=="LUA"
        )

    def convert(self, text: str, **options: Any) -> BackendResult:
        surface=classify_lsb_lua_methods(text)
        issues=[]

        if surface.framework_methods:
            issues.append({
                "type":"STRUCTURAL_FRAMEWORK_ADAPTATION",
                "methods":list(surface.framework_methods),
                "message":"LSB framework-object methods require target-specific structural adaptation.",
            })

        if "xi." in text:
            issues.append({
                "type":"UNVERIFIED_XI_NAMESPACE",
                "message":"Modern xi.* namespace conversion is not yet proven safe for legacy DSP.",
            })

        if issues:
            return BackendResult(
                backend_id=self.backend_id,
                status="MANUAL_REQUIRED",
                output=text,
                issues=tuple(issues),
            )

        result=legacy_lua.convert(
            text,
            zone_table=options.get("zone_table"),
            id_shape=options.get("id_shape"),
            id_file_hint=options.get("id_file_hint"),
            target="old_dsp_reference",
        )
        converter_issues=tuple(result.flagged)+tuple(result.unflagged_leftovers())
        return BackendResult(
            backend_id=self.backend_id,
            status="MANUAL_REQUIRED" if converter_issues else "CONVERTED",
            output=result.converted,
            issues=converter_issues,
        )


class MigrationBackendRegistry:
    def __init__(self) -> None:
        self._backends: list[MigrationBackend] = []

    def register(self, backend: MigrationBackend) -> None:
        if any(existing.backend_id==backend.backend_id for existing in self._backends):
            raise ValueError(f"Duplicate migration backend: {backend.backend_id}")
        self._backends.append(backend)

    def resolve(self, source_family: str, target_family: str, artifact_type: str) -> MigrationBackend | None:
        matches=[
            backend for backend in self._backends
            if backend.supports(source_family,target_family,artifact_type)
        ]
        if len(matches)>1:
            raise ValueError(
                f"Ambiguous migration backends for {source_family}->{target_family} {artifact_type}: "
                f"{[backend.backend_id for backend in matches]}"
            )
        return matches[0] if matches else None

    def backends(self) -> tuple[MigrationBackend, ...]:
        return tuple(self._backends)


def default_backend_registry() -> MigrationBackendRegistry:
    registry=MigrationBackendRegistry()
    registry.register(LegacyTopazDspLuaBackend())
    registry.register(LegacyTopazDspSqlBackend())
    registry.register(ConditionalLsbDspLuaBackend())
    return registry
