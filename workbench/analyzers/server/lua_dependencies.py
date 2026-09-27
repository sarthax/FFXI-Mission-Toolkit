#!/usr/bin/env python3
"""Conservative Lua dependency discovery for server scripts.

This analyzer intentionally proves only dependencies that can be derived from local source text and
optional zone identity data:

- require('path') -> Lua artifact dependency
- ID.mob.SYMBOL arithmetic/ranges -> concrete server entity dependencies when the symbol can be
  resolved through IDs.lua GetFirstID(...) plus zone mobs.yaml entity/template data

Unknown or ambiguous references become explicit Findings rather than disappearing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from workbench.core.provenance import snapshot_id
from workbench.core.schema import Artifact, DependencyEdge, Entity, Evidence, Finding, record_dict


REQUIRE_RE = re.compile(r"""require\s*\(\s*(['"])(?P<path>[^'"]+)\1\s*\)""")
FIRST_ID_RE = re.compile(
    r"""(?m)^\s*(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*GetFirstID\(\s*(['"])(?P<template>[^'"]+)\2\s*\)"""
)
MOB_OFFSET_RE = re.compile(
    r"""ID\.mob\.(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)\s*\+\s*(?P<offset>\d+)"""
)
MOB_RANGE_RE = re.compile(
    r"""for\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*ID\.mob\.(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)\s*\+\s*(?P<start>\d+)\s*,\s*ID\.mob\.(?P=symbol)\s*\+\s*(?P<end>\d+)\s*do"""
)
TEXT_REF_RE = re.compile(r"""ID\.text\.(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)""")
TITLE_REF_RE = re.compile(r"""xi\.title\.(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)""")
NUMERIC_SYMBOL_RE = re.compile(
    r"""(?m)^\s*(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>0x[0-9A-Fa-f]+|\d+)\s*,?"""
)


def _slug(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _artifact_id(snapshot: str, path: str) -> str:
    return f"artifact:lua:{_slug(snapshot)}:{path}"


def _entity_node_id(snapshot: str, zone_id: int | None, entity_id: int) -> str:
    zone = "unknown" if zone_id is None else str(zone_id)
    return f"entity:server:{_slug(snapshot)}:{zone}:{entity_id}"


def _evidence_id(snapshot: str, source_path: str, line: int, kind: str, target: str) -> str:
    return f"evidence:lua-dep:{_slug(snapshot)}:{_slug(source_path)}:{line}:{kind}:{_slug(target)}"


def _line(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def normalize_require_path(path: str) -> str:
    clean = str(path).strip().replace("\\", "/").lstrip("/")
    if not clean.endswith(".lua"):
        clean += ".lua"
    return clean


def load_zone_entities(path: Path) -> dict[str, Any]:
    """Load enough of modern LSB mobs.yaml to resolve first-template IDs and entity metadata."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    templates = payload.get("templates") or {}
    entities = payload.get("entities") or {}
    by_id: dict[int, dict[str, Any]] = {}
    template_ids: dict[str, list[int]] = {}

    for raw_id, row in entities.items():
        try:
            entity_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if not isinstance(row, dict):
            continue
        template = row.get("template")
        metadata = {
            "entity_id": entity_id,
            "template": template,
            "script": row.get("script"),
            "region": row.get("region"),
            "level": row.get("level"),
        }
        if template and isinstance(templates.get(template), dict):
            template_row = templates[template]
            metadata.update({
                "template_id": template_row.get("id"),
                "species": template_row.get("species"),
                "skill_list_id": template_row.get("skill_list_id"),
                "spell_list_id": template_row.get("spell_list_id"),
            })
        by_id[entity_id] = metadata
        if template:
            template_ids.setdefault(str(template), []).append(entity_id)

    for ids in template_ids.values():
        ids.sort()
    return {"templates": templates, "entities": by_id, "template_ids": template_ids}


def parse_first_id_symbols(ids_lua: Path, zone_data: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Resolve ID.mob symbols defined as GetFirstID('Template') only when one first ID is provable."""
    text = Path(ids_lua).read_text(encoding="utf-8", errors="replace")
    symbols: dict[str, int] = {}
    unresolved: list[dict[str, Any]] = []
    template_ids = zone_data.get("template_ids") or {}

    mob_block = re.search(r"(?s)\bmob\s*=\s*\{(?P<body>.*?)\n\s*\},", text)
    scan = mob_block.group("body") if mob_block else text
    base_offset = mob_block.start("body") if mob_block else 0

    for match in FIRST_ID_RE.finditer(scan):
        symbol = match.group("symbol")
        template = match.group("template")
        candidates = list(template_ids.get(template) or ())
        if candidates:
            symbols[symbol] = int(min(candidates))
        else:
            unresolved.append({
                "symbol": symbol,
                "template": template,
                "line": _line(text, base_offset + match.start()),
                "reason": "GetFirstID template has no matching entity in zone mobs.yaml.",
            })
    return symbols, unresolved


def parse_numeric_symbols(path: Path, *, table_name: str | None = None) -> dict[str,int]:
    """Parse flat Lua SYMBOL = integer assignments, optionally scoped to one table block."""
    text=Path(path).read_text(encoding="utf-8",errors="replace")
    scan=text
    if table_name:
        block=re.search(
            rf"(?s)\b{re.escape(table_name)}\s*=\s*\{{(?P<body>.*?)\n\s*\}},",
            text,
        )
        if block is None:
            return {}
        scan=block.group("body")
    result={}
    for match in NUMERIC_SYMBOL_RE.finditer(scan):
        result[match.group("symbol")]=int(match.group("value"),0)
    return result


def _record(value):
    return record_dict(value)


def analyze_script(
    root: Path,
    script: Path,
    *,
    source_snapshot_id: str | None = None,
    zone_id: int | None = None,
    ids_lua: Path | None = None,
    mobs_yaml: Path | None = None,
    titles_lua: Path | None = None,
) -> dict[str, Any]:
    root = Path(root)
    script = Path(script)
    sid = source_snapshot_id or snapshot_id(root)
    text = script.read_text(encoding="utf-8", errors="replace")
    rel = script.relative_to(root).as_posix() if script.is_relative_to(root) else script.as_posix()
    source_artifact_id = _artifact_id(sid, rel)

    artifacts: dict[str, Artifact] = {
        source_artifact_id: Artifact(
            source_artifact_id,
            "LUA",
            rel,
            sid,
            metadata={"analysis_role": "LUA_DEPENDENCY_SOURCE"},
        )
    }
    entities: dict[str, Entity] = {}
    edges: list[DependencyEdge] = []
    evidence: dict[str, Evidence] = {}
    findings: list[Finding] = []

    # require() dependencies
    for match in REQUIRE_RE.finditer(text):
        req = normalize_require_path(match.group("path"))
        line = _line(text, match.start())
        target_id = _artifact_id(sid, req)
        artifacts.setdefault(
            target_id,
            Artifact(
                target_id,
                "LUA",
                req,
                sid,
                metadata={
                    "analysis_role": "LUA_REQUIRED_ARTIFACT",
                    "exists_in_source": (root / req).is_file(),
                },
            ),
        )
        eid = _evidence_id(sid, rel, line, "require", req)
        evidence[eid] = Evidence(
            eid,
            "SERVER",
            rel,
            f"{rel}:{line}",
            sid,
            f"Lua require() dependency on {req}",
        )
        edges.append(DependencyEdge(
            edge_id=f"lua-require:{_slug(sid + rel + str(line) + req)}",
            source_node=source_artifact_id,
            target_node=target_id,
            relationship="REQUIRES",
            evidence_id=eid,
            confidence="VERIFIED",
            status="DISCOVERED",
            discovered_by="lua_dependency_discovery",
            source_location=f"{rel}:{line}",
            notes="Literal Lua require() path.",
            source_snapshot_id=sid,
        ))

    # Zone dialog/text symbols referenced by this script.
    text_symbols=parse_numeric_symbols(Path(ids_lua),table_name="text") if ids_lua and Path(ids_lua).is_file() else {}
    for match in TEXT_REF_RE.finditer(text):
        symbol=match.group("symbol")
        line=_line(text,match.start())
        value=text_symbols.get(symbol)
        if value is None:
            eid=_evidence_id(sid,rel,line,"zone-text-unresolved",symbol)
            evidence[eid]=Evidence(
                eid,"SERVER",rel,f"{rel}:{line}",sid,
                f"Could not resolve ID.text.{symbol} from the supplied zone IDs.lua text table.",
            )
            findings.append(Finding(
                finding_id=f"finding:lua-text:{_slug(eid)}",
                analysis_id="lua-dependency-discovery",
                subject_id=source_artifact_id,
                field=f"ID.text.{symbol}",
                value=None,
                status="UNKNOWN",
                confidence="UNKNOWN",
                evidence_id=eid,
                source_snapshot_id=sid,
                notes=["Zone text symbol remains unresolved."],
            ))
            continue
        node=f"zone-text:{_slug(sid)}:{'unknown' if zone_id is None else zone_id}:{value}"
        entities[node]=Entity(
            node,"ZONE_TEXT",symbol,
            metadata={
                "symbol":symbol,
                "text_id":value,
                "zone_id":zone_id,
                "definition_path":str(ids_lua),
                "source_snapshot_id":sid,
            },
        )
        eid=_evidence_id(sid,rel,line,"zone-text",f"{symbol}={value}")
        evidence[eid]=Evidence(
            eid,"SERVER",rel,f"{rel}:{line}",sid,
            f"Resolved ID.text.{symbol} to zone text id {value} from {ids_lua}.",
        )
        edges.append(DependencyEdge(
            edge_id=f"lua-zone-text:{_slug(sid + rel + str(line) + symbol + str(value))}",
            source_node=source_artifact_id,
            target_node=node,
            relationship="REQUIRES",
            evidence_id=eid,
            confidence="VERIFIED",
            status="DISCOVERED",
            discovered_by="lua_dependency_discovery",
            source_location=f"{rel}:{line}",
            notes="ZONE_TEXT_REFERENCE",
            source_snapshot_id=sid,
        ))

    # Global title symbols referenced by this script.
    title_path=Path(titles_lua) if titles_lua else root/"scripts/enum/title.lua"
    title_symbols=parse_numeric_symbols(title_path) if title_path.is_file() else {}
    for match in TITLE_REF_RE.finditer(text):
        symbol=match.group("symbol")
        line=_line(text,match.start())
        value=title_symbols.get(symbol)
        if value is None:
            eid=_evidence_id(sid,rel,line,"title-unresolved",symbol)
            evidence[eid]=Evidence(
                eid,"SERVER",rel,f"{rel}:{line}",sid,
                f"Could not resolve xi.title.{symbol} from {title_path}.",
            )
            findings.append(Finding(
                finding_id=f"finding:lua-title:{_slug(eid)}",
                analysis_id="lua-dependency-discovery",
                subject_id=source_artifact_id,
                field=f"xi.title.{symbol}",
                value=None,
                status="UNKNOWN",
                confidence="UNKNOWN",
                evidence_id=eid,
                source_snapshot_id=sid,
                notes=["Title symbol remains unresolved."],
            ))
            continue
        node=f"title:{_slug(sid)}:{value}"
        entities[node]=Entity(
            node,"TITLE",symbol,
            metadata={
                "symbol":symbol,
                "title_id":value,
                "definition_path":title_path.as_posix(),
                "source_snapshot_id":sid,
            },
        )
        eid=_evidence_id(sid,rel,line,"title",f"{symbol}={value}")
        evidence[eid]=Evidence(
            eid,"SERVER",rel,f"{rel}:{line}",sid,
            f"Resolved xi.title.{symbol} to title id {value} from {title_path}.",
        )
        edges.append(DependencyEdge(
            edge_id=f"lua-title:{_slug(sid + rel + str(line) + symbol + str(value))}",
            source_node=source_artifact_id,
            target_node=node,
            relationship="REQUIRES",
            evidence_id=eid,
            confidence="VERIFIED",
            status="DISCOVERED",
            discovered_by="lua_dependency_discovery",
            source_location=f"{rel}:{line}",
            notes="TITLE_REFERENCE",
            source_snapshot_id=sid,
        ))

    zone_data = load_zone_entities(mobs_yaml) if mobs_yaml and Path(mobs_yaml).is_file() else None
    symbols: dict[str, int] = {}
    symbol_unresolved: list[dict[str, Any]] = []
    if zone_data is not None and ids_lua and Path(ids_lua).is_file():
        symbols, symbol_unresolved = parse_first_id_symbols(Path(ids_lua), zone_data)

    for item in symbol_unresolved:
        eid = _evidence_id(sid, rel, item["line"], "first-id-unresolved", item["symbol"])
        evidence[eid] = Evidence(
            eid, "SERVER", str(ids_lua), f"{ids_lua}:{item['line']}", sid,
            item["reason"],
        )
        findings.append(Finding(
            finding_id=f"finding:lua-id:{_slug(eid)}",
            analysis_id="lua-dependency-discovery",
            subject_id=source_artifact_id,
            field=f"ID.mob.{item['symbol']}",
            value={"template": item["template"]},
            status="UNKNOWN",
            confidence="UNKNOWN",
            evidence_id=eid,
            source_snapshot_id=sid,
            notes=[item["reason"]],
        ))

    # Collect all explicit offsets plus inclusive offsets implied by numeric for-ranges.
    refs: dict[tuple[str, int], dict[str, Any]] = {}
    for match in MOB_OFFSET_RE.finditer(text):
        key = (match.group("symbol"), int(match.group("offset")))
        refs.setdefault(key, {"line": _line(text, match.start()), "basis": "ID_MOB_OFFSET"})
    for match in MOB_RANGE_RE.finditer(text):
        start, end = int(match.group("start")), int(match.group("end"))
        if end < start:
            continue
        for offset in range(start, end + 1):
            key = (match.group("symbol"), offset)
            refs.setdefault(key, {"line": _line(text, match.start()), "basis": "ID_MOB_RANGE"})

    zone_entities = (zone_data or {}).get("entities") or {}

    # Bind a zone mob script to its owning concrete entity only when the script stem maps to
    # exactly one entity/template in the supplied zone data. Generic scripts shared by multiple
    # entities intentionally remain unresolved.
    if zone_data is not None:
        script_stem=script.stem
        owning=[
            (entity_id,row)
            for entity_id,row in zone_entities.items()
            if str(row.get("template") or "")==script_stem
            or str(row.get("script") or "")==script_stem
        ]
        unique_owners={entity_id:row for entity_id,row in owning}
        if len(unique_owners)==1:
            entity_id,row=next(iter(unique_owners.items()))
            target_node=_entity_node_id(sid,zone_id,entity_id)
            entities[target_node]=Entity(
                target_node,
                "SERVER_ENTITY",
                str(row.get("template") or entity_id),
                metadata={
                    **dict(row),
                    "zone_id":zone_id,
                    "numeric_id":entity_id,
                    "source_snapshot_id":sid,
                },
            )
            eid=_evidence_id(sid,rel,1,"script-entity",str(entity_id))
            evidence[eid]=Evidence(
                eid,"SERVER",rel,rel,sid,
                f"Zone mob script {rel} uniquely maps to entity {entity_id} via template/script name {script_stem}.",
            )
            edges.append(DependencyEdge(
                edge_id=f"lua-script-entity:{_slug(sid + rel + str(entity_id))}",
                source_node=source_artifact_id,
                target_node=target_node,
                relationship="REFERENCES",
                evidence_id=eid,
                confidence="VERIFIED",
                status="DISCOVERED",
                discovered_by="lua_dependency_discovery",
                source_location=rel,
                notes="UNIQUE_ZONE_SCRIPT_ENTITY_BINDING",
                source_snapshot_id=sid,
            ))
        elif len(unique_owners)>1:
            eid=_evidence_id(sid,rel,1,"script-entity-ambiguous",script_stem)
            evidence[eid]=Evidence(
                eid,"SERVER",rel,rel,sid,
                f"Zone mob script {rel} matches multiple concrete entities; no owning entity was selected.",
            )
            findings.append(Finding(
                finding_id=f"finding:lua-script-entity:{_slug(eid)}",
                analysis_id="lua-dependency-discovery",
                subject_id=source_artifact_id,
                field="script_entity_binding",
                value={"script_stem":script_stem,"candidate_entity_ids":sorted(unique_owners)},
                status="UNKNOWN",
                confidence="UNKNOWN",
                evidence_id=eid,
                source_snapshot_id=sid,
                notes=["Multiple zone entities share this script/template name; binding remains unresolved."],
            ))

    for (symbol, offset), ref in sorted(refs.items()):
        line = int(ref["line"])
        base = symbols.get(symbol)
        if base is None:
            target = f"ID.mob.{symbol}+{offset}"
            eid = _evidence_id(sid, rel, line, "entity-unresolved", target)
            evidence[eid] = Evidence(
                eid, "SERVER", rel, f"{rel}:{line}", sid,
                f"Could not resolve {target}; missing/ambiguous GetFirstID zone identity evidence.",
            )
            findings.append(Finding(
                finding_id=f"finding:lua-entity:{_slug(eid)}",
                analysis_id="lua-dependency-discovery",
                subject_id=source_artifact_id,
                field=target,
                value=None,
                status="UNKNOWN",
                confidence="UNKNOWN",
                evidence_id=eid,
                source_snapshot_id=sid,
                notes=["Entity arithmetic reference was preserved as unresolved."],
            ))
            continue

        entity_id = base + offset
        row = zone_entities.get(entity_id)
        target_node = _entity_node_id(sid, zone_id, entity_id)
        if row is None:
            eid = _evidence_id(sid, rel, line, "entity-missing", str(entity_id))
            evidence[eid] = Evidence(
                eid, "SERVER", rel, f"{rel}:{line}", sid,
                f"Resolved {symbol}+{offset} to {entity_id}, but the entity is absent from zone mobs.yaml.",
            )
            findings.append(Finding(
                finding_id=f"finding:lua-entity:{_slug(eid)}",
                analysis_id="lua-dependency-discovery",
                subject_id=source_artifact_id,
                field=f"ID.mob.{symbol}+{offset}",
                value={"entity_id": entity_id},
                status="UNKNOWN",
                confidence="UNKNOWN",
                evidence_id=eid,
                source_snapshot_id=sid,
                notes=["Resolved numeric entity ID is missing from the supplied zone entity source."],
            ))
            continue

        entities[target_node] = Entity(
            target_node,
            "SERVER_ENTITY",
            str(row.get("template") or entity_id),
            metadata={
                **dict(row),
                "zone_id": zone_id,
                "numeric_id": entity_id,
                "source_snapshot_id": sid,
            },
        )
        target_expr = f"ID.mob.{symbol}+{offset}={entity_id}"
        eid = _evidence_id(sid, rel, line, "entity", target_expr)
        evidence[eid] = Evidence(
            eid, "SERVER", rel, f"{rel}:{line}", sid,
            f"Resolved {target_expr} using IDs.lua GetFirstID and zone mobs.yaml entity ordering.",
        )
        edges.append(DependencyEdge(
            edge_id=f"lua-entity:{_slug(sid + rel + str(line) + target_expr)}",
            source_node=source_artifact_id,
            target_node=target_node,
            relationship="REQUIRES",
            evidence_id=eid,
            confidence="VERIFIED",
            status="DISCOVERED",
            discovered_by="lua_dependency_discovery",
            source_location=f"{rel}:{line}",
            notes=ref["basis"],
            source_snapshot_id=sid,
        ))

    return {
        "schema": 1,
        "analysis": {
            "analysis_id": "lua-dependency-discovery",
            "analysis_type": "LUA_STATIC_DEPENDENCY_DISCOVERY",
            "source": rel,
            "target": None,
            "feature_id": None,
            "status": "ANALYZED",
            "created_at": None,
            "tool_version": "1",
            "findings": [],
            "source_snapshot_id": sid,
            "notes": [
                "Only literal require() paths, resolved ID.text/title symbols, and statically resolved ID.mob arithmetic are emitted as VERIFIED.",
                "Unknown or missing identity evidence is emitted as an explicit UNKNOWN finding.",
            ],
        },
        "artifacts": [_record(x) for x in artifacts.values()],
        "entities": [_record(x) for x in entities.values()],
        "evidence": [_record(x) for x in evidence.values()],
        "findings": [_record(x) for x in findings],
        "edges": [_record(x) for x in edges],
        "summary": {
            "require_dependencies": sum(1 for edge in edges if edge.edge_id.startswith("lua-require:")),
            "script_entity_bindings": sum(1 for edge in edges if edge.edge_id.startswith("lua-script-entity:")),
            "entity_dependencies": sum(1 for edge in edges if edge.edge_id.startswith("lua-entity:")),
            "zone_text_dependencies": sum(1 for edge in edges if edge.edge_id.startswith("lua-zone-text:")),
            "title_dependencies": sum(1 for edge in edges if edge.edge_id.startswith("lua-title:")),
            "unresolved_findings": len(findings),
        },
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("script",type=Path)
    ap.add_argument("--zone-id",type=int)
    ap.add_argument("--ids-lua",type=Path)
    ap.add_argument("--mobs-yaml",type=Path)
    ap.add_argument("--titles-lua",type=Path)
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    payload=analyze_script(
        args.root,args.script,zone_id=args.zone_id,ids_lua=args.ids_lua,mobs_yaml=args.mobs_yaml,
        titles_lua=args.titles_lua
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
