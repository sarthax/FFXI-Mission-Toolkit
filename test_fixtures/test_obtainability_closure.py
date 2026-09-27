#!/usr/bin/env python3
"""Regression fixture for generic recursive obtainability/access closure.

The labels model a difficult chained encounter, but the service only consumes
ordinary graph nodes, directed relationships, logical-group metadata and evidence.
"""
from pathlib import Path
import tempfile

from workbench.core import graph
from workbench.core.schema import DependencyEdge, Evidence
from workbench.core.services.obtainability_closure import build_obtainability_closure, closure_projection


def entity(con,node,label,*,terminal=False):
    con.execute("INSERT INTO entities VALUES (?,?,?,?)",(node,"FIXTURE",label,'{"obtainability_terminal": true}' if terminal else "{}"))


def edge(con,eid,source,target,relationship,group,**metadata):
    evidence=f"evidence:{eid}"
    graph.insert_record(con,Evidence(evidence,"FIXTURE","absolute-virtue-regression",f"fixture:{eid}","fixture",eid))
    graph.insert_record(con,DependencyEdge(eid,source,target,relationship,evidence,"VERIFIED","DISCOVERED",notes={"requirement_group":group,**metadata}))


def main():
    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"closure.db")
        names={
            "entity:av":"Absolute Virtue", "entity:jol":"Jailer of Love",
            "item:v4":"Fourth Virtue", "item:v5":"Fifth Virtue", "item:v6":"Sixth Virtue",
            "item:v1":"First Virtue", "item:v2":"Second Virtue", "item:v3":"Third Virtue",
            "mob:justice":"Jailer of Justice", "mob:hope":"Jailer of Hope", "mob:prudence":"Jailer of Prudence",
            "item:deed":"Deed of Moderation", "item:organ":"HQ organ", "zone:sea":"Sea access",
            "mission:cop":"Chains of Promathia", "item:alternative":"Alternative organ source", "missing:record":"Unindexed prerequisite",
            "mob:source-one":"Source NM One", "mob:source-two":"Source NM Two", "mob:source-three":"Source NM Three",
        }
        for node,label in names.items(): entity(con,node,label,terminal=node in {"mission:cop","item:alternative"})
        edge(con,"av-jol","entity:av","entity:jol","SPAWNED_BY",{"id":"av-spawn","operator":"AND"},probability=0.25)
        for eid,item,mob in (("jol-v4","item:v4","mob:justice"),("jol-v5","item:v5","mob:hope"),("jol-v6","item:v6","mob:prudence")):
            edge(con,eid,"entity:jol",item,"REQUIRES_ITEMS",{"id":"jol-trade","operator":"AND"},quantity=1,consumed=True)
            edge(con,f"{eid}-source",item,mob,"OBTAINED_FROM",{"id":f"{item}-source","operator":"AND"})
        for mob,virtue,source in (("mob:justice","item:v1","mob:source-one"),("mob:hope","item:v2","mob:source-two"),("mob:prudence","item:v3","mob:source-three")):
            edge(con,f"{mob}-virtue",mob,virtue,"REQUIRES_ITEMS",{"id":f"{mob}-trade","operator":"AND"},quantity=1,consumed=True)
            edge(con,f"{mob}-deed",mob,"item:deed","REQUIRES_ITEMS",{"id":f"{mob}-trade","operator":"AND"},quantity=1,consumed=True)
            edge(con,f"{mob}-organ",mob,"item:organ","REQUIRES_ITEMS",{"id":f"{mob}-trade","operator":"AND"},quantity=3,consumed=True)
            edge(con,f"{mob}-access",mob,"zone:sea","REQUIRES_ACCESS",{"id":f"{mob}-access","operator":"AND"},zone="Al'Taieu")
            edge(con,f"{virtue}-source",virtue,source,"OBTAINED_FROM",{"id":f"{virtue}-source","operator":"OR"},probability=0.5)
            edge(con,f"{source}-access",source,"zone:sea","REQUIRES_ACCESS",{"id":f"{source}-access","operator":"AND"},zone="Grand Palace of Hu'Xzoi")
        edge(con,"organ-alt","item:organ","item:alternative","OBTAINED_FROM",{"id":"organ-source","operator":"OR"},probability=0.5)
        edge(con,"organ-missing","item:organ","missing:record","OBTAINED_FROM",{"id":"organ-source","operator":"OR"})
        edge(con,"sea-cop","zone:sea","mission:cop","REQUIRES_MISSION",{"id":"sea-access","operator":"AND"})
        edge(con,"cop-cycle","mission:cop","zone:sea","UNLOCKS",{"id":"fixture-cycle","operator":"AND"})
        con.commit()
        closure=build_obtainability_closure(con,"entity:av",relationships={"SPAWNED_BY","REQUIRES_ITEMS","OBTAINED_FROM","REQUIRES_ACCESS","REQUIRES_MISSION","UNLOCKS"})
        assert closure["root"]=="entity:av"
        assert next(g for g in closure["gates"] if g["group_id"]=="jol-trade")["operator"]=="AND"
        assert len(next(g for g in closure["gates"] if g["group_id"]=="jol-trade")["edge_ids"])==3
        assert next(g for g in closure["gates"] if g["group_id"]=="organ-source")["operator"]=="OR"
        assert {"item:v1","item:v2","item:v3"}<={edge["target_node"] for edge in closure["edges"]}
        organ=next(e for e in closure["edges"] if e["edge_id"]=="organ-alt")
        assert organ["metadata"]["probability"]==0.5
        trade=next(e for e in closure["edges"] if e["edge_id"]=="mob:justice-organ")
        assert trade["metadata"]["quantity"]==3 and trade["metadata"]["consumed"] is True
        assert any(c["path"][-2:]==["mission:cop","zone:sea"] for c in closure["cycles"]),closure["cycles"]
        assert {row["node_id"] for row in closure["unresolved"]}>={"item:deed","missing:record"}
        assert len(closure["evidence"])==len(closure["edges"])
        projection=closure_projection(closure)
        assert any(node["node_type"]=="REQUIREMENT_GATE" for node in projection["nodes"])
        assert any(row["relationship"]=="REQUIRES_GATE" for row in projection["edges"])
        con.close()
    print("obtainability closure self-test: PASS")


if __name__=="__main__":
    main()
