"""Catalog and presentation adapters for Feature Trace.

Catalog rows describe indexed knowledge; they never manufacture graph relationships.
The adapters intentionally inspect the available Workbench schema so independently built
server/client/capture indexes can participate without requiring identical tables.
"""
from __future__ import annotations

import json
import sqlite3
from urllib.parse import quote, unquote

from workbench.adapters.servers.catalog_links import server_source_links
from workbench.core.services.feature_trace_providers import PROVIDER_LINKS, provider_tables


CANONICAL_TABLES = (
    ("entities", "entity_id", "entity_type", "display_name", "metadata_json"),
    ("features", "feature_id", "feature_type", "name", "metadata_json"),
    ("capabilities", "capability_id", "capability_type", "name", "notes_json"),
    ("functions", "function_id", "kind", "qualified_name", "notes_json"),
    ("bindings", "binding_id", "binding_system", "lua_name", "notes_json"),
    ("build_targets", "target_id", "build_system", "name", "notes_json"),
    ("artifacts", "artifact_id", "artifact_type", "path", "metadata_json"),
    ("enum_definitions", "enum_id", "format", "symbol", "notes_json"),
)
ID_COLUMNS = ("itemid", "npcid", "mobid", "entity_id", "mission_id", "quest_id", "zoneid", "id", "spellid", "abilityid", "weaponskillid", "traitid", "poolid", "groupid")
NAME_COLUMNS = ("name", "display_name", "mobname", "item_name", "instance_name", "qualified_name", "symbol", "tag", "filename")


def _tables(con):
    return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]


def _columns(con, table):
    return {r[1].lower(): r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def _json(value):
    try:
        return json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}


def _identity_columns(cols, key, spec):
    if spec is None:
        return (key,)
    return tuple(cols[column.lower()] for column in spec.identity_columns())


def _catalog_id(table, values, identity_columns=None):
    columns=tuple(identity_columns or ())
    if len(columns)<=1:
        value=values[0] if isinstance(values,(tuple,list)) else values
        return f"catalog:{table}:{value}"
    vals=tuple(values)
    return "catalog:"+table+":"+"&".join(
        f"{column}={quote(str(value),safe='')}" for column,value in zip(columns,vals)
    )


def _resolve_identity_values(con, table, raw, identity_columns, primary_key):
    if len(identity_columns)==1:
        value=unquote(raw)
        rows=con.execute(
            f"SELECT {identity_columns[0]} FROM {table} WHERE CAST({identity_columns[0]} AS TEXT)=? LIMIT 2",
            (value,),
        ).fetchall()
        return tuple(rows[0]) if len(rows)==1 else None
    if "=" in raw:
        parsed={}
        for part in raw.split("&"):
            if "=" not in part:
                continue
            name,value=part.split("=",1)
            parsed[name.casefold()]=unquote(value)
        if all(column.casefold() in parsed for column in identity_columns):
            return tuple(parsed[column.casefold()] for column in identity_columns)
        return None
    # Legacy single-key catalog IDs are accepted only when the old key is unique.
    rows=con.execute(
        f"SELECT {','.join(identity_columns)} FROM {table} WHERE CAST({primary_key} AS TEXT)=? LIMIT 2",
        (unquote(raw),),
    ).fetchall()
    return tuple(rows[0]) if len(rows)==1 else None


def _identity_where(identity_columns):
    return " AND ".join(f"CAST({column} AS TEXT)=?" for column in identity_columns)


