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

    checks=[]
    if lua:
        checks.extend([
            ValidationCheck("lua-sanity","LUA_SANITY",True,lua),
            ValidationCheck("binding-audit","BINDING_AUDIT",True,lua),
        ])
    if sql:
        checks.extend([
            ValidationCheck("sql-collision","SQL_ID_COLLISION",True,sql),
            ValidationCheck("sql-duplication","SQL_CONTENT_DUPLICATION",True,sql),
        ])

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
        "status":"READY" if manifest.get("migration",{}).get("status")!="BLOCKED" else "BLOCKED",
    }
