#!/usr/bin/env python3
"""Focused regression for Feature Trace Implementation Path diagnostics/presentation."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.devtools.features import trace as feature_trace
from workbench.core import graph


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        graph_db=root/"workbench.db"
        catalog=sqlite3.connect(":memory:")
        catalog.execute("CREATE TABLE lsb_mob_spawn_points (mobid INTEGER, mobname TEXT, groupid INTEGER)")
        catalog.execute("CREATE TABLE lsb_mob_groups (zoneid INTEGER, groupid INTEGER, poolid INTEGER, name TEXT, dropid INTEGER, respawntime INTEGER, minLevel INTEGER, maxLevel INTEGER)")
        catalog.execute("CREATE TABLE lsb_mob_pools (poolid INTEGER, name TEXT)")
        catalog.execute("INSERT INTO lsb_mob_spawn_points VALUES (17084539,'Diagnostic Mob',38)")
        catalog.execute("INSERT INTO lsb_mob_groups VALUES (75,38,2002,'Diagnostic Group',777,600,75,78)")
        catalog.execute("INSERT INTO lsb_mob_pools VALUES (2002,'Diagnostic Pool')")
        catalog.commit()

        con=graph.init_db(graph_db)
        con.execute("INSERT INTO entities VALUES (?,?,?,?)",("mob:diagnostic","MOB","Diagnostic Mob","{}"))
        con.execute(
            "INSERT INTO entity_identifiers VALUES (?,?,?,?)",
            ("mob:diagnostic","mobid","17084539","server-catalog"),
        )
        con.execute(
            "INSERT INTO evidence VALUES (?,?,?,?,?,?)",
            ("evidence:diag","SQL","lsb_mob_spawn_points","mobid=17084539","server:lsb","fixture evidence"),
        )
        con.execute(
            "INSERT INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",
            ("rel:diag","mob:diagnostic","capture:1","OBSERVES_ENTITY","evidence:diag","VERIFIED","DISCOVERED","{}","server:lsb"),
        )
        con.commit()

        diag=feature_trace.entity_query_diagnostics(con,catalog,"17084539")
        assert diag["status"]=="UNIQUE_CANONICAL_MAPPING",diag
        assert diag["canonical_roots"]==["mob:diagnostic"],diag

        path=feature_trace.entity_implementation_path(con,catalog,"17084539")
        assert path["mapping_status"]=="UNIQUE_CANONICAL_MAPPING",path
        assert path["canonical"]["root"]=="mob:diagnostic",path
        assert path["canonical"]["direct_relationship_count"]==1,path
        assert path["canonical"]["direct_evidence_count"]==1,path
        assert path["canonical"]["direct_evidence"][0]["evidence_source"]=="lsb_mob_spawn_points",path
        assert path["native_link_count"]>=2,path
        labels={row["label"] for row in path["handoffs"]}
        assert {"Entity Dossier","Canonical Trace","Behavior Inspector","Events / CSID","Capture Evidence","Path diagnostics JSON","Capture #1"} <= labels,path["handoffs"]
        assert path["coverage_cues"]==[],path["coverage_cues"]
        branch=next(b for b in path["branches"] if b["root"]["table"]=="lsb_mob_spawn_points")
        assert branch["native_link_count"]>=2,branch
        assert branch["max_depth"]>=2,branch
        assert branch["target_count"]>=2,branch
        assert branch["root"]["details"]["groupid"]==38,branch["root"]
        assert branch["root"]["sql_href"].startswith("/sql?table=lsb_mob_spawn_points"),branch["root"]
        assert branch["steps"][0]["target_sql_href"].startswith("/sql?table=lsb_mob_groups"),branch["steps"][0]
        assert branch["steps"][0]["target_details"]["poolid"]==2002,branch["steps"][0]

        # No canonical identity: keep source-native path, but explain why semantic traversal is withheld.
        con.execute("DELETE FROM entity_identifiers")
        con.commit()
        unmapped=feature_trace.entity_query_diagnostics(con,catalog,"17084539")
        assert unmapped["status"]=="NO_CANONICAL_MAPPING",unmapped
        path_unmapped=feature_trace.entity_implementation_path(con,catalog,"17084539")
        assert path_unmapped and not path_unmapped["canonical_mapped"],path_unmapped
        assert any(cue["code"]=="IDENTITY_BRIDGE_INCOMPLETE" for cue in path_unmapped["coverage_cues"]),path_unmapped

        # One numeric identity claimed by two canonical roots must be explicit ambiguity.
        for node in ("mob:a","mob:b"):
            con.execute("INSERT OR IGNORE INTO entities VALUES (?,?,?,?)",(node,"MOB",node,"{}"))
            con.execute("INSERT INTO entity_identifiers VALUES (?,?,?,?)",(node,"mobid","17084539","fixture"))
        con.commit()
        ambiguous=feature_trace.entity_query_diagnostics(con,catalog,"17084539")
        assert ambiguous["status"]=="AMBIGUOUS_NUMERIC_MAPPING",ambiguous
        assert len(ambiguous["mappings"][0]["canonical_roots"])==2,ambiguous

        # Two drifted numeric IDs may consolidate only when both map to one explicit root.
        catalog.execute("INSERT INTO lsb_mob_spawn_points VALUES (17000099,'Drifted Diagnostic Mob',38)")
        con.execute("DELETE FROM entity_identifiers")
        con.execute("INSERT INTO entity_identifiers VALUES (?,?,?,?)",("mob:diagnostic","mobid","17084539","old"))
        con.execute("INSERT INTO entity_identifiers VALUES (?,?,?,?)",("mob:diagnostic","client_snapshot_entity_id:new","17000099","new"))
        con.commit()
        drift=feature_trace.entity_query_diagnostics(con,catalog,"Diagnostic Mob")
        assert drift["status"]=="DRIFTED_IDS_ONE_ROOT",drift
        drift_path=feature_trace.entity_implementation_path(con,catalog,"Diagnostic Mob")
        assert drift_path and drift_path["numeric_ids"]==[17000099,17084539],drift_path

        repo_root=Path(__file__).resolve().parents[1]
        template=(repo_root/"gui/templates/feature_trace.html").read_text(encoding="utf-8")
        server=(repo_root/"src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
        for text in (
            "Direct canonical evidence / provenance",
            "Canonical semantic traversal reached its node budget",
            "identifier mapping resolves uniquely",
            "/research/evidence?evidence_id=",
            "Provider branches",
            "Native wiring links",
            "Trace canonical root",
            "Entity resolution diagnostic",
            "matched on:",
            "Entity workflow",
            "Evidence coverage cues",
            "impl-provider-filter",
            "impl-domain-filter",
            "impl-branch-filter",
            "impl-linked-only",
            "impl-reset-filters",
            "Trace this representation",
            "impl-source-facts",
            "Server Lua drill-down",
            "Open indexed SQL row",
            "Behavior graph JSON",
            "Source preview",
            "Indexed SQL row",
        ):
            assert text in template,text
        assert "feature_trace.entity_query_diagnostics" in server
        assert 'implementation_path["trace_summary"]' in server
        assert '@app.get("/features/trace/path.json")' in server
        assert '"implementation_path":path' in server
        assert "def _feature_trace_branch_source_drilldown(" in server
        assert "_FEATURE_TRACE_PROVIDER_SERVER" in server
        assert "preview_lines = lines[:40]" in server
        assert '"status": "RESOLVED"' in server
        assert '"AMBIGUOUS" if len(exact) > 1 else "SEARCH_ONLY"' in server
        assert "_feature_trace_branch_source_drilldown(implementation_path)" in server
        assert "_feature_trace_branch_source_drilldown(path)" in server

        con.close(); catalog.close()

    print("Feature Trace path diagnostics regression: PASS")


if __name__=="__main__":
    main()