def _indexed_specs(con):
    """Yield explicit provider tables first, then compatibility-discovered tables."""
    available=set(_tables(con))
    claimed=set()
    for table,(provider,spec) in provider_tables().items():
        if table not in available:
            continue
        # A known provider table is reserved even when its current schema is incomplete.
        # Do not reinterpret a schema mismatch through the heuristic fallback.
        claimed.add(table)
        cols=_columns(con,table)
        required={spec.id_column.lower(),*(col.lower() for col in spec.identity_columns())}
        if spec.name_column:
            required.add(spec.name_column.lower())
        if required.issubset(cols):
            name_col=cols[spec.name_column.lower()] if spec.name_column else None
            yield table,cols[spec.id_column.lower()],name_col,provider.provider_id,provider.domain,spec.object_type,spec
    for table in sorted(available-claimed):
        if table in {x[0] for x in CANONICAL_TABLES} or table=="entity_relationships":
            continue
        cols=_columns(con,table)
        key=next((cols[x] for x in ID_COLUMNS if x in cols),None)
        name=next((cols[x] for x in NAME_COLUMNS if x in cols),None)
        if key and name:
            yield table,key,name,"schema-fallback",table.split("_",1)[0],table.removeprefix("sql_").removeprefix("lsb_").removeprefix("dsp_").removeprefix("topaz_").upper(),None


def _provider_display(spec, identity: dict, name_value):
    if name_value not in (None,""):
        return name_value
    if spec is not None and spec.display_template:
        try:
            return spec.display_template.format(**identity)
        except (KeyError,ValueError):
            pass
    return " / ".join(f"{key}={value}" for key,value in identity.items())


def search_catalog(con: sqlite3.Connection, term: str, limit: int = 200):
    pattern=f"%{term.casefold()}%"
    rows=[]
    available=set(_tables(con))
    for table,key,kind,name,meta in CANONICAL_TABLES:
        if table not in available:
            continue
        columns=_columns(con,table)
        if not {key.lower(),kind.lower(),name.lower()}.issubset(columns):
            continue
        for row in con.execute(
            f"SELECT {key},{kind},{name} FROM {table} WHERE lower(CAST({key} AS TEXT)) LIKE ? OR lower(COALESCE({name},'')) LIKE ? ORDER BY {key} LIMIT ?",
            (pattern,pattern,limit),
        ):
            matched=[]
            term_fold=term.casefold()
            if term_fold in str(row[0] or "").casefold():
                matched.append(key)
            if term_fold in str(row[2] or "").casefold():
                matched.append(name)
            rows.append({"node_id":row[0],"node_type":row[1],"display_name":row[2],"domain":"canonical","source":table,"table":table,"catalog_only":False,"matched_on":matched})
    for table,key,name,provider_id,domain,object_type,spec in _indexed_specs(con):
        cols=_columns(con,table)
        identity_columns=_identity_columns(cols,key,spec)
        alias_columns=[]
        if spec is not None:
            excluded=set(identity_columns)
            if name:
                excluded.add(name)
            alias_columns=[
                cols[column.lower()] for column in spec.search_columns
                if column.lower() in cols and cols[column.lower()] not in excluded
            ]
        detail_columns=[]
        if spec is not None:
            excluded=set(identity_columns)
            if name:
                excluded.add(name)
            excluded.update(alias_columns)
            detail_columns=[
                cols[column.lower()] for column in spec.detail_columns
                if column.lower() in cols and cols[column.lower()] not in excluded
            ]
        search_columns=[*identity_columns]
        if name:
            search_columns.append(name)
        search_columns.extend(alias_columns)
        select_columns=[*search_columns,*detail_columns]
        where=" OR ".join(f"lower(COALESCE(CAST({column} AS TEXT),'')) LIKE ?" for column in search_columns)
        params=[pattern]*len(search_columns)+[limit]
        for row in con.execute(
            f"SELECT {','.join(select_columns)} FROM {table} WHERE {where} ORDER BY {','.join(identity_columns)} LIMIT ?",
            params,
        ):
            identity_values=tuple(row[:len(identity_columns)])
            identity=dict(zip(identity_columns,identity_values))
            name_value=row[len(identity_columns)] if name else None
            display=_provider_display(spec,identity,name_value)
            node_id=_catalog_id(table,identity_values,identity_columns)
            matched=[
                column for column,value in zip(search_columns,row)
                if term.casefold() in str(value or "").casefold()
            ]
            alias_offset=len(identity_columns)+(1 if name else 0)
            aliases={
                column:row[alias_offset+index]
                for index,column in enumerate(alias_columns)
            }
            detail_offset=alias_offset+len(alias_columns)
            details={
                column:row[detail_offset+index]
                for index,column in enumerate(detail_columns)
            }
            inspect_href=None
            primary_value=identity.get(cols[spec.id_column.lower()]) if spec is not None else (identity_values[0] if identity_values else None)
            if spec is not None and spec.inspect_path:
                inspect_href=spec.inspect_path.replace("{id}",quote(str(primary_value),safe=""))
            sql_href=None
            if domain=="server" and primary_value is not None:
                sql_href=f"/sql?table={quote(table,safe='')}&q={quote(str(primary_value),safe='')}"
            item={"node_id":node_id,"node_type":object_type,"display_name":display,"domain":domain,"source":table,"table":table,"provider":provider_id,"catalog_only":True,
                  "identity":identity,"aliases":aliases,"details":details,"matched_on":matched,"inspect_href":inspect_href,"sql_href":sql_href}
            if len(identity_values)==1 and identity_columns[0].lower() in ID_COLUMNS:
                item["numeric_id"]=identity_values[0]
            rows.append(item)
    rows.sort(key=lambda r:(str(r.get("display_name") or "").casefold(),r["node_id"]))
    return rows[:limit]


