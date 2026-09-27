"""A named regression/demo data set for the otherwise generic feature map.

This belongs with reference fixtures, not the closure engine: the graph service
only understands canonical nodes, relationships, gate metadata and evidence.
"""
from __future__ import annotations

from workbench.core import graph
from workbench.core.schema import DependencyEdge, Evidence
from workbench.core.services.obtainability_closure import build_obtainability_closure, closure_projection


RELATIONSHIPS={"SPAWNED_BY","REQUIRES_ITEMS","OBTAINED_FROM","REQUIRES_ACCESS","REQUIRES_MISSION","UNLOCKS"}


def build_projection() -> dict:
    con=graph.init_db(":memory:")
    try:
        rows={
            "entity:av":"Absolute Virtue", "entity:jol":"Jailer of Love",
            "item:fourth":"Fourth Virtue", "item:fifth":"Fifth Virtue", "item:sixth":"Sixth Virtue",
            "mob:justice":"Jailer of Justice", "mob:hope":"Jailer of Hope", "mob:prudence":"Jailer of Prudence",
            "item:first":"First Virtue", "item:second":"Second Virtue", "item:third":"Third Virtue",
            "item:deed":"Deed of Moderation", "item:organ":"HQ organ", "mob:source":"Sea source NM",
            "zone:sea":"Sea access", "mission:cop":"Chains of Promathia", "missing:source":"Unindexed source",
        }
        for node,label in rows.items():
            terminal=node == "mission:cop"
            con.execute("INSERT INTO entities VALUES (?,?,?,?)",(node,"DEMO",label,'{"obtainability_terminal": true}' if terminal else "{}"))

        def add(eid,source,target,relationship,group,**metadata):
            evidence=f"evidence:demo:{eid}"
            graph.insert_record(con,Evidence(evidence,"DEMO","absolute-virtue",f"demo:{eid}","demo",eid))
            graph.insert_record(con,DependencyEdge(eid,source,target,relationship,evidence,"VERIFIED","DISCOVERED",notes={"requirement_group":group,**metadata}))

        add("av-jol","entity:av","entity:jol","SPAWNED_BY",{"id":"av-spawn","operator":"AND"},probability=0.25)
        for later,mob in (("item:fourth","mob:justice"),("item:fifth","mob:hope"),("item:sixth","mob:prudence")):
            add(f"jol-{later}","entity:jol",later,"REQUIRES_ITEMS",{"id":"jol-trade","operator":"AND"},quantity=1,consumed=True)
            add(f"{later}-mob",later,mob,"OBTAINED_FROM",{"id":f"{later}-source","operator":"AND"})
        for mob,earlier in (("mob:justice","item:first"),("mob:hope","item:second"),("mob:prudence","item:third")):
            gate={"id":f"{mob}-trade","operator":"AND"}
            add(f"{mob}-virtue",mob,earlier,"REQUIRES_ITEMS",gate,quantity=1,consumed=True)
            add(f"{mob}-deed",mob,"item:deed","REQUIRES_ITEMS",gate,quantity=1,consumed=True)
            add(f"{mob}-organ",mob,"item:organ","REQUIRES_ITEMS",gate,quantity=3,consumed=True)
            add(f"{mob}-access",mob,"zone:sea","REQUIRES_ACCESS",{"id":f"{mob}-access","operator":"AND"},zone="Al'Taieu")
            add(f"{earlier}-source",earlier,"mob:source","OBTAINED_FROM",{"id":f"{earlier}-source","operator":"OR"},probability=0.5)
        add("organ-source","item:organ","mob:source","OBTAINED_FROM",{"id":"organ-source","operator":"OR"},probability=0.2)
        add("organ-missing","item:organ","missing:source","OBTAINED_FROM",{"id":"organ-source","operator":"OR"})
        add("source-access","mob:source","zone:sea","REQUIRES_ACCESS",{"id":"source-access","operator":"AND"},zone="Grand Palace of Hu'Xzoi")
        add("sea-cop","zone:sea","mission:cop","REQUIRES_MISSION",{"id":"sea-access","operator":"AND"})
        add("cop-cycle","mission:cop","zone:sea","UNLOCKS",{"id":"fixture-cycle","operator":"AND"})
        con.commit()
        closure=build_obtainability_closure(con,"entity:av",relationships=RELATIONSHIPS)
        projection=closure_projection(closure)
        projection["demo_name"]="Absolute Virtue"
        projection["source"]="Reference regression fixture; not a claim about live server state."
        return projection
    finally:
        con.close()
