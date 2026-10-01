"""Generic recursive prerequisite closure over canonical graph relationships.

The service deliberately knows nothing about a particular game, zone, mission, or
entity type. A producer imports directed requirement relationships into the
canonical graph and may annotate them with ``requirement_group`` metadata.
"""
from __future__ import annotations

from collections import defaultdict, deque
import hashlib
import json
import sqlite3
from typing import Any, Iterable

SCHEMA_VERSION="obtainability-closure/v1"


def resolve_obtainability_root(con: sqlite3.Connection, selection: str) -> str:
    value = selection.strip()
    if not value:
        raise ValueError("A canonical root or unique display label is required.")
    exact = con.execute("SELECT entity_id FROM entities WHERE entity_id=?", (value,)).fetchall()
    if exact:
        return exact[0][0]
    rows = con.execute(
        "SELECT entity_id FROM entities WHERE LOWER(display_name)=LOWER(?) "
        "UNION SELECT entity_id FROM entity_identifiers WHERE LOWER(identifier_value)=LOWER(?) "
        "ORDER BY entity_id",
        (value, value),
    ).fetchall()
    ids = [row[0] for row in rows]
    if len(ids) == 1:
        return ids[0]
    marks = ",".join("?" for _ in ids)
    connected = [
        row[0]
        for row in con.execute(
            f"SELECT source_node FROM entity_relationships WHERE source_node IN ({marks}) "
            "GROUP BY source_node HAVING COUNT(*) > 0 ORDER BY source_node",
            tuple(ids),
        ).fetchall()
    ] if ids else []
    if len(connected) == 1:
        return connected[0]
    if not ids:
        raise ValueError(f"No canonical graph node matches {selection!r}.")
    raise ValueError(f"Selection {selection!r} is ambiguous; use a canonical node ID.")


def _metadata(raw: str | None) -> dict[str, Any]:
    try:
        value=json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"raw_metadata":raw}
    return value if isinstance(value,dict) else {"raw_metadata":value}


def _gate_id(owner: str, group: str) -> str:
    digest=hashlib.sha256(f"{owner}\0{group}".encode("utf-8")).hexdigest()[:16]
    return f"closure-gate:{digest}"


def _node_rows(con: sqlite3.Connection, node_ids: Iterable[str]) -> dict[str,dict[str,Any]]:
    ids=sorted(set(node_ids))
    if not ids:
        return {}
    marks=",".join("?" for _ in ids)
    rows=con.execute(
        f"SELECT entity_id,entity_type,display_name,metadata_json FROM entities WHERE entity_id IN ({marks})",
        tuple(ids),
    ).fetchall()
    return {
        row[0]:{"node_id":row[0],"node_type":row[1],"label":row[2] or row[0],"metadata":_metadata(row[3])}
        for row in rows
    }