def catalog_node(con: sqlite3.Connection, node_id: str):
    if not node_id.startswith("catalog:"):
        return None
    _,table,raw=node_id.split(":",2)
    if table not in _tables(con):
        return None
    for candidate,key,name,provider_id,domain,object_type,spec in _indexed_specs(con):
        if candidate!=table:
            continue
        cols=_columns(con,table)
        identity_columns=_identity_columns(cols,key,spec)
        identity_values=_resolve_identity_values(con,table,raw,identity_columns,key)
        if identity_values is None:
            return None
        detail_columns=[]
        if spec is not None:
            excluded=set(identity_columns)
            if name:
                excluded.add(name)
            detail_columns=[
                cols[col.lower()] for col in spec.detail_columns
                if col.lower() in cols and cols[col.lower()] not in excluded
            ]
        select_columns=[*identity_columns]
        if name:
            select_columns.append(name)
        select_columns.extend(detail_columns)
        row=con.execute(
            f"SELECT {','.join(select_columns)} FROM {table} WHERE {_identity_where(identity_columns)}",
            tuple(str(v) for v in identity_values),
        ).fetchone()
        if not row:
            return None
        identity_count=len(identity_columns)
        actual_identity=tuple(row[:identity_count])
        identity=dict(zip(identity_columns,actual_identity))
        name_offset=identity_count
        name_value=row[name_offset] if name else None
        detail_offset=identity_count+(1 if name else 0)
        display=_provider_display(spec,identity,name_value)
        details={column:row[detail_offset+index] for index,column in enumerate(detail_columns)}
        inspect_href=None
        if spec is not None and spec.inspect_path:
            primary_value=identity.get(cols[spec.id_column.lower()])
            inspect_href=spec.inspect_path.replace("{id}",quote(str(primary_value),safe=""))
        primary_value=identity.get(cols[spec.id_column.lower()]) if spec is not None else (actual_identity[0] if actual_identity else None)
        sql_href=f"/sql?table={quote(table,safe='')}&q={quote(str(primary_value),safe='')}" if domain=="server" and primary_value is not None else None
        metadata={"catalog_only":True,"source_table":table,"provider":provider_id,"domain":domain,"identity":identity,"details":details,"sql_href":sql_href}
        if len(actual_identity)==1:
            metadata["numeric_id"]=actual_identity[0]
        if inspect_href:
            metadata["inspect_href"]=inspect_href
        return {"node_id":node_id,"known":True,"representations":[{"table":table,"node_id":node_id,"node_type":object_type,"display_name":display,"metadata":metadata}]}
    return None


