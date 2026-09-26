"""Coverage audit for source-neutral server schema profiles."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from workbench.adapters.servers.base import SchemaProfile, TableShape


@dataclass(frozen=True)
class TableMappingCoverage:
    logical_type: str
    physical_table: str
    identity_fields: tuple[str, ...]
    mapped_logical_fields: tuple[str, ...]
    parsed_physical_fields: tuple[str, ...]
    mapped_physical_fields: tuple[str, ...]
    unmapped_parsed_fields: tuple[str, ...]
    missing_identity_mappings: tuple[str, ...]
    status: str


def table_mapping_coverage(shape: TableShape) -> TableMappingCoverage:
    mapped_logical=tuple(sorted(m.logical_name for m in shape.field_mappings))
    mapped_physical={
        physical.lower()
        for mapping in shape.field_mappings
        for physical in mapping.physical_names
    }
    parsed=tuple(shape.parse_columns)
    unmapped=tuple(sorted(
        field for field in parsed
        if field.lower() not in mapped_physical
    ))
    missing_identity=tuple(sorted(
        field for field in shape.identity_fields
        if field not in mapped_logical
    ))
    if missing_identity:
        status="IDENTITY_MAPPING_GAP"
    elif unmapped:
        status="PARTIAL_FIELD_MAPPING"
    elif shape.field_mappings:
        status="FULL_PARSE_MAPPING"
    else:
        status="NO_LOGICAL_MAPPING"
    return TableMappingCoverage(
        logical_type=shape.logical_name,
        physical_table=shape.physical_table,
        identity_fields=tuple(shape.identity_fields),
        mapped_logical_fields=mapped_logical,
        parsed_physical_fields=parsed,
        mapped_physical_fields=tuple(sorted(mapped_physical)),
        unmapped_parsed_fields=unmapped,
        missing_identity_mappings=missing_identity,
        status=status,
    )


def profile_mapping_coverage(profile: SchemaProfile) -> dict:
    tables=[
        table_mapping_coverage(shape)
        for _name,shape in sorted(profile.tables.items())
    ]
    summary={}
    for row in tables:
        summary[row.status]=summary.get(row.status,0)+1
    return {
        "schema":1,
        "kind":"SERVER_SCHEMA_MAPPING_COVERAGE",
        "profile_id":profile.profile_id,
        "family":profile.family,
        "summary":dict(sorted(summary.items())),
        "tables":[asdict(row) for row in tables],
    }


def compare_profile_coverage(profiles: Iterable[SchemaProfile]) -> dict:
    profiles=tuple(profiles)
    by_family={profile.family:profile_mapping_coverage(profile) for profile in profiles}
    logical_types=sorted({
        name
        for profile in profiles
        for name in profile.tables
    })
    matrix=[]
    for logical_type in logical_types:
        row={"logical_type":logical_type,"families":{}}
        for profile in profiles:
            shape=profile.tables.get(logical_type)
            if shape is None:
                row["families"][profile.family]={"status":"MISSING_LOGICAL_TYPE"}
            else:
                coverage=table_mapping_coverage(shape)
                row["families"][profile.family]={
                    "status":coverage.status,
                    "physical_table":coverage.physical_table,
                    "identity_fields":list(coverage.identity_fields),
                    "mapped_logical_fields":list(coverage.mapped_logical_fields),
                    "unmapped_parsed_fields":list(coverage.unmapped_parsed_fields),
                }
        matrix.append(row)
    return {
        "schema":1,
        "kind":"SERVER_SCHEMA_MAPPING_MATRIX",
        "families":[profile.family for profile in profiles],
        "logical_types":logical_types,
        "profiles":by_family,
        "matrix":matrix,
    }
