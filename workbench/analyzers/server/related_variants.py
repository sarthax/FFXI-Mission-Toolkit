#!/usr/bin/env python3
"""Conservative related-variant/shared-system discovery for zone mob scripts.

A same-stem script in another zone is not automatically a dependency. This analyzer only promotes
related variants when at least two sibling zone variants independently reference the same
xi.<system> namespace. The resulting edges are review-visible conditional relationships, not
default package requirements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from workbench.analyzers.server.lua_dependencies import _artifact_id
from workbench.core.provenance import snapshot_id
from workbench.core.schema import Artifact, DependencyEdge, Evidence, record_dict


SYSTEM_CALL_RE=re.compile(r"""\bxi\.(?P<system>[A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_][A-Za-z0-9_]*\s*\(""")
GENERIC_NAMESPACES={
    "mobskill","mobskills","zone","title","item","keyitem","effect","msg","quest","mission",
}


def _slug(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _record(value):
    return record_dict(value)


def _systems(text: str) -> set[str]:
    return {
        match.group("system")
        for match in SYSTEM_CALL_RE.finditer(text)
        if match.group("system").lower() not in GENERIC_NAMESPACES
    }


def analyze_related_variants(
    root: Path,
    script: Path,
    *,
    source_snapshot_id: str | None = None,
) -> dict[str,Any]:
    root=Path(root)
    script=Path(script)
    sid=source_snapshot_id or snapshot_id(root)
    rel=script.relative_to(root).as_posix() if script.is_relative_to(root) else script.as_posix()
    source_id=_artifact_id(sid,rel)

    artifacts: dict[str,Artifact]={
        source_id:Artifact(
            source_id,"LUA",rel,sid,
            metadata={"analysis_role":"RELATED_VARIANT_SOURCE"},
        )
    }
    evidence: dict[str,Evidence]={}
    edges: list[DependencyEdge]=[]

    candidates=[]
    mobs_root=root/"scripts/zones"
    if mobs_root.is_dir():
        for candidate in sorted(mobs_root.glob(f"*/mobs/{script.name}")):
            if candidate.resolve()==script.resolve():
                continue
            text=candidate.read_text(encoding="utf-8",errors="replace")
            systems=_systems(text)
            if systems:
                candidates.append((candidate,systems))

    systems_to_variants: dict[str,list[Path]]={}
    for candidate,systems in candidates:
        for system in systems:
            systems_to_variants.setdefault(system,[]).append(candidate)

    coupled={
        system:sorted(paths)
        for system,paths in systems_to_variants.items()
        if len({path.parts[-3] for path in paths})>=2
    }

    for system,variants in sorted(coupled.items()):
        system_rel=f"scripts/globals/{system}.lua"
        system_path=root/system_rel
        system_id=_artifact_id(sid,system_rel)
        artifacts[system_id]=Artifact(
            system_id,
            "LUA",
            system_rel,
            sid,
            metadata={
                "analysis_role":"SHARED_SYSTEM",
                "system_namespace":system,
                "exists_in_source":system_path.is_file(),
            },
        )

        evidence_id=f"evidence:system-coupling:{_slug(sid+rel+system)}"
        variant_rels=[
            path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
            for path in variants
        ]
        evidence[evidence_id]=Evidence(
            evidence_id,
            "SERVER",
            rel,
            rel,
            sid,
            (
                f"Same-stem zone variants {variant_rels} independently call xi.{system}.*; "
                f"surface {system_rel} and those variants as conditional system coupling."
            ),
        )
        edges.append(DependencyEdge(
            edge_id=f"system-coupling:{_slug(sid+rel+system)}",
            source_node=source_id,
            target_node=system_id,
            relationship="SYSTEM_COUPLED_CONDITIONAL_DEPENDENCY",
            evidence_id=evidence_id,
            confidence="HIGH",
            status="QUESTIONABLE",
            discovered_by="related_variant_system_discovery",
            source_location=rel,
            notes=f"shared xi.{system} namespace across same-stem zone variants",
            source_snapshot_id=sid,
        ))

        for variant in variants:
            variant_rel=variant.relative_to(root).as_posix() if variant.is_relative_to(root) else variant.as_posix()
            variant_id=_artifact_id(sid,variant_rel)
            artifacts[variant_id]=Artifact(
                variant_id,
                "LUA",
                variant_rel,
                sid,
                metadata={
                    "analysis_role":"RELATED_ZONE_VARIANT",
                    "shared_system":system,
                },
            )
            veid=f"evidence:related-variant:{_slug(sid+rel+variant_rel+system)}"
            evidence[veid]=Evidence(
                veid,
                "SERVER",
                variant_rel,
                variant_rel,
                sid,
                f"Same-stem zone variant {variant_rel} calls xi.{system}.*.",
            )
            edges.append(DependencyEdge(
                edge_id=f"related-variant:{_slug(sid+rel+variant_rel+system)}",
                source_node=source_id,
                target_node=variant_id,
                relationship="RELATED_VARIANT",
                evidence_id=veid,
                confidence="HIGH",
                status="QUESTIONABLE",
                discovered_by="related_variant_system_discovery",
                source_location=variant_rel,
                notes=f"conditionally coupled through xi.{system}",
                source_snapshot_id=sid,
            ))

    return {
        "schema":1,
        "analysis":{
            "analysis_id":"related-variant-system-discovery",
            "analysis_type":"RELATED_VARIANT_SYSTEM_DISCOVERY",
            "source":rel,
            "target":None,
            "feature_id":None,
            "status":"ANALYZED",
            "created_at":None,
            "tool_version":"1",
            "findings":[],
            "notes":[
                "Same-name/same-stem alone is not dependency evidence.",
                "A shared system is surfaced only when at least two separate zone variants independently call the same non-generic xi namespace.",
                "RELATED_VARIANT and SYSTEM_COUPLED_CONDITIONAL_DEPENDENCY are intentionally excluded from default package closure.",
            ],
            "source_snapshot_id":sid,
        },
        "artifacts":[_record(x) for x in artifacts.values()],
        "evidence":[_record(x) for x in evidence.values()],
        "edges":[_record(x) for x in edges],
        "summary":{
            "candidate_variants":len(candidates),
            "shared_systems":len(coupled),
            "related_variant_edges":sum(1 for edge in edges if edge.relationship=="RELATED_VARIANT"),
            "conditional_system_edges":sum(
                1 for edge in edges
                if edge.relationship=="SYSTEM_COUPLED_CONDITIONAL_DEPENDENCY"
            ),
        },
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("script",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    payload=analyze_related_variants(args.root,args.script)
    data=json.dumps(payload,indent=2,sort_keys=True)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(data+"\n",encoding="utf-8")
    else:
        print(data)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
