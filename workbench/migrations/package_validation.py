"""Validation package metadata for staged Workbench migrations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    validation_type: str
    required: bool = True
    artifact_paths: tuple[str, ...] = ()
    metadata: dict | None = None


def build_validation_package(manifest: dict) -> dict:
    steps=manifest.get("execution",{}).get("steps",[])
    lua=tuple(sorted({s["path"] for s in steps if s.get("backend")=="lua" and s.get("path")}))
    sql=tuple(sorted({s["path"] for s in steps if s.get("backend")=="sql" and s.get("path")}))
    generated_sql=tuple(sorted({
        item["path"]
        for item in manifest.get("generated_artifacts",[])
        if str(item.get("artifact_type","")).upper()=="SQL" and item.get("path")
    }))
    all_sql=tuple(sorted(set(sql) | set(generated_sql)))

    checks=[]
    unsupported=tuple(
        step for step in steps
        if step.get("backend") in {"lua","sql"} and step.get("conversion_status")=="UNSUPPORTED"
    )
    if lua:
        checks.extend([
            ValidationCheck("lua-sanity","LUA_SANITY",True,lua),
            ValidationCheck("binding-audit","BINDING_AUDIT",True,lua),
        ])
    if all_sql:
        checks.extend([
            ValidationCheck("sql-collision","SQL_ID_COLLISION",True,all_sql),
            ValidationCheck("sql-duplication","SQL_CONTENT_DUPLICATION",True,all_sql),
        ])
    if generated_sql:
        checks.append(ValidationCheck(
            "generated-target-sql",
            "GENERATED_TARGET_SQL",
            True,
            generated_sql,
            {"generated_count":len(generated_sql),"conversion_required":False},
        ))
    if unsupported:
        checks.append(ValidationCheck(
            "converter-backend",
            "CONVERTER_BACKEND_SUPPORT",
            True,
            tuple(sorted(str(step.get("path")) for step in unsupported if step.get("path"))),
            {"unsupported_count":len(unsupported)},
        ))

    migration_status=manifest.get("migration",{}).get("status")
    if migration_status=="BLOCKED":
        status="BLOCKED"
    elif unsupported:
        status="MANUAL_REQUIRED"
    else:
        status="READY"

    return {
        "schema":1,
        "kind":"WORKBENCH_VALIDATION_PACKAGE",
        "migration":dict(manifest.get("migration",{})),
        "checks":[
            {
                "check_id":c.check_id,
                "validation_type":c.validation_type,
                "required":c.required,
                "artifact_paths":list(c.artifact_paths),
                "metadata":dict(c.metadata or {}),
            }
            for c in checks
        ],
        "status":status,
    }