def _wiki_composite_relationships(
    con: sqlite3.Connection,
    node_id: str,
    table: str,
    identity_columns: tuple[str, ...] | list[str],
    identity_values: tuple,
) -> list[dict]:
    """Exact Wiki V2 links that require composite source/page identity."""
    identity=dict(zip(identity_columns,identity_values))
    links=[]
    specs={candidate:(key,name,provider_id,domain,object_type,spec)
           for candidate,key,name,provider_id,domain,object_type,spec in _indexed_specs(con)}

    def target_node(target_table: str, requested: dict, relationship: str):
        target_specs=specs.get(target_table)
        if target_specs is None:
            return
        target_key,_name,_provider,_domain,_type,target_spec=target_specs
        columns=_columns(con,target_table)
        target_identity_columns=_identity_columns(columns,target_key,target_spec)
        lowered={str(k).casefold():v for k,v in requested.items()}
        if not all(column.casefold() in lowered for column in target_identity_columns):
            return
        values=tuple(lowered[column.casefold()] for column in target_identity_columns)
        rows=con.execute(
            f"SELECT {','.join(target_identity_columns)} FROM {target_table} "
            f"WHERE {_identity_where(target_identity_columns)} LIMIT 2",
            tuple(str(v) for v in values),
        ).fetchall()
        if len(rows)!=1:
            return
        actual=tuple(rows[0])
        tid=_catalog_id(target_table,actual,target_identity_columns)
        target=catalog_node(con,tid)
        if target is None:
            return
        rep=(target.get("representations") or [{}])[0]
        candidate={
            "relationship":relationship,
            "source_node":node_id,
            "target_node":tid,
            "target_name":rep.get("display_name") or tid,
            "target_type":rep.get("node_type") or "UNKNOWN",
            "provider_native":True,
            "basis":"source_id+page_id",
            "adapter":"reference-wiki",
        }
        if not any(x.get("relationship")==relationship and x.get("target_node")==tid for x in links):
            links.append(candidate)

    if table in {"reference_wiki_claims","reference_wiki_blocks","reference_wiki_topic_pages"}:
        columns=_columns(con,table)
        if "source_id" in columns and "page_id" in columns:
            row=con.execute(
                f"SELECT {columns['source_id']},{columns['page_id']} FROM {table} "
                f"WHERE {_identity_where(identity_columns)}",
                tuple(str(v) for v in identity_values),
            ).fetchone()
            if row and row[0] is not None and row[1] is not None:
                rel={
                    "reference_wiki_claims":"FROM_REFERENCE_PAGE",
                    "reference_wiki_blocks":"IN_REFERENCE_PAGE",
                    "reference_wiki_topic_pages":"TOPIC_MEMBER_PAGE",
                }[table]
                target_node("reference_wiki_pages",{"source_id":row[0],"page_id":row[1]},rel)

    if table=="reference_wiki_pages":
        source_id=identity.get("source_id")
        page_id=identity.get("page_id")
        if source_id is not None and page_id is not None and "reference_wiki_topic_pages" in specs:
            rows=con.execute(
                """SELECT topic_id,source_id,page_id FROM reference_wiki_topic_pages
                   WHERE source_id=? AND page_id=? ORDER BY topic_id""",
                (str(source_id),str(page_id)),
            ).fetchall()
            for topic_id,src,pid in rows:
                target_node(
                    "reference_wiki_topic_pages",
                    {"topic_id":topic_id,"source_id":src,"page_id":pid},
                    "IN_REFERENCE_TOPIC",
                )
    return links


