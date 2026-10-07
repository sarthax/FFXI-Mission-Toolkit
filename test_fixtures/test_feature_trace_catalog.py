#!/usr/bin/env python3
"""Focused discovery and presentation regressions for Feature Trace."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from workbench.devtools.features import trace as feature_trace
from workbench.core.services.feature_trace_catalog import present_relationships, runtime_hierarchy, filter_runtime_observations, provider_relationships
from workbench.core.services.feature_trace_dossier import build_dossier


def main():
    con=sqlite3.connect(":memory:")
    con.execute("CREATE TABLE entities (entity_id TEXT, entity_type TEXT, display_name TEXT, metadata_json TEXT)")
    con.execute("CREATE TABLE sql_item_basic (itemid INTEGER, name TEXT, sortname TEXT)")
    con.executemany("INSERT INTO sql_item_basic VALUES (?,?,?)",[(2413,"Coiler","coiler"),(8583,"Coiler","coiler")])
    con.execute("INSERT INTO entities VALUES (?,?,?,?)",("entity:fixture","NPC","Coiler","{}"))
    matches=feature_trace.search_nodes(con,"cOiL")
    assert len(matches)==3 and {m["node_id"] for m in matches if m["catalog_only"]}=={"catalog:sql_item_basic:2413","catalog:sql_item_basic:8583"}
    assert feature_trace.node_info(con,"catalog:sql_item_basic:2413")["known"]
    rep=feature_trace.node_info(con,"catalog:sql_item_basic:2413")["representations"][0]
    assert rep["metadata"]["numeric_id"]==2413 and rep["metadata"]["provider"]=="server-sql"
    assert next(m for m in matches if m["node_id"]=="catalog:sql_item_basic:2413")["provider"]=="server-sql"
    con.execute("CREATE TABLE custom_objects (id INTEGER, name TEXT)")
    con.execute("INSERT INTO custom_objects VALUES (77,'Fallback Probe')")
    fallback=feature_trace.search_nodes(con,"Fallback Probe")
    assert fallback[0]["provider"]=="schema-fallback"

    # mob_groups is composite-keyed by zoneid + groupid; groupid alone is not globally unique.
    con.execute("CREATE TABLE lsb_mob_groups (zoneid INTEGER, groupid INTEGER, poolid INTEGER, name TEXT, dropid INTEGER, respawntime INTEGER, minLevel INTEGER, maxLevel INTEGER)")
    con.executemany("INSERT INTO lsb_mob_groups VALUES (?,?,?,?,?,?,?,?)",[
        (55,38,1001,"Group Thirty Eight",501,300,70,72),
        (75,38,2002,"Group Thirty Eight",777,600,75,78),
    ])
    group_matches=feature_trace.search_nodes(con,"Group Thirty Eight")
    group_ids={row["node_id"] for row in group_matches if row.get("table")=="lsb_mob_groups"}
    assert group_ids=={
        "catalog:lsb_mob_groups:zoneid=55&groupid=38",
        "catalog:lsb_mob_groups:zoneid=75&groupid=38",
    },group_ids
    assert feature_trace.node_info(con,"catalog:lsb_mob_groups:38")["known"] is False
    group_node=feature_trace.node_info(con,"catalog:lsb_mob_groups:zoneid=75&groupid=38")
    assert group_node["known"]
    group_meta=group_node["representations"][0]["metadata"]
    assert group_meta["identity"]=={"zoneid":75,"groupid":38}
    assert group_meta["details"]["dropid"]==777
    drop_search=[row for row in feature_trace.search_nodes(con,"777") if row.get("table")=="lsb_mob_groups"]
    assert drop_search and "dropid" in drop_search[0]["matched_on"],drop_search
    con.execute("CREATE TABLE dsp_mob_groups (groupid INTEGER, name TEXT)")
    con.execute("INSERT INTO dsp_mob_groups VALUES (38,'Malformed Provider Group')")
    assert not feature_trace.search_nodes(con,"Malformed Provider Group")

    con.execute("CREATE TABLE lsb_mob_pools (poolid INTEGER, name TEXT, familyid INTEGER, modelid TEXT)")
    con.executemany("INSERT INTO lsb_mob_pools VALUES (?,?,?,?)",[(1001,"Pool 1001",10,"0x0001"),(2002,"Pool 2002",20,"0x0002")])
    pool_node=feature_trace.node_info(con,"catalog:lsb_mob_pools:2002")
    assert pool_node["representations"][0]["metadata"]["details"]=={"familyid":20,"modelid":"0x0002"}
    zone75_mobid=(1<<24)|(75<<12)|123
    con.execute("CREATE TABLE lsb_mob_spawn_points (mobid INTEGER, mobname TEXT, groupid INTEGER)")
    con.execute("INSERT INTO lsb_mob_spawn_points VALUES (?,?,?)",(zone75_mobid,"Zone Seventy Five Mob",38))
    spawn_links=provider_relationships(con,f"catalog:lsb_mob_spawn_points:{zone75_mobid}")
    assert len(spawn_links)==1,spawn_links
    assert spawn_links[0]["relationship"]=="SPAWN_USES_GROUP"
    assert spawn_links[0]["target_node"]=="catalog:lsb_mob_groups:zoneid=75&groupid=38"
    assert spawn_links[0]["adapter"]=="server"

    # Arbitrary entity IDs/names consolidate source representations into an Implementation Path
    # without manufacturing canonical graph edges.
    graph_entity=sqlite3.connect(":memory:")
    graph_entity.execute("CREATE TABLE entity_relationships (relationship_id TEXT, source_node TEXT, target_node TEXT, relationship TEXT, evidence_id TEXT, confidence TEXT, status TEXT, metadata_json TEXT, source_snapshot_id TEXT)")
    path_by_id=feature_trace.entity_implementation_path(graph_entity,con,str(zone75_mobid))
    assert path_by_id is not None,path_by_id
    assert path_by_id["numeric_id"]==zone75_mobid,path_by_id
    assert path_by_id["canonical_mapped"] is False,path_by_id
    lsb_branch=next(b for b in path_by_id["branches"] if b["root"]["node_id"]==f"catalog:lsb_mob_spawn_points:{zone75_mobid}")
    assert [s["relationship"] for s in lsb_branch["steps"]][:2]==["SPAWN_USES_GROUP","GROUP_USES_POOL"],lsb_branch

    path_by_name=feature_trace.entity_implementation_path(graph_entity,con,"Zone Seventy Five Mob")
    assert path_by_name and path_by_name["numeric_id"]==zone75_mobid,path_by_name

    graph_entity.execute("CREATE TABLE entity_identifiers (entity_id TEXT, identifier_type TEXT, identifier_value TEXT)")
    graph_entity.execute("INSERT INTO entity_identifiers VALUES ('npc:zone75fixture','mobid',?)",(str(zone75_mobid),))
    # Unrelated domains can reuse the same numeric value; they must not make entity identity
    # ambiguous when identifier_type distinguishes the namespace.
    graph_entity.execute("INSERT INTO entity_identifiers VALUES ('item:numeric-collision','itemid',?)",(str(zone75_mobid),))
    path_mapped=feature_trace.entity_implementation_path(graph_entity,con,str(zone75_mobid))
    assert path_mapped["canonical_root"]=="npc:zone75fixture",path_mapped
    assert path_mapped["canonical_mapped"] is True,path_mapped
    graph_entity.close()

    con.execute("CREATE TABLE lsb_instance_list (instanceid INTEGER, instance_name TEXT)")
    con.execute("INSERT INTO lsb_instance_list VALUES (100,'Fixture Instance')")
    con.execute("CREATE TABLE lsb_instance_entities (instanceid INTEGER, id INTEGER)")
    con.execute("INSERT INTO lsb_instance_entities VALUES (?,?)",(100,zone75_mobid))
    instance_id=f"catalog:lsb_instance_entities:instanceid=100&id={zone75_mobid}"
    instance_node=feature_trace.node_info(con,instance_id)
    assert instance_node["known"]
    assert instance_node["representations"][0]["display_name"]==f"Instance 100 entity {zone75_mobid}"
    instance_search=feature_trace.search_nodes(con,str(zone75_mobid))
    bridge=next(row for row in instance_search if row.get("table")=="lsb_instance_entities")
    assert bridge["node_id"]==instance_id and "id" in bridge["matched_on"]
    instance_links=provider_relationships(con,instance_id)
    assert {link["relationship"] for link in instance_links}=={"INSTANCE_MEMBER_OF","INSTANCE_ENTITY_MOB"},instance_links
    assert any(link["target_node"]=="catalog:lsb_instance_list:100" for link in instance_links)
    assert any(link["target_node"]==f"catalog:lsb_mob_spawn_points:{zone75_mobid}" for link in instance_links)

    group_links=provider_relationships(con,"catalog:lsb_mob_groups:zoneid=75&groupid=38")
    assert len(group_links)==1,group_links
    assert group_links[0]["relationship"]=="GROUP_USES_POOL"
    assert group_links[0]["target_node"]=="catalog:lsb_mob_pools:2002"

    con.execute("CREATE TABLE lsb_item_basic (itemid INTEGER, name TEXT)")
    con.execute("CREATE TABLE lsb_item_equipment (itemid INTEGER, name TEXT)")
    con.execute("INSERT INTO lsb_item_basic VALUES (2413,'Coiler')")
    con.execute("INSERT INTO lsb_item_equipment VALUES (2413,'Coiler')")
    item_links=provider_relationships(con,"catalog:lsb_item_equipment:2413")
    assert len(item_links)==1,item_links
    assert item_links[0]["relationship"]=="ITEM_DETAIL_FOR"
    assert item_links[0]["target_node"]=="catalog:lsb_item_basic:2413"

    # Additional durable named server objects participate through explicit providers.
    expected_provider={"sql":"server-sql","lsb":"landsandboat","topaz":"topaz","dsp":"dsp"}
    for prefix in ("sql","lsb","topaz","dsp"):
        if prefix!="lsb":
            con.execute(f"CREATE TABLE {prefix}_mob_pools (poolid INTEGER, name TEXT)")
            con.execute(f"INSERT INTO {prefix}_mob_pools VALUES (2002,'Pool 2002 {prefix}')")
        con.execute(f"CREATE TABLE {prefix}_mob_skills (mob_skill_id INTEGER, name TEXT)")
        con.execute(f"INSERT INTO {prefix}_mob_skills VALUES (900,'Provider Skill {prefix}')")
        con.execute(f"CREATE TABLE {prefix}_spell_list (spellid INTEGER, name TEXT)")
        con.execute(f"INSERT INTO {prefix}_spell_list VALUES (500,'Provider Spell {prefix}')")
        con.execute(f"CREATE TABLE {prefix}_blue_spell_list (spellid INTEGER, mob_skill_id INTEGER)")
        con.execute(f"INSERT INTO {prefix}_blue_spell_list VALUES (500,900)")
        con.execute(f"CREATE TABLE {prefix}_pet_list (petid INTEGER, name TEXT, poolid INTEGER)")
        con.execute(f"INSERT INTO {prefix}_pet_list VALUES (77,'Provider Pet {prefix}',2002)")
        skill_rows=feature_trace.search_nodes(con,f"Provider Skill {prefix}")
        assert any(row.get("provider")==expected_provider[prefix] for row in skill_rows),(prefix,skill_rows)
        blue_node=feature_trace.node_info(con,f"catalog:{prefix}_blue_spell_list:500")
        assert blue_node["known"]
        blue_rep=blue_node["representations"][0]
        assert blue_rep["display_name"]=="Blue spell wiring 500"
        assert blue_rep["metadata"]["details"]["mob_skill_id"]==900
        blue_links=provider_relationships(con,f"catalog:{prefix}_blue_spell_list:500")
        assert {link["relationship"] for link in blue_links}=={"BLUE_SPELL_SPELL","BLUE_SPELL_MOB_SKILL"},(prefix,blue_links)
        assert {link["target_node"] for link in blue_links}=={f"catalog:{prefix}_spell_list:500",f"catalog:{prefix}_mob_skills:900"}
        blue_search=[
            row for row in feature_trace.search_nodes(con,"900")
            if row.get("table")==f"{prefix}_blue_spell_list"
        ]
        assert blue_search and "mob_skill_id" in blue_search[0]["matched_on"],(prefix,blue_search)
        pet_links=provider_relationships(con,f"catalog:{prefix}_pet_list:77")
        assert pet_links and pet_links[0]["relationship"]=="PET_USES_POOL",(prefix,pet_links)
        assert pet_links[0]["target_node"]==f"catalog:{prefix}_mob_pools:2002"

    con.execute("CREATE TABLE lsb_effects (effectid INTEGER, name TEXT, norm_name TEXT, display_name TEXT)")
    con.execute("INSERT INTO lsb_effects VALUES (12,'provider_effect','provider effect','Provider Effect Display')")
    con.execute("CREATE TABLE topaz_effects (effectid INTEGER, name TEXT, norm_name TEXT)")
    con.execute("INSERT INTO topaz_effects VALUES (12,'provider_effect_topaz','provider effect topaz')")
    con.execute("CREATE TABLE dsp_effects (effectid INTEGER, name TEXT, norm_name TEXT)")
    con.execute("INSERT INTO dsp_effects VALUES (12,'provider_effect_dsp','provider effect dsp')")
    effect_rows=feature_trace.search_nodes(con,"Provider Effect Display")
    assert any(row.get("table")=="lsb_effects" and row.get("provider")=="landsandboat" and "display_name" in row.get("matched_on",[]) for row in effect_rows),effect_rows
    assert any(row.get("provider")=="topaz" for row in feature_trace.search_nodes(con,"provider effect topaz"))
    assert any(row.get("provider")=="dsp" for row in feature_trace.search_nodes(con,"provider effect dsp"))

    # Server event references are composite by source+zone+script+CSID; CSID alone can collide.
    con.execute("CREATE TABLE npc_event_refs (source TEXT, zone_name TEXT, npc_script TEXT, csid INTEGER)")
    con.executemany("INSERT INTO npc_event_refs VALUES (?,?,?,?)",[
        ("lsb","Southern_San_dOria_S","Raustigne",149),
        ("topaz","Southern_San_dOria_S","Raustigne",149),
    ])
    event_rows=[
        row for row in feature_trace.search_nodes(con,"Raustigne")
        if row.get("table")=="npc_event_refs"
    ]
    assert len(event_rows)==2,event_rows
    assert {row["provider"] for row in event_rows}=={"server-event-refs"}
    assert {row["identity"]["source"] for row in event_rows}=={"lsb","topaz"}
    lsb_event_id="catalog:npc_event_refs:source=lsb&zone_name=Southern_San_dOria_S&npc_script=Raustigne&csid=149"
    event_node=feature_trace.node_info(con,lsb_event_id)
    assert event_node["known"]
    assert event_node["representations"][0]["display_name"]=="lsb Southern_San_dOria_S/Raustigne event 149"
    assert feature_trace.node_info(con,"catalog:npc_event_refs:149")["known"] is False

    # Key-item providers preserve LSB-primary, Topaz, and retail/reference provenance.
    con.execute("CREATE TABLE keyitems_ours (id INTEGER, const_name TEXT, norm_name TEXT)")
    con.execute("INSERT INTO keyitems_ours VALUES (794,'FIXTURE_KEY_ITEM','fixturekeyitem')")
    con.execute("CREATE TABLE topaz_keyitems (id INTEGER, const_name TEXT, norm_name TEXT)")
    con.execute("INSERT INTO topaz_keyitems VALUES (814,'FIXTURE_TOPAZ_KEY_ITEM','fixturetopazkeyitem')")
    con.execute("CREATE TABLE keyitems_external (id INTEGER, name TEXT, norm_name TEXT)")
    con.execute("INSERT INTO keyitems_external VALUES (900,'Fixture Retail Key Item','fixtureretailkeyitem')")
    lsb_ki=feature_trace.search_nodes(con,"FIXTURE_KEY_ITEM")
    assert any(row.get("provider")=="landsandboat" and row.get("node_id")=="catalog:keyitems_ours:794" for row in lsb_ki),lsb_ki
    topaz_ki=feature_trace.search_nodes(con,"FIXTURE_TOPAZ_KEY_ITEM")
    assert any(row.get("provider")=="topaz" and row.get("node_id")=="catalog:topaz_keyitems:814" for row in topaz_ki),topaz_ki
    retail_ki=feature_trace.search_nodes(con,"Fixture Retail Key Item")
    assert any(row.get("provider")=="retail-reference" and row.get("domain")=="reference" for row in retail_ki),retail_ki
    assert feature_trace.node_info(con,"catalog:keyitems_ours:794")["known"]
    con.execute("INSERT INTO keyitems_ours VALUES (794,'DUPLICATE_FIXTURE_KEY_ITEM','duplicatefixturekeyitem')")
    assert feature_trace.node_info(con,"catalog:keyitems_ours:794")["known"] is False

    # Explicit non-server providers expose durable searchable records, not raw observation rows.
    con.execute("CREATE TABLE identity_snapshots (snapshot_id TEXT, version TEXT)")
    con.execute("INSERT INTO identity_snapshots VALUES ('client:2022','30120222_1')")
    con.execute("CREATE TABLE identity_records (record_id TEXT, semantic_key TEXT, snapshot_id TEXT, namespace TEXT, numeric_id TEXT, zone_key TEXT, actor_key TEXT, owner_key TEXT, evidence_id TEXT)")
    con.execute("INSERT INTO identity_records VALUES ('identity:event:1','EVENT:zone:actor:149','client:2022','EVENT','16974347','SOUTHERN_SAN_DORIA_S','Raustigne',NULL,'evidence:client:1')")
    con.execute("INSERT INTO identity_records VALUES ('identity:entity:1','ENTITY:SOUTHERN_SAN_DORIA_S:NPC:Raustigne','client:2022','ENTITY','16974347','SOUTHERN_SAN_DORIA_S','Raustigne',NULL,'evidence:client:entity:1')")
    con.execute("CREATE TABLE captures (capture_id INTEGER, capture_label TEXT, capturer TEXT, content_type TEXT, zones TEXT, mission_name TEXT, client_build TEXT, is_retail INTEGER, start_time INTEGER)")
    con.execute("INSERT INTO captures VALUES (17,'Ancient Vows retail','tester','Missions','Riverne - Site #A01','Ancient Vows','30120222_1',1,12345)")
    con.execute("CREATE TABLE research_sessions (research_session_id TEXT, question TEXT, provider TEXT, model TEXT, feature_root TEXT, entity_root TEXT, verification_state TEXT)")
    con.execute("INSERT INTO research_sessions VALUES ('research:1','Why does this event differ?','ollama','test-model','feature:wotg-25','npc:raustigne','DRAFT')")
    con.execute("CREATE TABLE research_proposals (proposal_id TEXT, subject_id TEXT)")
    con.execute("INSERT INTO research_proposals VALUES ('proposal:1','npc:16974347')")
    con.execute("CREATE TABLE validation_runs (run_id TEXT, name TEXT)")
    con.execute("INSERT INTO validation_runs VALUES ('run:1','Ancient Vows validation')")
    con.execute("CREATE TABLE validation_results (validation_id TEXT, validation_type TEXT, run_id TEXT, subject_id TEXT, status TEXT, evidence_id TEXT, source TEXT, target TEXT)")
    con.execute("INSERT INTO validation_results VALUES ('validation:1','EVENT_MATCH','run:1','npc:424242','VERIFIED','evidence:validation:1','capture','server')")
    con.execute("CREATE TABLE migrations (migration_id TEXT, feature_id TEXT)")
    con.execute("INSERT INTO migrations VALUES ('migration:1','feature:ancient-vows')")
    con.execute("CREATE TABLE migration_actions (action_id TEXT, action TEXT)")
    con.execute("INSERT INTO migration_actions VALUES ('action:1','COPY_FILE')")
    con.execute("CREATE TABLE package_scope_reviews (migration_id TEXT, status TEXT)")
    con.execute("INSERT INTO package_scope_reviews VALUES ('migration:1','APPROVED')")
    provider_expectations={
        "30120222_1":"client-identity",
        "EVENT:zone:actor:149":"client-identity",
        "Ancient Vows retail":"captures",
        "Why does this event differ?":"research",
        "proposal:1":"research",
        "Ancient Vows validation":"validation",
        "EVENT_MATCH":"validation",
        "feature:ancient-vows":"packages",
        "COPY_FILE":"packages",
    }
    for query,provider in provider_expectations.items():
        rows=feature_trace.search_nodes(con,query)
        assert any(row.get("provider")==provider for row in rows),(query,rows)
    alias_expectations={
        "SOUTHERN_SAN_DORIA_S":("client-identity","zone_key"),
        "Riverne - Site #A01":("captures","zones"),
        "feature:wotg-25":("research","feature_root"),
        "npc:424242":("validation","subject_id"),
    }
    for query,(provider,field) in alias_expectations.items():
        rows=feature_trace.search_nodes(con,query)
        hit=next((row for row in rows if row.get("provider")==provider),None)
        assert hit is not None,(query,rows)
        assert field in hit.get("matched_on",[]),(query,hit)

    # Numeric client identity aliases remain searchable across namespaces, but an entity
    # Implementation Path must admit only ENTITY rows rather than conflating EVENT ids.
    numeric_identity_rows=[
        row for row in feature_trace.search_nodes(con,"16974347")
        if row.get("table")=="identity_records"
    ]
    assert {row.get("aliases",{}).get("namespace") for row in numeric_identity_rows}=={"EVENT","ENTITY"},numeric_identity_rows
    assert all(row.get("aliases",{}).get("numeric_id")=="16974347" for row in numeric_identity_rows),numeric_identity_rows
    assert all("numeric_id" not in row for row in numeric_identity_rows),numeric_identity_rows
    graph=sqlite3.connect(":memory:")
    graph.execute("CREATE TABLE entities (entity_id TEXT, entity_type TEXT, display_name TEXT, metadata_json TEXT)")
    graph.execute("CREATE TABLE entity_relationships (relationship_id TEXT, source_node TEXT, target_node TEXT, relationship TEXT, evidence_id TEXT, confidence TEXT, status TEXT, metadata_json TEXT, source_snapshot_id TEXT)")
    graph.execute("CREATE TABLE validation_runs (run_id TEXT, name TEXT)")
    graph.execute("INSERT INTO validation_runs VALUES ('run:graph','Graph-side validation')")
    graph.execute("CREATE TABLE validation_results (validation_id TEXT, validation_type TEXT, run_id TEXT)")
    graph.execute("INSERT INTO validation_results VALUES ('validation:graph','EVENT_MATCH','run:graph')")

    client_entity_path=feature_trace.entity_implementation_path(graph,con,"16974347")
    assert client_entity_path is not None,client_entity_path
    client_identity_branches=[
        branch for branch in client_entity_path["branches"]
        if (branch.get("root") or {}).get("table")=="identity_records"
    ]
    assert len(client_identity_branches)==1,client_entity_path
    assert client_identity_branches[0]["root"]["aliases"]["namespace"]=="ENTITY",client_entity_path
    graph_trace=feature_trace.trace(graph,"catalog:validation_results:validation:graph",3,"both",con)
    graph_dossier=build_dossier(graph_trace)
    assert graph_dossier["identity"]["provider"]=="validation"
    assert graph_dossier["provider_relationship_count"]==1
    assert graph_dossier["provider_relationships"][0]["relationship"]=="FROM_VALIDATION_RUN"
    assert graph_dossier["provider_relationships"][0]["target_node"]=="catalog:validation_runs:run:graph"
    assert not graph_trace["edges"]
    client_trace=feature_trace.trace(graph,"catalog:identity_snapshots:client:2022",3,"both",con)
    client_dossier=build_dossier(client_trace)
    assert client_dossier["identity"]["provider"]=="client-identity"
    assert client_dossier["identity"]["domain"]=="client"
    assert client_dossier["identity"]["inspect_href"]=="/clientoverview"
    assert not client_trace["edges"]
    capture_trace=feature_trace.trace(graph,"catalog:captures:17",3,"both",con)
    capture_dossier=build_dossier(capture_trace)
    assert capture_dossier["identity"]["details"]["client_build"]=="30120222_1"
    assert capture_dossier["identity"]["details"]["mission_name"]=="Ancient Vows"
    assert capture_dossier["identity"]["inspect_href"]=="/captures/17"
    rows_2413=feature_trace.search_nodes(con,"2413")
    ids_2413={row["node_id"] for row in rows_2413}
    assert {"catalog:sql_item_basic:2413","catalog:lsb_item_basic:2413","catalog:lsb_item_equipment:2413"}.issubset(ids_2413)
    coiler_rows=feature_trace.search_nodes(con,"Coiler")
    coiler_ids={row["node_id"] for row in coiler_rows}
    assert {"entity:fixture","catalog:sql_item_basic:2413","catalog:sql_item_basic:8583"}.issubset(coiler_ids)  # ambiguity remains visible
    bridged=feature_trace.search_nodes(graph,"Coiler",con)
    assert any(m["node_id"]=="catalog:sql_item_basic:2413" for m in bridged)
    catalog_trace=feature_trace.trace(graph,"catalog:sql_item_basic:2413",3,"both",con)
    assert catalog_trace["nodes"][0]["known"] and not catalog_trace["edges"]
    graph.executemany("INSERT INTO entities VALUES (?,?,?,?)",[("npc:root","NPC","Root","{}"),("runtime:one","OBSERVATION","Packet one","{}"),("entity:semantic","NPC","Semantic","{}")])
    graph.executemany("INSERT INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",[
        ("semantic","npc:root","entity:semantic","IMPLEMENTS",None,"HIGH","KNOWN","{}",None),
        ("packet-1","npc:root","runtime:one","OBSERVES","ev:1","OBSERVED","KNOWN",'{"opcode":"0x00E","capture_id":1}',None),
        ("packet-2","npc:root","runtime:one","OBSERVES","ev:2","OBSERVED","KNOWN",'{"opcode":"0x00E","capture_id":2}',None),
    ])
    semantic_trace=feature_trace.trace(graph,"npc:root",3,"both",con)
    assert {node["node_id"] for node in semantic_trace["nodes"]}=={"npc:root","entity:semantic"}
    assert len(semantic_trace["edges"])==1 and semantic_trace["runtime_hierarchy"]["groups"][0]["observation_count"]==2, semantic_trace
    assert "_runtime_edges" not in semantic_trace
    dossier=build_dossier(semantic_trace)
    assert dossier["identity"]["node_id"]=="npc:root" and dossier["runtime_capture_count"]==2
    assert any(f["name"]=="Implementation / Server" for f in dossier["facets"])
    template=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"feature_trace.html").read_text(encoding="utf-8")
    assert "grouped without expanding semantic topology" in template
    assert "Evidence Dossier" in template
    assert "Implementation Path" in template
    assert "canonical graph identity mapped" in template
    assert "no canonical graph identity mapping yet" in template
    assert "Open Entity Dossier" in template
    assert "Canonical Dependency Map" in template
    assert "No canonical root selected" in template
    assert "Absolute Virtue reference fixture" not in template
    assert "Source details" in template and "Open source view" in template
    assert "Source-native links" in template
    assert "Matched on" in template
    assert "section.edges" in template and "{% for edge in result.edges %}" not in template
    assert "/features/trace/runtime.json" in template
    assert "runtimeEsc(e.relationship)" in template
    edges=[
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x00E","capture_id":1},"source_snapshot_id":None},
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x00E","capture_id":2},"source_snapshot_id":None},
        {"relationship":"PACKET_OBSERVED","metadata":{"opcode":"0x032","capture_id":1},"source_snapshot_id":None},
        {"relationship":"NEW_RELATION","metadata":{}},
    ]
    sections=present_relationships(edges)
    runtime=next(s for s in sections if s["name"]=="Runtime / Captures & Packets")
    opcode=next(g for g in runtime["runtime_groups"] if g["opcode"]=="0x00E")
    assert opcode["observation_count"]==2 and opcode["capture_count"]==2 and "edges" not in opcode
    hierarchy=runtime_hierarchy(edges[:3])
    assert hierarchy["observation_count"]==3 and hierarchy["capture_count"]==2
    page=filter_runtime_observations(edges[:3],"0x00E","1",0,10)
    assert page["total"]==1 and len(page["observations"])==1
    bounded=filter_runtime_observations(edges[:3],limit=9999)
    assert bounded["limit"]==250
    assert any(s["name"]=="Other / Unclassified" for s in sections)
    # Both production databases may differ in schema; discovery must tolerate that.
    with sqlite3.connect(Path(__file__).resolve().parents[1]/"workbench.db") as graph_db, sqlite3.connect(Path(__file__).resolve().parents[1]/"ffxi_zone_database.db") as index_db:
        feature_trace.search_nodes(graph_db,"coiler",index_db)
        real=feature_trace.trace(graph_db,"npc:16974347",3,"both",index_db)
        assert real["runtime_observation_count"] > 0
        assert any(group["capture_count"] > 0 for group in real["runtime_hierarchy"]["groups"])
    print("feature trace catalog self-test: PASS")


if __name__=="__main__":
    main()
