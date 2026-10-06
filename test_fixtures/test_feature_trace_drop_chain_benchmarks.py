from __future__ import annotations

import sqlite3

from workbench.core import graph
from workbench.devtools.features import trace as feature_trace
from workbench.devtools.features.trace_benchmarks import SCENARIO_BY_ID, evaluate_trace
from workbench.devtools.features.trace_expansion import provider_candidates
from workbench.devtools.features.trace_validation import (
    ClosureValidationCase,
    TraceValidationCase,
    validate_case,
    validate_closure_case,
    validate_closure_cases,
)


def _provider_db():
    con=sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    con.executescript("""
    CREATE TABLE topaz_mob_spawn_points(mobid INTEGER PRIMARY KEY,mobname TEXT,groupid INTEGER,pos_x REAL,pos_y REAL,pos_z REAL,pos_rot INTEGER);
    CREATE TABLE topaz_mob_groups(zoneid INTEGER,groupid INTEGER,name TEXT,poolid INTEGER,dropid INTEGER,respawntime INTEGER,minLevel INTEGER,maxLevel INTEGER,PRIMARY KEY(zoneid,groupid));
    CREATE TABLE topaz_mob_pools(poolid INTEGER PRIMARY KEY,name TEXT,familyid INTEGER,modelid INTEGER);
    CREATE TABLE topaz_mob_droplist(dropid INTEGER,dropType INTEGER,groupId INTEGER,groupRate INTEGER,itemId INTEGER,itemRate INTEGER);
    CREATE TABLE topaz_item_basic(itemid INTEGER PRIMARY KEY,name TEXT,stackSize INTEGER,flags INTEGER,aH INTEGER,BaseSell INTEGER);
    """)
    zoneid=100
    mobid=(zoneid<<12)+7
    con.execute("INSERT INTO topaz_mob_spawn_points VALUES(?,?,?,?,?,?,?)",(mobid,"Benchmark NM",9,0,0,0,0))
    con.execute("INSERT INTO topaz_mob_groups VALUES(?,?,?,?,?,?,?,?)",(zoneid,9,"Benchmark NM Group",33,77,300,75,75))
    con.execute("INSERT INTO topaz_mob_pools VALUES(?,?,?,?)",(33,"Benchmark NM Pool",10,123))
    con.execute("INSERT INTO topaz_mob_droplist VALUES(?,?,?,?,?,?)",(77,0,0,1000,5001,250))
    con.execute("INSERT INTO topaz_mob_droplist VALUES(?,?,?,?,?,?)",(77,0,0,1000,5002,100))
    con.execute("INSERT INTO topaz_item_basic VALUES(?,?,?,?,?,?)",(5001,"Benchmark Trophy",1,0,0,0))
    con.execute("INSERT INTO topaz_item_basic VALUES(?,?,?,?,?,?)",(5002,"Benchmark Rare Drop",1,0,0,0))
    con.commit()
    return con,mobid


def _closure_db():
    con=sqlite3.connect(":memory:")
    con.executescript(graph.SCHEMA)
    con.executescript("""
    CREATE TABLE lsb_item_basic(itemid INTEGER, name TEXT);
    CREATE TABLE reference_wiki_mappings(
        mapping_id TEXT, claim_id TEXT, target_domain TEXT, target_table TEXT,
        target_key TEXT, target_label TEXT, mapping_method TEXT,
        mapping_status TEXT, confidence TEXT
    );
    CREATE TABLE identity_snapshots(snapshot_id TEXT, version TEXT);
    CREATE TABLE captures(capture_id INTEGER, capture_label TEXT, client_build TEXT);
    CREATE TABLE research_sessions(research_session_id TEXT, question TEXT, feature_root TEXT, entity_root TEXT);
    """)
    con.execute("INSERT INTO lsb_item_basic VALUES(2413,'Coiler')")
    con.executemany(
        "INSERT INTO reference_wiki_mappings VALUES(?,?,?,?,?,?,?,?,?)",
        [
            ("map-ok","claim-1","item","lsb_item_basic","2413","Coiler","NORMALIZED_NAME_EXACT","MAPPED","HIGH"),
            ("map-ambiguous","claim-2","item","lsb_item_basic","2413","Coiler","NORMALIZED_NAME_EXACT","AMBIGUOUS","LOW"),
        ],
    )
    con.execute("INSERT INTO identity_snapshots VALUES('client:2022','30120222_1')")
    con.execute("INSERT INTO captures VALUES(17,'Ancient Vows retail','30120222_1')")
    con.execute(
        "INSERT INTO features(feature_id,feature_type,name,metadata_json) VALUES(?,?,?,?)",
        ("feature:wotg-25","MISSION","Crossroads of Time","{}"),
    )
    con.execute("INSERT INTO research_sessions VALUES('research:wotg-25','Why does this differ?','feature:wotg-25',NULL)")
    con.execute(
        """INSERT INTO validation_runs(
               run_id,name,source_snapshot_id,target_snapshot_id,feature_id,status,started_at,finished_at,metadata_json
           ) VALUES(?,?,?,?,?,?,?,?,?)""",
        ("validation:wotg-25","WotG 25 validation",None,None,"feature:wotg-25","VERIFIED",None,None,"{}"),
    )
    con.execute(
        "INSERT INTO artifacts(artifact_id,artifact_type,path,metadata_json) VALUES(?,?,?,?)",
        ("artifact:raustigne-lua","LUA","scripts/zones/Southern_San_dOria_S/npcs/Raustigne.lua","{}"),
    )
    con.execute(
        """INSERT INTO migration_actions(
               action_id,migration_id,action,artifact_id,status,reason,metadata_json
           ) VALUES(?,?,?,?,?,?,?)""",
        ("action:1","migration:fixture","COPY_FILE","artifact:raustigne-lua","PLANNED","fixture","{}"),
    )
    con.commit()
    return con