def build_obtainability_closure(
    con: sqlite3.Connection,
    root: str,
    *,
    relationships: Iterable[str] | None = None,
    max_edges: int = 1000,
) -> dict[str,Any]:
    if not root:
        raise ValueError("root is required")
    if max_edges <= 0:
        raise ValueError("max_edges must be positive")
    allowed=set(relationships or ())
    queue=deque([(root,(root,))])
    seen_nodes={root}
    seen_edges=set()
    edges=[]
    cycles=[]
    unresolved=[]
    truncated=False

    while queue:
        node,path=queue.popleft()
        sql=("SELECT relationship_id,source_node,target_node,relationship,evidence_id,confidence,"
             "status,metadata_json,source_snapshot_id FROM entity_relationships WHERE source_node=?")
        rows=con.execute(sql,(node,)).fetchall()
        selected=[row for row in rows if not allowed or row[3] in allowed]
        if not selected:
            unresolved.append({"node_id":node,"reason":"NO_PREREQUISITE_EDGE"})
            continue
        for row in sorted(selected,key=lambda item:item[0]):
            if row[0] in seen_edges:
                continue
            if len(edges)>=max_edges:
                truncated=True
                queue.clear()
                break
            seen_edges.add(row[0])
            metadata=_metadata(row[7])
            group=metadata.get("requirement_group") or {}
            if not isinstance(group,dict):
                group={"id":str(group)}
            group_id=str(group.get("id") or row[0])
            operator=str(group.get("operator") or "AND").upper()
            if operator not in {"AND","OR"}:
                operator="AND"
            edges.append({
                "edge_id":row[0],"source_node":row[1],"target_node":row[2],
                "relationship":row[3],"evidence_id":row[4],"confidence":row[5],
                "status":row[6],"metadata":metadata,"source_snapshot_id":row[8],
                "requirement_group":{"id":group_id,"operator":operator},
            })
            target=row[2]
            if target in path:
                cycles.append({"edge_id":row[0],"path":[*path,target]})
                continue
            if target not in seen_nodes:
                seen_nodes.add(target)
                queue.append((target,(*path,target)))

    node_map=_node_rows(con,seen_nodes)
    nodes=[]
    for node in sorted(seen_nodes):
        record=node_map.get(node,{"node_id":node,"node_type":"UNRESOLVED","label":node,"metadata":{}})
        terminal=bool(record["metadata"].get("obtainability_terminal") or record["metadata"].get("terminal"))
        record["terminal"]=terminal
        nodes.append(record)
    terminal_ids={node["node_id"] for node in nodes if node["terminal"]}
    unresolved=[entry for entry in unresolved if entry["node_id"] not in terminal_ids]

    groups=defaultdict(lambda:{"edge_ids":[],"owner":None,"operator":"AND"})
    for edge in edges:
        group=edge["requirement_group"]
        key=(edge["source_node"],group["id"])
        groups[key]["owner"]=edge["source_node"]
        groups[key]["operator"]=group["operator"]
        groups[key]["edge_ids"].append(edge["edge_id"])
    group_rows=[
        {"gate_id":_gate_id(owner,group),"group_id":group,"owner":data["owner"],
         "operator":data["operator"],"edge_ids":sorted(data["edge_ids"])}
        for (owner,group),data in sorted(groups.items())
    ]
    evidence_ids=sorted({edge["evidence_id"] for edge in edges if edge["evidence_id"]})
    evidence=[]
    if evidence_ids:
        marks=",".join("?" for _ in evidence_ids)
        evidence=[
            {"evidence_id":row[0],"evidence_type":row[1],"source":row[2],"location":row[3],"snapshot":row[4],"notes":row[5]}
            for row in con.execute(f"SELECT evidence_id,evidence_type,source,location,snapshot,notes FROM evidence WHERE evidence_id IN ({marks}) ORDER BY evidence_id",tuple(evidence_ids)).fetchall()
        ]
    return {
        "schema_version":SCHEMA_VERSION,"root":root,"relationships":sorted(allowed),
        "nodes":nodes,"edges":edges,"gates":group_rows,"cycles":cycles,
        "unresolved":sorted(unresolved,key=lambda entry:(entry["node_id"],entry["reason"])),
        "evidence":evidence,"truncated":truncated,
    }


def closure_projection(closure: dict[str,Any]) -> dict[str,Any]:
    nodes=list(closure["nodes"])
    edges=[]
    gates={(gate["owner"],gate["group_id"]):gate for gate in closure["gates"]}
    for gate in closure["gates"]:
        nodes.append({"node_id":gate["gate_id"],"node_type":"REQUIREMENT_GATE",
                      "label":gate["operator"],"metadata":{"operator":gate["operator"],"group_id":gate["group_id"]}})
        edges.append({"source_node":gate["owner"],"target_node":gate["gate_id"],"relationship":"REQUIRES_GATE"})
    for edge in closure["edges"]:
        gate=gates[(edge["source_node"],edge["requirement_group"]["id"])]
        edges.append({"source_node":gate["gate_id"],"target_node":edge["target_node"],
                      "relationship":edge["relationship"],"edge_id":edge["edge_id"],
                      "metadata":edge["metadata"],"evidence_id":edge["evidence_id"],
                      "confidence":edge["confidence"],"status":edge["status"]})
    return {"schema_version":SCHEMA_VERSION,"root":closure["root"],"nodes":nodes,"edges":edges,
            "cycles":closure["cycles"],"unresolved":closure["unresolved"],"evidence":closure["evidence"]}
