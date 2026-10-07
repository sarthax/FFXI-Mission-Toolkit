"""Reconcile emitted mission server-event identities with indexed source/client evidence.

This service does not infer actor aliases or translate CSIDs. It only recognizes exact
zone+actor+CSID evidence where actor identity has already been independently established.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from workbench.core import graph as graph_store
from workbench.core.schema import DependencyEdge


@dataclass(frozen=True)
class ClientEventCheck:
    snapshot_id: str
    status: str
    actor_record_id: str | None = None
    actor_numeric_id: str | None = None
    event_record_id: str | None = None
    event_evidence_id: str | None = None
    confidence: str = "UNKNOWN"
    reason: str | None = None


@dataclass(frozen=True)
class MissionEventReconciliation:
    feature_id: str
    event_node: str
    source_family: str
    zone: str
    actor: str | None
    event_id: int
    source_ref_status: str
    source_ref_node: str | None = None
    client_checks: tuple[ClientEventCheck, ...] = ()


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _feature_events(con: sqlite3.Connection, feature_id: str) -> list[tuple[str,dict]]:
    if not _table_exists(con,"entity_relationships") or not _table_exists(con,"entities"):
        return []
    rows=con.execute(
        """
        SELECT DISTINCT e.entity_id,e.metadata_json
        FROM entity_relationships ft
        JOIN entity_relationships te ON te.source_node=ft.target_node
        JOIN entities e ON e.entity_id=te.target_node
        WHERE ft.source_node=? AND ft.relationship='HAS_TRANSITION'
          AND te.relationship='TRIGGERED_BY_EVENT'
          AND e.entity_type='MISSION_EVENT'
        ORDER BY e.entity_id
        """,
        (feature_id,),
    ).fetchall()
    out=[]
    for entity_id,metadata_json in rows:
        try:
            metadata=json.loads(metadata_json or "{}")
        except (TypeError,ValueError):
            metadata={}
        out.append((entity_id,metadata))
    return out


def _server_ref(catalog_con: sqlite3.Connection | None, source_family: str, zone: str,
                actor: str | None, event_id: int) -> tuple[str,str | None]:
    if catalog_con is None or actor is None or not _table_exists(catalog_con,"npc_event_refs"):
        return "UNAVAILABLE",None
    rows=catalog_con.execute(
        """
        SELECT source,zone_name,npc_script,csid
        FROM npc_event_refs
        WHERE lower(source)=lower(?) AND zone_name=? AND npc_script=? AND csid=?
        LIMIT 2
        """,
        (source_family,zone,actor,event_id),
    ).fetchall()
    if not rows:
        return "MISSING",None
    if len(rows)>1:
        return "AMBIGUOUS",None
    source,zone_name,npc_script,csid=rows[0]
    raw="&".join((
        f"source={quote(str(source),safe='')}",
        f"zone_name={quote(str(zone_name),safe='')}",
        f"npc_script={quote(str(npc_script),safe='')}",
        f"csid={quote(str(csid),safe='')}",
    ))
    return "EXACT",f"catalog:npc_event_refs:{raw}"


def _client_checks(con: sqlite3.Connection, zone: str, actor: str | None,
                   event_id: int) -> tuple[ClientEventCheck,...]:
    if actor is None or not all(_table_exists(con,t) for t in ("identity_snapshots","identity_records")):
        return ()
    snapshots=[
        row[0] for row in con.execute(
            "SELECT snapshot_id FROM identity_snapshots WHERE upper(snapshot_type)='CLIENT' ORDER BY snapshot_id"
        )
    ]
    checks=[]
    for snapshot_id in snapshots:
        actor_rows=[]
        for row in con.execute(
            """
            SELECT record_id,numeric_id,metadata_json
            FROM identity_records
            WHERE snapshot_id=? AND namespace='ENTITY' AND zone_key=?
            ORDER BY record_id
            """,
            (snapshot_id,zone),
        ):
            record_id,numeric_id,metadata_json=row
            try:
                metadata=json.loads(metadata_json or "{}")
            except (TypeError,ValueError):
                metadata={}
            semantic=str(metadata.get("semantic_identity") or "").strip()
            if semantic.casefold()==actor.strip().casefold():
                actor_rows.append((record_id,str(numeric_id)))
        if not actor_rows:
            checks.append(ClientEventCheck(
                snapshot_id,"ACTOR_UNRESOLVED",
                reason="No independently established ENTITY semantic identity matches the source actor in this zone.",
            ))
            continue
        if len(actor_rows)!=1:
            checks.append(ClientEventCheck(
                snapshot_id,"ACTOR_AMBIGUOUS",
                reason="Multiple ENTITY identities match the source actor in this zone.",
            ))
            continue
        actor_record_id,actor_numeric_id=actor_rows[0]
        event_rows=con.execute(
            """
            SELECT record_id,evidence_id,confidence
            FROM identity_records
            WHERE snapshot_id=? AND namespace='EVENT' AND zone_key=?
              AND actor_key=? AND numeric_id=?
            ORDER BY record_id LIMIT 2
            """,
            (snapshot_id,zone,actor_numeric_id,str(event_id)),
        ).fetchall()
        if not event_rows:
            checks.append(ClientEventCheck(
                snapshot_id,"EVENT_UNRESOLVED",actor_record_id,actor_numeric_id,
                reason="Actor identity is exact, but no EVENT record has this CSID in the same snapshot/zone/actor context.",
            ))
            continue
        if len(event_rows)!=1:
            checks.append(ClientEventCheck(
                snapshot_id,"EVENT_AMBIGUOUS",actor_record_id,actor_numeric_id,
                reason="Multiple EVENT records share this exact snapshot/zone/actor/CSID context.",
            ))
            continue
        event_record_id,evidence_id,confidence=event_rows[0]
        checks.append(ClientEventCheck(
            snapshot_id,"EXACT",actor_record_id,actor_numeric_id,
            event_record_id,evidence_id,str(confidence or "UNKNOWN"),
            "Exact client EVENT presence after independently established actor identity.",
        ))
    return tuple(checks)


def reconcile_feature_events(
    con: sqlite3.Connection,
    feature_id: str,
    *,
    catalog_con: sqlite3.Connection | None=None,
) -> tuple[MissionEventReconciliation,...]:
    results=[]
    for event_node,metadata in _feature_events(con,feature_id):
        source_family=str(metadata.get("source_family") or "")
        zone=str(metadata.get("zone") or "")
        actor=metadata.get("actor")
        raw_event_id=metadata.get("event_id")
        try:
            event_id=int(raw_event_id)
        except (TypeError,ValueError):
            continue
        ref_status,ref_node=_server_ref(catalog_con,source_family,zone,actor,event_id)
        results.append(MissionEventReconciliation(
            feature_id,event_node,source_family,zone,actor,event_id,
            ref_status,ref_node,_client_checks(con,zone,actor,event_id),
        ))
    return tuple(results)


def persist_event_reconciliation(
    con: sqlite3.Connection,
    results: tuple[MissionEventReconciliation,...],
    *,
    source_snapshot_id: str | None=None,
    commit: bool=True,
) -> int:
    written=0
    for result in results:
        if result.source_ref_status=="EXACT" and result.source_ref_node:
            graph_store.insert_record(con,DependencyEdge(
                f"mission-event-source-ref:{result.event_node}",
                result.event_node,result.source_ref_node,"SUPPORTED_BY_SOURCE_REF",
                confidence="VERIFIED",status="DISCOVERED",
                discovered_by="mission_event_reconciliation",
                notes="Exact source family + zone + actor script + CSID row in npc_event_refs.",
                source_snapshot_id=source_snapshot_id,
            ))
            written+=1
        for check in result.client_checks:
            if check.status!="EXACT" or not check.event_record_id:
                continue
            graph_store.insert_record(con,DependencyEdge(
                f"mission-event-client:{result.event_node}:{check.snapshot_id}",
                result.event_node,f"catalog:identity_records:{check.event_record_id}",
                "SUPPORTED_BY_CLIENT_EVENT",check.event_evidence_id,
                check.confidence,"DISCOVERED",
                discovered_by="mission_event_reconciliation",
                notes=(
                    f"Exact zone+actor+CSID presence in {check.snapshot_id}; "
                    f"actor identity record {check.actor_record_id}."
                ),
                source_snapshot_id=check.snapshot_id,
            ))
            written+=1
    if commit:
        con.commit()
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("feature_id", help="Canonical mission/quest feature id already emitted to the graph")
    ap.add_argument("--db", type=Path, default=Path("workbench.db"), help="Workbench DB")
    ap.add_argument("--catalog-db", type=Path, default=Path("ffxi_zone_database.db"), help="Indexed source/reference DB")
    ap.add_argument("--write", action="store_true", help="Persist exact support edges; default is preview only")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    catalog = sqlite3.connect(args.catalog_db) if args.catalog_db.exists() else None
    try:
        rows = reconcile_feature_events(con, args.feature_id, catalog_con=catalog)
        if not rows:
            print("no emitted mission events found for feature")
            return
        for row in rows:
            print(f"{row.event_node}")
            print(f"  source ref: {row.source_ref_status}" + (f" -> {row.source_ref_node}" if row.source_ref_node else ""))
            for check in row.client_checks:
                suffix = f" -> {check.event_record_id}" if check.event_record_id else ""
                print(f"  client {check.snapshot_id}: {check.status} [{check.confidence}]{suffix}")
                if check.reason:
                    print(f"    {check.reason}")
        if not args.write:
            print("preview only; pass --write to persist exact support relationships")
            return
        count = persist_event_reconciliation(con, rows)
        print(f"persisted relationships: {count}")
    finally:
        if catalog is not None:
            catalog.close()
        con.close()


if __name__ == "__main__":
    main()