def provider_relationships(con: sqlite3.Connection, node_id: str) -> list[dict]:
    """Return exact source-native links for a catalog node without adding graph edges."""
    if not node_id.startswith("catalog:"):
        return []
    _,table,raw=node_id.split(":",2)
    specs={candidate:(key,name,provider_id,domain,object_type,spec)
           for candidate,key,name,provider_id,domain,object_type,spec in _indexed_specs(con)}
    source_specs=specs.get(table)
    if source_specs is None:
        return []
    key,_name,_provider_id,_domain,_object_type,spec=source_specs
    columns=_columns(con,table)
    identity_columns=_identity_columns(columns,key,spec)
    identity_values=_resolve_identity_values(con,table,raw,identity_columns,key)
    if identity_values is None:
        return []
    links=_wiki_composite_relationships(con,node_id,table,identity_columns,identity_values)
    for link in PROVIDER_LINKS:
        if link.source_table!=table or link.source_column.lower() not in columns:
            continue
        target_specs=specs.get(link.target_table)
        if target_specs is None:
            continue
        target_key,_target_name,_target_provider,_target_domain,_target_type,target_spec=target_specs
        target_columns=_columns(con,link.target_table)
        if link.target_column.lower() not in target_columns:
            continue
        source_column=columns[link.source_column.lower()]
        value_row=con.execute(
            f"SELECT {source_column} FROM {table} WHERE {_identity_where(identity_columns)}",
            tuple(str(v) for v in identity_values),
        ).fetchone()
        if not value_row or value_row[0] is None:
            continue
        target_identity_columns=_identity_columns(target_columns,target_key,target_spec)
        target_column=target_columns[link.target_column.lower()]
        target_matches=con.execute(
            f"SELECT {','.join(target_identity_columns)} FROM {link.target_table} WHERE CAST({target_column} AS TEXT)=? LIMIT 2",
            (str(value_row[0]),),
        ).fetchall()
        if len(target_matches)!=1:
            continue
        target_values=tuple(target_matches[0])
        target_node=_catalog_id(link.target_table,target_values,target_identity_columns)
        target=catalog_node(con,target_node)
        if target is None:
            continue
        rep=(target.get("representations") or [{}])[0]
        links.append({
            "relationship":link.relationship,
            "source_node":node_id,
            "target_node":target_node,
            "target_name":rep.get("display_name") or str(value_row[0]),
            "target_type":rep.get("node_type") or "UNKNOWN",
            "provider_native":True,
        })

    source_identity=dict(zip(identity_columns,identity_values))
    for native in server_source_links(con,table,source_identity):
        target_table=native.get("target_table")
        target_specs=specs.get(target_table)
        if target_specs is None:
            continue
        target_key,_target_name,_target_provider,_target_domain,_target_type,target_spec=target_specs
        target_columns=_columns(con,target_table)
        target_identity_columns=_identity_columns(target_columns,target_key,target_spec)
        requested={str(k).casefold():v for k,v in dict(native.get("target_identity") or {}).items()}
        if not all(column.casefold() in requested for column in target_identity_columns):
            continue
        requested_values=tuple(requested[column.casefold()] for column in target_identity_columns)
        target_rows=con.execute(
            f"SELECT {','.join(target_identity_columns)} FROM {target_table} WHERE {_identity_where(target_identity_columns)} LIMIT 2",
            tuple(str(value) for value in requested_values),
        ).fetchall()
        if len(target_rows)!=1:
            continue
        target_values=tuple(target_rows[0])
        target_node=_catalog_id(target_table,target_values,target_identity_columns)
        target=catalog_node(con,target_node)
        if target is None:
            continue
        rep=(target.get("representations") or [{}])[0]
        candidate={
            "relationship":native.get("relationship") or "SOURCE_LINK",
            "source_node":node_id,
            "target_node":target_node,
            "target_name":rep.get("display_name") or target_node,
            "target_type":rep.get("node_type") or "UNKNOWN",
            "provider_native":True,
            "basis":native.get("basis"),
            "adapter":"server",
        }
        if not any(
            existing.get("relationship")==candidate["relationship"]
            and existing.get("target_node")==candidate["target_node"]
            for existing in links
        ):
            links.append(candidate)
    return links


