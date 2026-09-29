"""Conservative cross-zone/shared-system lifecycle coupling discovery for LSB-style Lua.

A candidate alternate script is never linked merely because it shares a filename. It must also
contain explicit xi.<system>.onMob* lifecycle calls, and at least two distinct lifecycle hooks must
delegate to the same system module before the relationship is surfaced.

The output is evidence for review, not proof that every variant must ship together.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from workbench.core.schema import Artifact, Evidence, record_dict
from workbench.core.services.conditional_dependencies import (
    ConditionalDependency,
    project_conditional_dependency,
)

LIFECYCLE_METHODS = {
    "onMobInitialize",
    "onMobSpawn",
    "onMobDeath",
    "onMobDespawn",
}
CALL_RE = re.compile(
    r"\bxi\.([A-Za-z_][A-Za-z0-9_]*)\.(onMobInitialize|onMobSpawn|onMobDeath|onMobDespawn)\s*\("
)


def _artifact_id(snapshot: str, rel: str) -> str:
    safe=rel.replace("\\","/")
    return f"artifact:{snapshot}:{safe}"


def _line_number(text: str, offset: int) -> int:
    return text.count("\n",0,offset)+1


def _scan_lifecycle_calls(path: Path) -> dict[str, dict[str, Any]]:
    text=path.read_text(encoding="utf-8",errors="ignore")
    systems: dict[str, dict[str, Any]]={}
    for match in CALL_RE.finditer(text):
        system,method=match.groups()
        row=systems.setdefault(system,{"methods":set(),"lines":[]})
        row["methods"].add(method)
        row["lines"].append(_line_number(text,match.start()))
    return {
        system:{
            "methods":tuple(sorted(row["methods"])),
            "lines":tuple(sorted(set(row["lines"]))),
        }
        for system,row in systems.items()
        if len(row["methods"])>=2
    }


def analyze_cross_zone_system_coupling(
    root: Path,
    root_script: Path,
    *,
    source_snapshot_id: str,
) -> dict:
    """Discover reviewable cross-zone lifecycle coupling around one mob script."""
    root=Path(root)
    root_script=Path(root_script)
    try:
        root_rel=root_script.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("root_script must be inside root") from exc

    parts=root_rel.split("/")
    if len(parts)<5 or parts[0:2]!=["scripts","zones"] or "mobs" not in parts:
        raise ValueError("root_script must be an LSB-style scripts/zones/<zone>/mobs/<name>.lua path")

    script_name=root_script.name
    root_artifact=Artifact(
        _artifact_id(source_snapshot_id,root_rel),
        "LUA",root_rel,source_snapshot_id,
        metadata={"analysis_role":"SYSTEM_COUPLING_ROOT"},
    )

    candidates=sorted(
        p for p in (root/"scripts"/"zones").glob(f"*/mobs/{script_name}")
        if p.is_file() and p.resolve()!=root_script.resolve()
    )

    artifacts={root_artifact.artifact_id:root_artifact}
    evidence=[]
    entities=[]
    edges=[]
    groups: dict[str,list[tuple[Path,dict[str,Any]]]]={}

    for candidate in candidates:
        calls=_scan_lifecycle_calls(candidate)
        for system,details in calls.items():
            groups.setdefault(system,[]).append((candidate,details))

    for system,rows in sorted(groups.items()):
        module=root/"scripts"/"globals"/f"{system}.lua"
        if not module.is_file():
            continue
        module_rel=module.relative_to(root).as_posix()
        module_artifact=Artifact(
            _artifact_id(source_snapshot_id,module_rel),
            "LUA",module_rel,source_snapshot_id,
            metadata={"analysis_role":"SHARED_LIFECYCLE_SYSTEM","system":system},
        )
        artifacts[module_artifact.artifact_id]=module_artifact

        all_methods=sorted({m for _path,details in rows for m in details["methods"]})
        variant_rels=[path.relative_to(root).as_posix() for path,_details in rows]
        system_eid=f"evidence:system-coupling:{source_snapshot_id}:{system}:{script_name}"
        evidence.append(Evidence(
            system_eid,
            "SERVER_SOURCE",
            source_snapshot_id,
            location=";".join(variant_rels),
            snapshot=source_snapshot_id,
            notes=(
                f"Alternate {script_name} implementations explicitly delegate lifecycle hooks "
                f"{all_methods} to xi.{system}; surfaced as a conditional system dependency."
            ),
        ))

        system_projection=project_conditional_dependency(ConditionalDependency(
            root_artifact.artifact_id,
            module_artifact.artifact_id,
            f"Shared lifecycle system: xi.{system}",
            conditions=(
                {
                    "subject":f"cross-zone-variant:{script_name}",
                    "operator":"DELEGATES_LIFECYCLE_TO",
                    "value":f"xi.{system}",
                },
            ),
            rationale=(
                "Alternate cross-zone implementations explicitly delegate multiple mob lifecycle "
                "hooks to this shared module; review whether the root feature depends on the same "
                "system-level lifecycle semantics."
            ),
            evidence_id=system_eid,
            confidence="INFERRED",
            source_snapshot_id=source_snapshot_id,
            source_location=";".join(variant_rels),
            metadata={
                "detector":"lsb_shared_lifecycle_module",
                "system":system,
                "lifecycle_methods":all_methods,
                "variant_count":len(rows),
            },
        ))
        entities.append(system_projection.gate)
        edges.extend(system_projection.edges)

        for path,details in rows:
            rel=path.relative_to(root).as_posix()
            artifact=Artifact(
                _artifact_id(source_snapshot_id,rel),
                "LUA",rel,source_snapshot_id,
                metadata={
                    "analysis_role":"CROSS_ZONE_SYSTEM_VARIANT",
                    "system":system,
                    "lifecycle_methods":list(details["methods"]),
                },
            )
            artifacts[artifact.artifact_id]=artifact
            variant_eid=f"evidence:system-coupling:{source_snapshot_id}:{system}:{rel}"
            evidence.append(Evidence(
                variant_eid,
                "SERVER_SOURCE",
                source_snapshot_id,
                location=f"{rel}:L{','.join(str(x) for x in details['lines'])}",
                snapshot=source_snapshot_id,
                notes=(
                    f"{rel} explicitly calls xi.{system} lifecycle hooks "
                    f"{list(details['methods'])}."
                ),
            ))
            projection=project_conditional_dependency(ConditionalDependency(
                module_artifact.artifact_id,
                artifact.artifact_id,
                f"Cross-zone lifecycle variant: {rel}",
                conditions=(
                    {
                        "subject":f"system:xi.{system}",
                        "operator":"HAS_LIFECYCLE_VARIANT",
                        "value":rel,
                    },
                ),
                rationale=(
                    "This alternate implementation explicitly participates in the shared lifecycle "
                    "system and must be reviewed rather than silently included or excluded."
                ),
                evidence_id=variant_eid,
                confidence="VERIFIED",
                source_snapshot_id=source_snapshot_id,
                source_location=rel,
                metadata={
                    "detector":"lsb_shared_lifecycle_module",
                    "system":system,
                    "lifecycle_methods":list(details["methods"]),
                },
            ))
            entities.append(projection.gate)
            edges.extend(projection.edges)

    return {
        "schema":1,
        "analysis":{
            "analysis_id":"cross-zone-system-coupling",
            "analysis_type":"LSB_SHARED_LIFECYCLE_SYSTEM_COUPLING",
            "source":root_rel,
            "target":None,
            "feature_id":None,
            "status":"ANALYZED",
            "created_at":None,
            "tool_version":"1",
            "findings":[],
            "notes":[
                "Same-name candidate discovery alone is insufficient.",
                "A candidate is surfaced only when it explicitly delegates at least two supported lifecycle hooks to one xi.<system> module.",
                "Discovered dependencies remain conditional/reviewable rather than ordinary REQUIRED truth.",
            ],
            "source_snapshot_id":source_snapshot_id,
        },
        "artifacts":[record_dict(x) for x in artifacts.values()],
        "entities":[record_dict(x) for x in entities],
        "evidence":[record_dict(x) for x in evidence],
        "edges":[record_dict(x) for x in edges],
        "summary":{
            "candidate_variant_files":len(candidates),
            "shared_systems":len(groups),
            "qualified_systems":sum(
                1 for system in groups
                if (root/"scripts"/"globals"/f"{system}.lua").is_file()
            ),
            "conditional_gate_nodes":len(entities),
            "conditional_edges":len(edges),
        },
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("root_script",type=Path)
    ap.add_argument("--snapshot",required=True)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    payload=analyze_cross_zone_system_coupling(
        args.root,args.root_script,source_snapshot_id=args.snapshot
    )
    data=json.dumps(payload,indent=2,sort_keys=True)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(data+"\n",encoding="utf-8")
    else:
        print(data)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