def test_generic_nm_trace_reaches_drop_rows_and_items():
    con,mobid=_provider_db()
    root=f"catalog:topaz_mob_spawn_points:{mobid}"
    rows=provider_candidates(con,root,mode="implementation",max_depth=4)
    relationships=[row.relationship for row in rows]
    assert "SPAWN_USES_GROUP" in relationships
    assert "GROUP_USES_POOL" in relationships
    assert relationships.count("GROUP_HAS_DROP")==2
    assert relationships.count("DROP_GIVES_ITEM")==2

    traced=feature_trace.trace(con,root,4,"both",con,mode="implementation")
    generated={row["relationship"] for row in traced["generated_relationships"]}
    assert generated >= {"SPAWN_USES_GROUP","GROUP_USES_POOL","GROUP_HAS_DROP","DROP_GIVES_ITEM"}
    names={
        rep.get("display_name")
        for node in traced["nodes"]
        for rep in (node.get("representations") or [])
    }
    assert "Benchmark Trophy" in names
    assert "Benchmark Rare Drop" in names
    assert traced["canonical_edges"]==[]

    benchmark=evaluate_trace(traced,SCENARIO_BY_ID["nm"])
    assert benchmark["passed"] is True,benchmark
    assert benchmark["checks"]["required_generators"] is True
    assert benchmark["required"]["drop"] is True
    assert benchmark["required"]["item"] is True

    validation=validate_case(
        con,
        TraceValidationCase("benchmark-nm-real-object", "nm", root=root),
        con,
    )
    assert validation["status"]=="PASS",validation
    assert validation["passed"] is True,validation
    assert validation["resolved_root"]==root,validation
    assert validation["evaluation"]["checks"]["required_generators"] is True,validation
    con.close()

    closure=_closure_db()
    report=validate_closure_cases(
        closure,
        (
            ClosureValidationCase(
                "wiki-to-item",
                "catalog:reference_wiki_mappings:map-ok",
                (("REFERENCE_MAPPING_TARGET","catalog:lsb_item_basic:2413"),),
            ),
            ClosureValidationCase(
                "capture-to-client",
                "catalog:captures:17",
                (("CAPTURE_CLIENT_BUILD","catalog:identity_snapshots:client:2022"),),
            ),
            ClosureValidationCase(
                "mission-research-to-feature",
                "catalog:research_sessions:research:wotg-25",
                (("RESEARCH_FEATURE_ROOT","feature:wotg-25"),),
            ),
            ClosureValidationCase(
                "mission-validation-to-feature",
                "catalog:validation_runs:validation:wotg-25",
                (("VALIDATES_FEATURE","feature:wotg-25"),),
            ),
            ClosureValidationCase(
                "migration-to-artifact",
                "catalog:migration_actions:action:1",
                (("MIGRATION_ACTION_ARTIFACT","artifact:raustigne-lua"),),
            ),
            ClosureValidationCase(
                "ambiguous-wiki-fails-closed",
                "catalog:reference_wiki_mappings:map-ambiguous",
                (),
                forbidden_relationships=("REFERENCE_MAPPING_TARGET",),
            ),
        ),
        closure,
    )
    assert report["counts"]["PASS"]==6,report
    assert report["counts"]["CONTRACT_GAP"]==0,report
    assert report["all_attempted_passed"] is True,report

    closure.execute("INSERT INTO identity_snapshots VALUES('client:2022-copy','30120222_1')")
    duplicate=validate_closure_case(
        closure,
        ClosureValidationCase(
            "duplicate-client-build-fails-closed",
            "catalog:captures:17",
            (),
            forbidden_relationships=("CAPTURE_CLIENT_BUILD",),
        ),
        closure,
    )
    assert duplicate["status"]=="PASS",duplicate
    closure.close()


def test_drop_row_composite_identity_is_stable_and_navigable():
    con,mobid=_provider_db()
    root=f"catalog:topaz_mob_spawn_points:{mobid}"
    rows=provider_candidates(con,root,mode="implementation",max_depth=4)
    drop_targets=sorted({row.target_node for row in rows if row.relationship=="GROUP_HAS_DROP"})
    assert len(drop_targets)==2
    assert all(target.startswith("catalog:topaz_mob_droplist:") for target in drop_targets)
    assert drop_targets[0]!=drop_targets[1]
    item_targets={row.target_node for row in rows if row.relationship=="DROP_GIVES_ITEM"}
    assert item_targets=={"catalog:topaz_item_basic:5001","catalog:topaz_item_basic:5002"}
    con.close()