def relationship_section(edge):
    rel = (edge.get("relationship") or "").upper()
    if is_runtime_edge(edge):
        return "Runtime / Captures & Packets"
    if any(x in rel for x in ("VALIDAT", "EXPECTED", "OBSERVED")):
        return "Validation"
    if any(x in rel for x in ("ENTITY", "DAT", "CSID", "MODEL", "CLIENT")):
        return "Client"
    if any(x in rel for x in ("LUA", "SQL", "CPP", "CXX", "BIND", "ENUM", "IMPORT", "IMPLEMENT")):
        return "Implementation / Server"
    if any(x in rel for x in ("OBTAIN", "DROP", "TRADE", "ITEM", "MISSION", "ACCESS")):
        return "Acquisition / Progression"
    if any(x in rel for x in ("REQUIRE", "SPAWN", "PREREQUISITE", "DEPEND")):
        return "Dependencies / Requirements"
    if any(x in rel for x in ("EVIDENCE", "REFERENCE", "SOURCE", "CONTRADICT")):
        return "Evidence / References"
    return "Other / Unclassified"


def is_runtime_relationship(relationship):
    """Runtime observations are evidence, not semantic traversal topology."""
    rel = (relationship or "").upper()
    return any(x in rel for x in ("PACKET", "CAPTURE", "RUNTIME", "OPCODE"))


def is_runtime_edge(edge):
    if is_runtime_relationship(edge.get("relationship")):
        return True
    if "OBSERV" not in (edge.get("relationship") or "").upper():
        return False
    metadata = edge.get("metadata") or {}
    return (any(key in metadata for key in ("capture_id", "capture", "opcode", "packet_opcode", "entity_id"))
            or str(edge.get("source_node") or "").startswith("capture:")
            or str(edge.get("target_node") or "").startswith("capture:"))


def _runtime_dimensions(edge):
    meta=edge.get("metadata") or {}
    opcode=meta.get("opcode") or meta.get("packet_opcode") or edge.get("relationship")
    capture=(meta.get("capture_id") or meta.get("capture") or edge.get("source_snapshot_id")
             or next((node for node in (edge.get("source_node"),edge.get("target_node"))
                      if str(node or "").startswith("capture:")),None))
    return str(opcode), str(meta.get("direction") or ""), None if capture is None else str(capture)


def runtime_hierarchy(edges):
    """Compact runtime summary. Raw observation edges are deliberately not retained."""
    groups={}
    captures=set()
    for edge in edges:
        opcode,direction,capture=_runtime_dimensions(edge)
        key=(opcode,direction)
        group=groups.setdefault(key,{"opcode":opcode,"direction":direction or None,"observation_count":0,"captures":{}})
        group["observation_count"]+=1
        if capture is not None:
            captures.add(capture)
            group["captures"][capture]=group["captures"].get(capture,0)+1
    rendered=[]
    for group in groups.values():
        capture_groups=[{"capture_id":cid,"observation_count":count} for cid,count in sorted(group.pop("captures").items())]
        group["capture_count"]=len(capture_groups)
        group["capture_groups"]=capture_groups
        rendered.append(group)
    rendered.sort(key=lambda g:(-g["observation_count"],str(g["opcode"]),str(g.get("direction") or "")))
    return {"observation_count":sum(g["observation_count"] for g in rendered),"capture_count":len(captures),"group_count":len(rendered),"groups":rendered}


def filter_runtime_observations(edges, opcode=None, capture_id=None, offset=0, limit=100):
    """Bounded final-level drill-down for a selected runtime group/capture."""
    rows=[]
    for edge in edges:
        edge_opcode,_direction,capture=_runtime_dimensions(edge)
        if opcode is not None and edge_opcode!=str(opcode):
            continue
        if capture_id is not None and capture!=str(capture_id):
            continue
        rows.append(edge)
    total=len(rows)
    offset=max(0,offset)
    limit=max(1,min(limit,250))
    return {"total":total,"offset":offset,"limit":limit,"observations":rows[offset:offset+limit]}


def present_relationships(edges):
    sections={}
    for edge in edges:
        sections.setdefault(relationship_section(edge),[]).append(edge)
    result=[]
    for name,members in sections.items():
        if name=="Runtime / Captures & Packets":
            hierarchy=runtime_hierarchy(members)
            result.append({"name":name,"count":len(members),"runtime_groups":hierarchy["groups"],"edges":[]})
        else:
            result.append({"name":name,"count":len(members),"runtime_groups":[],"edges":members})
    return result
