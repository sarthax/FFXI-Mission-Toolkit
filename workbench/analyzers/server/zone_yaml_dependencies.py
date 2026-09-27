#!/usr/bin/env python3
"""Modern LSB zone-YAML dependency closure.

Bridges concrete zone entities into template/species/skill/spell dependencies using:
- data/zones/<zone>/mobs.yaml
- normalized mob_skill_lists / mob_skills
- normalized mob_spell_lists / spells

The analyzer emits generic Entity/Artifact/DependencyEdge records and preserves unresolved
membership/script gaps as Findings rather than silently omitting them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from workbench.adapters.servers import LSBAdapter
from workbench.adapters.servers.sql_extract import extract_logical_records
from workbench.analyzers.server.lua_dependencies import (
    _artifact_id,
    _entity_node_id,
    load_zone_entities,
)
from workbench.core.provenance import snapshot_id
from workbench.core.schema import Artifact, DependencyEdge, Entity, Evidence, Finding, record_dict


def _slug(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _node(prefix: str, sid: str, key: str | int, zone_id: int | None = None) -> str:
    zone = "" if zone_id is None else f":{zone_id}"
    return f"{prefix}:{_slug(sid)}{zone}:{key}"


def _evidence_id(sid: str, source: str, subject: str, kind: str) -> str:
    return f"evidence:zone-yaml:{_slug(sid)}:{_slug(source)}:{kind}:{_slug(subject)}"


def _record(value):
    return record_dict(value)


def _edge(
    edges: list[DependencyEdge],
    *,
    sid: str,
    source: str,
    target: str,
    evidence_id: str,
    role: str,
) -> None:
    edges.append(DependencyEdge(
        edge_id=f"zone-dep:{_slug(sid + source + target + role)}",
        source_node=source,
        target_node=target,
        relationship="REQUIRES",
        evidence_id=evidence_id,
        confidence="VERIFIED",
        status="DISCOVERED",
        discovered_by="zone_yaml_dependency_closure",
        notes=role,
        source_snapshot_id=sid,
    ))


def analyze_zone(
    root: Path,
    mobs_yaml: Path,
    *,
    zone_id: int,
    source_snapshot_id: str | None = None,
    root_entity_ids: Iterable[int] | None = None,
) -> dict[str, Any]:
    root=Path(root)
    mobs_yaml=Path(mobs_yaml)
    sid=source_snapshot_id or snapshot_id(root)
    zone_data=load_zone_entities(mobs_yaml)
    all_entities=zone_data["entities"]
    templates=zone_data["templates"]

    selected=sorted({int(x) for x in root_entity_ids}) if root_entity_ids else sorted(all_entities)

    adapter=LSBAdapter(root)
    skill_members=extract_logical_records(adapter,"mob_skill_lists")
    skills=extract_logical_records(adapter,"mob_skills")
    spell_members=extract_logical_records(adapter,"mob_spell_lists")
    spells=extract_logical_records(adapter,"spells")

    skills_by_id={int(r.fields["mob_skill_id"]):r for r in skills if r.fields.get("mob_skill_id") is not None}
    skill_members_by_list: dict[int,list[Any]]={}
    for record in skill_members:
        lid=record.fields.get("skill_list_id")
        if lid is not None:
            skill_members_by_list.setdefault(int(lid),[]).append(record)

    spells_by_id={int(r.fields["spell_id"]):r for r in spells if r.fields.get("spell_id") is not None}
    spell_members_by_list: dict[int,list[Any]]={}
    for record in spell_members:
        lid=record.fields.get("spell_list_id")
        if lid is not None:
            spell_members_by_list.setdefault(int(lid),[]).append(record)

    entities: dict[str,Entity]={}
    artifacts: dict[str,Artifact]={}
    evidence: dict[str,Evidence]={}
    edges: list[DependencyEdge]=[]
    findings: list[Finding]=[]

    yaml_rel=mobs_yaml.relative_to(root).as_posix() if mobs_yaml.is_relative_to(root) else mobs_yaml.as_posix()

    def add_evidence(subject: str,kind: str,note: str,source: str=yaml_rel) -> str:
        eid=_evidence_id(sid,source,subject,kind)
        evidence[eid]=Evidence(eid,"SERVER",source,source,sid,note)
        return eid

    def add_finding(subject: str,field: str,value: Any,note: str,eid: str) -> None:
        findings.append(Finding(
            finding_id=f"finding:zone-yaml:{_slug(subject + field + eid)}",
            analysis_id="zone-yaml-dependency-closure",
            subject_id=subject,
            field=field,
            value=value,
            status="UNKNOWN",
            confidence="UNKNOWN",
            evidence_id=eid,
            source_snapshot_id=sid,
            notes=[note],
        ))

    for entity_id in selected:
        row=all_entities.get(entity_id)
        if row is None:
            missing_node=_entity_node_id(sid,zone_id,entity_id)
            eid=add_evidence(str(entity_id),"missing-entity",f"Requested entity {entity_id} is absent from {yaml_rel}.")
            add_finding(missing_node,"entity_id",entity_id,"Root entity is missing from zone YAML.",eid)
            continue

        entity_node=_entity_node_id(sid,zone_id,entity_id)
        entities[entity_node]=Entity(
            entity_node,
            "SERVER_ENTITY",
            str(row.get("template") or entity_id),
            metadata={**dict(row),"zone_id":zone_id,"numeric_id":entity_id,"source_snapshot_id":sid},
        )
        template_name=row.get("template")
        if not template_name:
            eid=add_evidence(str(entity_id),"missing-template",f"Entity {entity_id} has no template reference.")
            add_finding(entity_node,"template",None,"Entity has no template reference.",eid)
            continue

        template_row=templates.get(template_name)
        template_node=_node("mob-template",sid,str(template_name),zone_id)
        entities[template_node]=Entity(
            template_node,
            "MOB_TEMPLATE",
            str(template_name),
            metadata={
                "template_name":template_name,
                "zone_id":zone_id,
                "source_snapshot_id":sid,
                **(dict(template_row) if isinstance(template_row,dict) else {}),
            },
        )
        eid=add_evidence(f"{entity_id}:{template_name}","entity-template",f"Entity {entity_id} uses template {template_name}.")
        _edge(edges,sid=sid,source=entity_node,target=template_node,evidence_id=eid,role="ENTITY_USES_TEMPLATE")

        if not isinstance(template_row,dict):
            add_finding(template_node,"template",template_name,"Referenced template is absent from zone YAML.",eid)
            continue

        species=template_row.get("species")
        if species:
            species_node=_node("species",sid,str(species))
            entities[species_node]=Entity(
                species_node,"SPECIES",str(species),
                metadata={"species":species,"source_snapshot_id":sid},
            )
            seid=add_evidence(f"{template_name}:{species}","template-species",f"Template {template_name} declares species {species}.")
            _edge(edges,sid=sid,source=template_node,target=species_node,evidence_id=seid,role="TEMPLATE_REQUIRES_SPECIES")

        skill_list_id=template_row.get("skill_list_id")
        if skill_list_id is not None:
            skill_list_id=int(skill_list_id)
            list_node=_node("mob-skill-list",sid,skill_list_id)
            entities[list_node]=Entity(
                list_node,"MOB_SKILL_LIST",f"Mob skill list {skill_list_id}",
                metadata={"skill_list_id":skill_list_id,"source_snapshot_id":sid},
            )
            leid=add_evidence(f"{template_name}:skill:{skill_list_id}","template-skill-list",f"Template {template_name} uses mob skill list {skill_list_id}.")
            _edge(edges,sid=sid,source=template_node,target=list_node,evidence_id=leid,role="TEMPLATE_REQUIRES_SKILL_LIST")

            members=skill_members_by_list.get(skill_list_id,[])
            if not members:
                add_finding(list_node,"members",[],f"No mob_skill_lists members were extracted for list {skill_list_id}.",leid)
            for member in members:
                skill_id=int(member.fields["mob_skill_id"])
                skill=skills_by_id.get(skill_id)
                skill_name=(skill.fields.get("name") if skill else None) or f"mob_skill_{skill_id}"
                skill_node=_node("mob-skill",sid,skill_id)
                entities[skill_node]=Entity(
                    skill_node,"MOB_SKILL",str(skill_name),
                    metadata={
                        "mob_skill_id":skill_id,
                        "source_snapshot_id":sid,
                        **(dict(skill.fields) if skill else {}),
                    },
                )
                meid=add_evidence(f"{skill_list_id}:{skill_id}","skill-list-member",f"Mob skill list {skill_list_id} contains skill {skill_id}.","sql/mob_skill_lists.sql")
                _edge(edges,sid=sid,source=list_node,target=skill_node,evidence_id=meid,role="SKILL_LIST_REQUIRES_SKILL")

                if skill is None:
                    add_finding(skill_node,"definition",skill_id,f"Mob skill {skill_id} has no normalized mob_skills definition.",meid)
                    continue

                script_rel=f"scripts/actions/mobskills/{skill_name}.lua"
                script_path=root/script_rel
                if script_path.is_file():
                    artifact_id=_artifact_id(sid,script_rel)
                    artifacts[artifact_id]=Artifact(
                        artifact_id,"LUA",script_rel,sid,
                        metadata={"analysis_role":"MOB_SKILL_IMPLEMENTATION","mob_skill_id":skill_id},
                    )
                    seid2=add_evidence(f"{skill_id}:{script_rel}","mob-skill-script",f"Mob skill {skill_id} resolves to conventional implementation {script_rel}.","sql/mob_skills.sql")
                    _edge(edges,sid=sid,source=skill_node,target=artifact_id,evidence_id=seid2,role="MOB_SKILL_REQUIRES_LUA_IMPLEMENTATION")
                else:
                    meid2=add_evidence(f"{skill_id}:{script_rel}","missing-mob-skill-script",f"No conventional mob-skill Lua file exists at {script_rel}.","sql/mob_skills.sql")
                    add_finding(skill_node,"lua_implementation",script_rel,"Mob skill definition has no conventional Lua implementation path.",meid2)

        spell_list_id=template_row.get("spell_list_id")
        if spell_list_id is not None:
            spell_list_id=int(spell_list_id)
            list_node=_node("mob-spell-list",sid,spell_list_id)
            entities[list_node]=Entity(
                list_node,"MOB_SPELL_LIST",f"Mob spell list {spell_list_id}",
                metadata={"spell_list_id":spell_list_id,"source_snapshot_id":sid},
            )
            leid=add_evidence(f"{template_name}:spell:{spell_list_id}","template-spell-list",f"Template {template_name} uses mob spell list {spell_list_id}.")
            _edge(edges,sid=sid,source=template_node,target=list_node,evidence_id=leid,role="TEMPLATE_REQUIRES_SPELL_LIST")

            members=spell_members_by_list.get(spell_list_id,[])
            if not members:
                add_finding(list_node,"members",[],f"No mob_spell_lists members were extracted for list {spell_list_id}.",leid)
            for member in members:
                spell_id=int(member.fields["spell_id"])
                spell=spells_by_id.get(spell_id)
                spell_name=(spell.fields.get("name") if spell else None) or f"spell_{spell_id}"
                spell_node=_node("spell",sid,spell_id)
                entities[spell_node]=Entity(
                    spell_node,"SPELL",str(spell_name),
                    metadata={
                        "spell_id":spell_id,
                        "min_level":member.fields.get("min_level"),
                        "max_level":member.fields.get("max_level"),
                        "source_snapshot_id":sid,
                        **(dict(spell.fields) if spell else {}),
                    },
                )
                meid=add_evidence(f"{spell_list_id}:{spell_id}","spell-list-member",f"Mob spell list {spell_list_id} contains spell {spell_id}.","sql/mob_spell_lists.sql")
                _edge(edges,sid=sid,source=list_node,target=spell_node,evidence_id=meid,role="SPELL_LIST_REQUIRES_SPELL")
                if spell is None:
                    add_finding(spell_node,"definition",spell_id,f"Spell {spell_id} has no normalized spell_list definition.",meid)

    return {
        "schema":1,
        "analysis":{
            "analysis_id":"zone-yaml-dependency-closure",
            "analysis_type":"LSB_ZONE_YAML_DEPENDENCY_CLOSURE",
            "source":yaml_rel,
            "target":None,
            "feature_id":None,
            "status":"ANALYZED",
            "created_at":None,
            "tool_version":"1",
            "findings":[],
            "notes":[
                "Zone entity/template dependencies come from mobs.yaml.",
                "Skill/spell membership and definitions reuse profile-backed normalized SQL extraction.",
                "Missing members/definitions/scripts remain explicit UNKNOWN findings.",
            ],
            "source_snapshot_id":sid,
        },
        "entities":[_record(x) for x in entities.values()],
        "artifacts":[_record(x) for x in artifacts.values()],
        "evidence":[_record(x) for x in evidence.values()],
        "findings":[_record(x) for x in findings],
        "edges":[_record(x) for x in edges],
        "summary":{
            "root_entities":len(selected),
            "entity_nodes":len(entities),
            "artifacts":len(artifacts),
            "edges":len(edges),
            "unresolved_findings":len(findings),
        },
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("root",type=Path)
    ap.add_argument("mobs_yaml",type=Path)
    ap.add_argument("--zone-id",type=int,required=True)
    ap.add_argument("--entity-id",type=int,action="append",dest="entity_ids")
    ap.add_argument("--json",type=Path)
    args=ap.parse_args()
    payload=analyze_zone(
        args.root,args.mobs_yaml,zone_id=args.zone_id,root_entity_ids=args.entity_ids
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
